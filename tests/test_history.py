import json
from pathlib import Path

from oterminus.history import PersistentHistoryStore, SessionHistory, SessionHistoryItem


def test_latest_failure_no_failure_returns_none() -> None:
    history = SessionHistory()
    item = history.start("pwd")
    item.execution_status = "executed"
    item.exit_code = 0

    assert history.latest_failure() is None


def test_latest_failure_prefers_latest_non_zero_and_success_does_not_replace() -> None:
    history = SessionHistory()
    first = history.start("bad")
    first.execution_status = "executed"
    first.exit_code = 2
    success = history.start("good")
    success.execution_status = "executed"
    success.exit_code = 0

    assert history.latest_failure() is first

    second = history.start("worse")
    second.execution_status = "executed"
    second.exit_code = 7

    assert history.latest_failure() is second


def test_persisted_history_loads_legacy_records_without_failure_fields(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    path.write_text('{"id": 1, "user_input": "legacy", "exit_code": 1}\n', encoding="utf-8")
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=False)

    items = store.load()

    assert len(items) == 1
    assert items[0].stderr is None
    assert items[0].failure_likely_cause is None


def test_persisted_history_ignores_legacy_output_fields(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    path.write_text(
        '{"id": 1, "user_input": "legacy", "stdout": "secret out", "stderr": "secret err"}\n',
        encoding="utf-8",
    )
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=False)

    items = store.load()

    assert len(items) == 1
    assert items[0].stdout is None
    assert items[0].stderr is None


def test_persistent_history_redacts_new_failure_fields(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=True)
    store.append(
        SessionHistoryItem(
            id=1,
            user_input="token=abc123",
            rendered_command="echo abc123",
            execution_status="executed",
            exit_code=1,
            stdout="out token=abc123",
            stderr="err token=abc123",
            failure_stderr_summary="summary token=abc123",
            failure_likely_cause="cause token=abc123",
            failure_suggested_next_action="inspect token=abc123",
        )
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert "stdout" not in payload
    assert "stderr" not in payload
    assert payload["failure_stderr_summary"] == "summary token=[REDACTED]"
    assert payload["failure_likely_cause"] == "cause token=[REDACTED]"
    assert payload["failure_suggested_next_action"] == "inspect token=[REDACTED]"


def test_persistent_history_keeps_new_failure_fields_when_redaction_disabled(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.jsonl"
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=False)
    store.append(
        SessionHistoryItem(
            id=1,
            user_input="x",
            stdout="secret out",
            stderr="secret err",
            stdout_truncated=True,
            stderr_truncated=True,
            stdout_original_chars=100,
            stderr_original_chars=200,
            failure_stderr_summary="summary secret",
            exit_code=1,
        )
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert "stdout" not in payload
    assert "stderr" not in payload
    assert payload["stdout_truncated"] is True
    assert payload["stderr_truncated"] is True
    assert payload["stdout_original_chars"] == 100
    assert payload["stderr_original_chars"] == 200
    assert payload["failure_stderr_summary"] == "summary secret"


def test_persistent_history_round_trips_recovery_metadata(tmp_path) -> None:
    path = tmp_path / "history.jsonl"
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=False)
    store.append(
        SessionHistoryItem(
            id=2,
            user_input="ls /",
            recovery_source_history_id=1,
            recovery_request=True,
        )
    )

    loaded = store.load()

    assert loaded[0].recovery_source_history_id == 1
    assert loaded[0].recovery_request is True

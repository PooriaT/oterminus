import json
from pathlib import Path
from unittest.mock import Mock

from oterminus.config import load_config

from oterminus.cli import RunMode, handle_request
from oterminus.history import PersistentHistoryStore, SessionHistory, SessionHistoryItem
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel
from oterminus.policies import PolicyConfig
from oterminus.validator import Validator


def test_history_config_defaults_to_disabled_and_redacted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_HISTORY_ENABLED", raising=False)
    monkeypatch.delenv("OTERMINUS_HISTORY_REDACT", raising=False)
    monkeypatch.delenv("OTERMINUS_AUDIT_REDACT", raising=False)

    config = load_config()

    assert config.history_enabled is False
    assert config.history_redact is True


def test_persistence_writes_only_bounded_metadata_not_outputs_or_raw_planner(
    tmp_path: Path,
) -> None:
    path = tmp_path / "h.jsonl"
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=True)
    item = SessionHistoryItem(
        id=1,
        user_input="TOKEN=secret",
        rendered_command="env TOKEN",
        proposal_origin="llm_planner",
        command_family="env",
        risk_level="safe",
        validation_status="accepted",
        execution_status="executed",
        exit_code=0,
    )
    item.proposal = {"raw_planner_response": "TOKEN=secret"}
    item.validation = {"stdout": "TOKEN=secret"}

    store.append(item)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["user_input"] == "TOKEN=[REDACTED]"
    assert payload["rendered_command"] == "env TOKEN"
    assert payload["proposal_origin"] == "llm_planner"
    assert payload["command_family"] == "env"
    assert "stdout" not in payload
    assert "stderr" not in payload
    assert "failure_stderr_summary" not in payload
    assert "failure_stdout_summary" not in payload
    assert "proposal" not in payload
    assert "validation" not in payload
    assert "raw_planner_response" not in path.read_text(encoding="utf-8")


def test_persistence_disabled_does_not_create_file(tmp_path: Path) -> None:
    store = PersistentHistoryStore(tmp_path / "h.jsonl", enabled=False, limit=10, redact=True)
    store.append(SessionHistoryItem(id=1, user_input="echo hi", execution_status="executed"))
    assert not (tmp_path / "h.jsonl").exists()


def test_persistence_enabled_writes_and_loads(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=False)
    store.append(
        SessionHistoryItem(
            id=1,
            user_input="echo hi",
            proposal_origin="direct_command",
            execution_status="executed",
        )
    )
    items = store.load()
    assert len(items) == 1
    assert items[0].user_input == "echo hi"
    assert items[0].proposal_origin == "direct_command"


def test_persistence_loads_legacy_records_without_proposal_origin(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    path.write_text('{"id":1,"user_input":"legacy"}\n', encoding="utf-8")
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=False)

    items = store.load()

    assert len(items) == 1
    assert items[0].proposal_origin is None


def test_handle_request_persists_canonical_proposal_origins(tmp_path: Path) -> None:
    history = SessionHistory()
    store = PersistentHistoryStore(tmp_path / "h.jsonl", enabled=True, limit=10, redact=False)
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    executor = Mock()
    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="ls",
        arguments={
            "path": ".",
            "long": False,
            "human_readable": False,
            "all": False,
            "recursive": False,
        },
        summary="show files",
        explanation="List files.",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    direct_code = handle_request(
        "pwd",
        planner,
        validator,
        executor,
        run_mode=RunMode.DRY_RUN,
        session_history=history,
        persistent_store=store,
    )
    shortcut_code = handle_request(
        "show current directory",
        planner,
        validator,
        executor,
        run_mode=RunMode.DRY_RUN,
        session_history=history,
        persistent_store=store,
    )
    planner_code = handle_request(
        "show files",
        planner,
        validator,
        executor,
        run_mode=RunMode.DRY_RUN,
        session_history=history,
        persistent_store=store,
    )

    assert (direct_code, shortcut_code, planner_code) == (0, 0, 0)
    assert [item.proposal_origin for item in history.all_items()] == [
        "direct_command",
        "deterministic_shortcut",
        "llm_planner",
    ]
    persisted = [json.loads(line) for line in (tmp_path / "h.jsonl").read_text().splitlines()]
    assert [item["proposal_origin"] for item in persisted] == [
        "direct_command",
        "deterministic_shortcut",
        "llm_planner",
    ]


def test_persistence_redacts_sensitive_values(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=True)
    store.append(
        SessionHistoryItem(id=1, user_input="token=abc123", rendered_command="curl --token abc123")
    )
    raw = path.read_text(encoding="utf-8")
    assert "abc123" not in raw
    assert "[REDACTED]" in raw


def test_load_ignores_malformed_jsonl_line(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    path.write_text('not-json\n{"id":1,"user_input":"ls"}\n', encoding="utf-8")
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=True)
    items = store.load()
    assert len(items) == 1


def test_history_limit_enforced_on_load(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    lines = [f'{{"id":{i},"user_input":"req {i}"}}' for i in range(1, 6)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    store = PersistentHistoryStore(path, enabled=True, limit=2, redact=False)
    items = store.load()
    assert [item.user_input for item in items] == ["req 4", "req 5"]


def test_session_history_assigns_distinct_ids_for_persisted_items() -> None:
    history = SessionHistory()
    history.add_persisted(
        SessionHistoryItem(id=0, user_input="old", source="persisted", persisted_id=9)
    )
    current = history.start("new")
    assert current.id == 2

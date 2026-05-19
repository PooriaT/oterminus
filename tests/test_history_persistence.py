from pathlib import Path

from oterminus.history import PersistentHistoryStore, SessionHistory, SessionHistoryItem


def test_persistence_disabled_does_not_create_file(tmp_path: Path) -> None:
    store = PersistentHistoryStore(tmp_path / "h.jsonl", enabled=False, limit=10, redact=True)
    store.append(SessionHistoryItem(id=1, user_input="echo hi", execution_status="executed"))
    assert not (tmp_path / "h.jsonl").exists()


def test_persistence_enabled_writes_and_loads(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    store = PersistentHistoryStore(path, enabled=True, limit=10, redact=False)
    store.append(SessionHistoryItem(id=1, user_input="echo hi", execution_status="executed"))
    items = store.load()
    assert len(items) == 1
    assert items[0].user_input == "echo hi"


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

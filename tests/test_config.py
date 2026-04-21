from pathlib import Path

from oterminus.config import load_config


def test_load_config_audit_path_from_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_AUDIT_LOG_PATH", str(tmp_path / "audit-lines.jsonl"))
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))

    config = load_config()

    assert config.audit_log_path == tmp_path / "audit-lines.jsonl"

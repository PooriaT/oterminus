from pathlib import Path

from oterminus.config import load_config


def test_load_config_audit_path_from_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_AUDIT_LOG_PATH", str(tmp_path / "audit-lines.jsonl"))
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))

    config = load_config()

    assert config.audit_log_path == tmp_path / "audit-lines.jsonl"


def test_load_config_invalid_user_audit_path_type_falls_back_to_default(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"audit_log_path": 123}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_AUDIT_LOG_PATH", raising=False)

    config = load_config()

    assert config.audit_log_path == Path.home() / ".oterminus" / "audit.jsonl"


def test_load_config_audit_controls_default_to_enabled_and_redacted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_AUDIT_ENABLED", raising=False)
    monkeypatch.delenv("OTERMINUS_AUDIT_REDACT", raising=False)

    config = load_config()

    assert config.audit_enabled is True
    assert config.audit_redact is True


def test_load_config_audit_controls_can_be_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_AUDIT_ENABLED", "false")
    monkeypatch.setenv("OTERMINUS_AUDIT_REDACT", "false")

    config = load_config()

    assert config.audit_enabled is False
    assert config.audit_redact is False

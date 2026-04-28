import json
from pathlib import Path

from oterminus.audit import AuditEvent, AuditLogger
from oterminus.audit_privacy import redact_argv, redact_text


def test_redact_text_redacts_token_password_and_api_key_values() -> None:
    raw = "token=abc123 --password hunter2 --api-key sk-live-123"

    redacted = redact_text(raw)

    assert "abc123" not in redacted
    assert "hunter2" not in redacted
    assert "sk-live-123" not in redacted
    assert redacted.count("[REDACTED]") >= 3


def test_redact_text_redacts_bearer_tokens() -> None:
    raw = "Authorization: Bearer super-secret-jwt"

    redacted = redact_text(raw)

    assert "super-secret-jwt" not in redacted
    assert "Bearer [REDACTED]" in redacted


def test_redact_argv_redacts_sensitive_env_assignments() -> None:
    argv = ["curl", "API_KEY=my-secret", "TOKEN=abc", "https://example.com"]

    redacted = redact_argv(argv)

    assert redacted[1] == "API_KEY=[REDACTED]"
    assert redacted[2] == "TOKEN=[REDACTED]"


def test_redact_text_handles_invalid_url_port_without_crashing() -> None:
    raw = "curl https://user:pass@example.com:bad/path"

    redacted = redact_text(raw)

    assert "user:pass@" not in redacted
    assert "https://[REDACTED]@example.com/path" in redacted


def test_audit_logger_respects_redaction_default(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    event = AuditEvent.start("run --token abc123")
    event.rendered_command = "curl --password hunter2 https://user:pw@example.com"
    event.argv = ["curl", "--token", "abc123", "API_KEY=shh"]
    event.warnings = ["command had --api-key sk-test-xyz"]
    logger.write(event)

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["user_input"] == "run --token [REDACTED]"
    assert payload["argv"][2] == "[REDACTED]"
    assert "hunter2" not in payload["rendered_command"]
    assert "sk-test-xyz" not in payload["warnings"][0]


def test_audit_logger_can_disable_redaction_when_explicitly_opted_out(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path, redact=False)
    event = AuditEvent.start("run --token abc123")
    event.argv = ["curl", "--token", "abc123"]
    logger.write(event)

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["user_input"] == "run --token abc123"
    assert payload["argv"][2] == "abc123"

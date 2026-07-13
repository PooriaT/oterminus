from oterminus.audit import AuditEvent


def test_audit_event_includes_recovery_metadata() -> None:
    event = AuditEvent.start("ls /")
    event.recovery_source_history_id = 1
    event.recovery_request = True

    payload = event.to_payload()

    assert payload["recovery_source_history_id"] == 1
    assert payload["recovery_request"] is True


def test_audit_event_includes_clarification_metadata() -> None:
    event = AuditEvent.start("clean this folder")
    event.ambiguity_detected = True
    event.ambiguity_reason = "broad token=abc123"
    event.ambiguity_safe_options = ["inspect token=abc123"]
    event.clarification_requested = True
    event.clarification_prompt = "clarify> "
    event.clarification_answer = "list token=abc123"
    event.clarification_outcome = "clarified"
    event.clarified_request_text = "list token=abc123"
    event.clarification_source_history_id = 4
    event.is_clarified_request = True

    payload = event.to_payload()

    assert payload["clarification_requested"] is True
    assert payload["clarification_prompt"] == "clarify> "
    assert payload["clarification_answer"] == "list token=abc123"
    assert payload["clarification_outcome"] == "clarified"
    assert payload["clarified_request_text"] == "list token=abc123"
    assert payload["clarification_source_history_id"] == 4
    assert payload["is_clarified_request"] is True

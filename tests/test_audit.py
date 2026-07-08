from oterminus.audit import AuditEvent


def test_audit_event_includes_recovery_metadata() -> None:
    event = AuditEvent.start("ls /")
    event.recovery_source_history_id = 1
    event.recovery_request = True

    payload = event.to_payload()

    assert payload["recovery_source_history_id"] == 1
    assert payload["recovery_request"] is True

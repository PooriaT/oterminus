from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oterminus.audit_privacy import redact_argv, redact_text


@dataclass
class AuditEvent:
    timestamp: str
    user_input: str
    direct_command_detected: bool
    ambiguity_detected: bool = False
    ambiguity_reason: str | None = None
    ambiguity_safe_options: list[str] = field(default_factory=list)
    routed_category: str | None = None
    proposal_mode: str | None = None
    command_family: str | None = None
    rendered_command: str | None = None
    argv: list[str] = field(default_factory=list)
    validation_accepted: bool | None = None
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    confirmation_result: str | None = None
    execution_exit_code: int | None = None
    rerun_source_history_id: int | None = None
    duration_ms: int | None = None

    @classmethod
    def start(cls, user_input: str) -> AuditEvent:
        return cls(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            user_input=user_input,
            direct_command_detected=False,
        )

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


class AuditLogger:
    def __init__(self, path: Path, *, redact: bool = True):
        self.path = path
        self.redact = redact

    def write(self, event: AuditEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.to_payload()
        if self.redact:
            payload = self._redacted_payload(payload)
        serialized = json.dumps(payload, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(serialized + "\n")

    def status(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "exists": "yes" if self.path.exists() else "no",
            "redaction": "enabled" if self.redact else "disabled (explicit opt-out)",
        }

    def _redacted_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        cloned = dict(payload)
        for field_name in ("user_input", "rendered_command", "ambiguity_reason"):
            value = cloned.get(field_name)
            if isinstance(value, str):
                cloned[field_name] = redact_text(value)
        for field_name in ("warnings", "rejection_reasons", "ambiguity_safe_options"):
            raw = cloned.get(field_name)
            if isinstance(raw, list):
                cloned[field_name] = [redact_text(item) if isinstance(item, str) else item for item in raw]
        raw_argv = cloned.get("argv")
        if isinstance(raw_argv, list):
            cloned["argv"] = redact_argv([str(item) for item in raw_argv])
        return cloned

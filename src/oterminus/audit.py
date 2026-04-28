from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
    def __init__(self, path: Path):
        self.path = path

    def write(self, event: AuditEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(event.to_payload(), sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(serialized + "\n")

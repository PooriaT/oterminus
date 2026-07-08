from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from oterminus.audit_privacy import redact_text

LOGGER = logging.getLogger("oterminus")


@dataclass
class SessionHistoryItem:
    id: int
    user_input: str
    source: str = "session"
    persisted_id: int | None = None
    timestamp: str | None = None
    direct_command_detected: bool = False
    routed_category: str | None = None
    proposal_origin: str | None = None
    proposal_mode: str | None = None
    command_family: str | None = None
    rendered_command: str | None = None
    risk_level: str | None = None
    validation_status: str | None = None
    execution_status: str = "pending"
    exit_code: int | None = None
    rerun_source_history_id: int | None = None
    recovery_source_history_id: int | None = None
    recovery_request: bool = False
    proposal: object | None = None
    validation: object | None = None
    stdout: str | None = None
    stderr: str | None = None
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    stdout_original_chars: int | None = None
    stderr_original_chars: int | None = None
    failure_stderr_summary: str | None = None
    failure_likely_cause: str | None = None
    failure_suggested_next_action: str | None = None
    failure_suggested_next_action_mode: str | None = None
    failure_explanation_error: str | None = None


class SessionHistory:
    def __init__(self) -> None:
        self._items: list[SessionHistoryItem] = []
        self._next_id = 1

    def start(self, user_input: str) -> SessionHistoryItem:
        item = SessionHistoryItem(id=self._next_id, user_input=user_input)
        self._next_id += 1
        self._items.append(item)
        return item

    def add_persisted(self, item: SessionHistoryItem) -> None:
        item.id = self._next_id
        item.source = "persisted"
        self._next_id += 1
        self._items.append(item)

    def all_items(self) -> list[SessionHistoryItem]:
        return list(self._items)

    def find(self, history_id: int) -> SessionHistoryItem | None:
        for item in self._items:
            if item.id == history_id:
                return item
        return None

    def latest_failure(self) -> SessionHistoryItem | None:
        """Return the most recent failed execution in this session.

        Prefer concrete command failures represented by a non-zero exit code.
        If no such entry exists, fall back to terminal execution failure states
        that may not have captured a process exit code.
        """
        fallback_statuses = {"timed_out", "execution_failed", "interrupted"}
        fallback: SessionHistoryItem | None = None
        for item in reversed(self._items):
            if item.exit_code is not None and item.exit_code != 0:
                return item
            if fallback is None and item.execution_status in fallback_statuses:
                fallback = item
        return fallback

    def render_table(self, limit: int | None = None, *, source: str | None = None) -> str:
        items = self._items
        if source is not None:
            items = [item for item in items if item.source == source]
        items = items if limit is None else items[-limit:]
        if not items:
            return (
                "No session history yet." if source != "persisted" else "No persisted history yet."
            )

        rows = [
            (
                str(item.id),
                item.source,
                _truncate(item.user_input, 34),
                _truncate(item.rendered_command or "(none)", 34),
                item.risk_level or "-",
                item.execution_status,
            )
            for item in items
        ]
        headers = ("id", "source", "input", "command", "risk", "status")
        widths = [
            max(len(headers[idx]), *(len(row[idx]) for row in rows)) for idx in range(len(headers))
        ]

        def _line(values: tuple[str, ...]) -> str:
            return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(values))

        output = [_line(headers), _line(tuple("-" * width for width in widths))]
        output.extend(_line(row) for row in rows)
        return "\n".join(output)


class PersistentHistoryStore:
    def __init__(self, path: Path, *, enabled: bool, limit: int, redact: bool) -> None:
        self.path = path
        self.enabled = enabled
        try:
            parsed_limit = int(limit)
        except (TypeError, ValueError):
            parsed_limit = 100
        self.limit = max(1, parsed_limit)
        self.redact = redact

    def load(self) -> list[SessionHistoryItem]:
        if not self.enabled or not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            LOGGER.warning("unable_to_read_persistent_history path=%s error=%s", self.path, exc)
            return []
        items: list[SessionHistoryItem] = []
        for raw in lines:
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                LOGGER.warning("ignored_malformed_history_line path=%s", self.path)
                continue
            user_input = payload.get("user_input")
            if not isinstance(user_input, str):
                continue
            items.append(
                SessionHistoryItem(
                    id=0,
                    source="persisted",
                    persisted_id=int(payload.get("id", 0))
                    if str(payload.get("id", "")).isdigit()
                    else None,
                    timestamp=payload.get("timestamp"),
                    user_input=user_input,
                    direct_command_detected=bool(payload.get("direct_command_detected", False)),
                    routed_category=payload.get("routed_category"),
                    proposal_origin=payload.get("proposal_origin"),
                    proposal_mode=payload.get("proposal_mode"),
                    command_family=payload.get("command_family"),
                    rendered_command=payload.get("rendered_command"),
                    risk_level=payload.get("risk_level"),
                    validation_status=payload.get("validation_status"),
                    execution_status=payload.get("execution_status") or "pending",
                    exit_code=payload.get("exit_code"),
                    rerun_source_history_id=payload.get("rerun_source_history_id"),
                    recovery_source_history_id=payload.get("recovery_source_history_id"),
                    recovery_request=bool(payload.get("recovery_request", False)),
                    stdout_truncated=bool(payload.get("stdout_truncated", False)),
                    stderr_truncated=bool(payload.get("stderr_truncated", False)),
                    stdout_original_chars=payload.get("stdout_original_chars"),
                    stderr_original_chars=payload.get("stderr_original_chars"),
                    failure_stderr_summary=payload.get("failure_stderr_summary"),
                    failure_likely_cause=payload.get("failure_likely_cause"),
                    failure_suggested_next_action=payload.get("failure_suggested_next_action"),
                    failure_suggested_next_action_mode=payload.get(
                        "failure_suggested_next_action_mode"
                    ),
                    failure_explanation_error=payload.get("failure_explanation_error"),
                )
            )
        return items[-self.limit :]

    def append(self, item: SessionHistoryItem) -> None:
        if not self.enabled:
            return
        payload = {
            "id": item.id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "user_input": item.user_input,
            "direct_command_detected": item.direct_command_detected,
            "routed_category": item.routed_category,
            "proposal_origin": item.proposal_origin,
            "proposal_mode": item.proposal_mode,
            "command_family": item.command_family,
            "rendered_command": item.rendered_command,
            "risk_level": item.risk_level,
            "validation_status": item.validation_status,
            "execution_status": item.execution_status,
            "exit_code": item.exit_code,
            "rerun_source_history_id": item.rerun_source_history_id,
            "recovery_source_history_id": item.recovery_source_history_id,
            "recovery_request": item.recovery_request,
            "stdout_truncated": item.stdout_truncated,
            "stderr_truncated": item.stderr_truncated,
            "stdout_original_chars": item.stdout_original_chars,
            "stderr_original_chars": item.stderr_original_chars,
            "failure_stderr_summary": item.failure_stderr_summary,
            "failure_likely_cause": item.failure_likely_cause,
            "failure_suggested_next_action": item.failure_suggested_next_action,
            "failure_suggested_next_action_mode": item.failure_suggested_next_action_mode,
            "failure_explanation_error": item.failure_explanation_error,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        if not item.recovery_request:
            payload.pop("recovery_request", None)
        if self.redact:
            for key in (
                "user_input",
                "rendered_command",
                "failure_stderr_summary",
                "failure_likely_cause",
                "failure_suggested_next_action",
                "failure_explanation_error",
            ):
                if isinstance(payload.get(key), str):
                    payload[key] = redact_text(payload[key])
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True) + "\n")
        except OSError as exc:
            LOGGER.warning("unable_to_write_persistent_history path=%s error=%s", self.path, exc)


def _truncate(value: str, width: int) -> str:
    value = " ".join(value.split())
    if len(value) <= width:
        return value
    return value[: width - 1] + "…"

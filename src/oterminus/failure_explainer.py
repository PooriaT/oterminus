from __future__ import annotations

import json
from dataclasses import dataclass

from oterminus.audit_privacy import redact_text
from oterminus.models import FailureExplanation, SuggestedNextActionMode
from oterminus.ollama_client import OllamaPlannerClient


@dataclass(frozen=True)
class FailureExplainerConfig:
    enabled: bool = False
    max_chars: int = 4000


class FailureExplainer:
    def __init__(self, ollama_client: OllamaPlannerClient, *, max_chars: int = 4000):
        self._ollama_client = ollama_client
        self._max_chars = max_chars

    def explain(
        self, *, command: str, exit_code: int, stdout: str, stderr: str
    ) -> FailureExplanation:
        stderr_summary = _redact_and_truncate(stderr, self._max_chars)
        stdout_summary = _redact_and_truncate(stdout, self._max_chars)

        payload = {
            "command": redact_text(command),
            "exit_code": exit_code,
            "stderr": stderr_summary,
            "stdout": stdout_summary,
            "instruction": (
                "Explain likely cause in one sentence. Return JSON with keys "
                "likely_cause, stderr_summary, suggested_next_action, suggested_next_action_mode, notes. "
                "suggested_next_action_mode must be one of dry-run, copy-only, none. "
                "At most one read-only command suggestion. Never suggest destructive actions."
            ),
        }
        raw = self._ollama_client.chat_json(
            "You explain failed shell commands conservatively and safely.", json.dumps(payload)
        )
        parsed = json.loads(raw)

        likely_cause = str(
            parsed.get("likely_cause") or "The command failed with a non-zero exit code."
        )
        suggested_next_action = parsed.get("suggested_next_action")
        if suggested_next_action is not None:
            suggested_next_action = redact_text(str(suggested_next_action).strip()) or None
        raw_mode = str(parsed.get("suggested_next_action_mode") or "none").lower()
        if raw_mode not in {"dry-run", "copy-only", "none"}:
            raw_mode = "none"
        notes = [redact_text(str(item)) for item in parsed.get("notes", []) if str(item).strip()]

        if not suggested_next_action:
            raw_mode = "none"

        parsed_stderr_summary = str(parsed.get("stderr_summary") or stderr_summary)

        return FailureExplanation(
            command=redact_text(command),
            exit_code=exit_code,
            stderr_summary=_truncate(redact_text(parsed_stderr_summary), self._max_chars),
            likely_cause=redact_text(likely_cause),
            suggested_next_action=suggested_next_action,
            suggested_next_action_mode=SuggestedNextActionMode(raw_mode),
            notes=notes,
        )


def _redact_and_truncate(value: str, max_chars: int) -> str:
    return _truncate(redact_text(value), max_chars)


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars]

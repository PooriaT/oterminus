from __future__ import annotations

import shlex

from oterminus.command_registry import get_command_spec, looks_like_direct_invocation
from oterminus.models import ActionType, Proposal, ProposalMode


def detect_direct_command(request: str) -> Proposal | None:
    command = request.strip()
    if not command:
        return None

    try:
        args = shlex.split(command)
    except ValueError:
        return None

    if not args:
        return None

    base = args[0]
    spec = get_command_spec(base)
    if spec is None or not spec.direct_supported:
        return None

    if not looks_like_direct_invocation(base, args[1:]):
        return None

    notes = ["Detected as a direct shell command; skipped the LLM planner.", *spec.notes]

    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.RAW,
        command_family=base,
        command=command,
        summary=f"Run direct command: {spec.name}",
        explanation="Input already looks like a shell command, so it will be validated locally and executed directly.",
        needs_confirmation=True,
        notes=notes,
    )

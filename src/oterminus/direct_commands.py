from __future__ import annotations

import shlex

from oterminus.commands import get_command_spec, looks_like_direct_invocation
from oterminus.models import ActionType, Proposal, ProposalMode
from oterminus.structured_commands import StructuredCommandError, parse_raw_command_as_structured


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
    try:
        parsed = parse_raw_command_as_structured(command)
    except StructuredCommandError as exc:
        notes.append(f"Structured parsing skipped: {exc}")
        parsed = None
    if parsed is not None:
        command_family, arguments = parsed
        return Proposal(
            action_type=ActionType.SHELL_COMMAND,
            mode=ProposalMode.STRUCTURED,
            command_family=command_family,
            arguments=arguments,
            command=command,
            summary=f"Run direct command: {spec.name}",
            explanation="Input already looks like a shell command, so it will be validated locally and rendered deterministically when possible.",
            needs_confirmation=True,
            notes=notes,
        )

    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command_family=base,
        command=command,
        summary=f"Run direct command: {spec.name}",
        explanation="Input already looks like a shell command, so it will be validated locally and executed as an experimental fallback.",
        needs_confirmation=True,
        notes=notes,
    )

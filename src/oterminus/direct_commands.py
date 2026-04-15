from __future__ import annotations

import shlex

from oterminus.models import ActionType, Proposal

DIRECT_COMMANDS = {
    "cd",
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "du",
    "stat",
    "mkdir",
    "cp",
    "mv",
    "chmod",
    "touch",
    "rm",
    "chown",
    "sudo",
}


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
    if base not in DIRECT_COMMANDS:
        return None

    if not _looks_like_direct_command(base, args[1:]):
        return None

    notes = ["Detected as a direct shell command; skipped the LLM planner."]
    if base == "cd":
        notes.append("Changes the oterminus working directory for the current REPL session.")

    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        command=command,
        summary=f"Run direct command: {base}",
        explanation="Input already looks like a shell command, so it will be validated locally and executed directly.",
        needs_confirmation=True,
        notes=notes,
    )


def _looks_like_direct_command(base: str, operands: list[str]) -> bool:
    if base == "pwd":
        return len(operands) == 0

    if base == "cd":
        return len(operands) <= 1

    if base == "find":
        if not operands:
            return True
        first = operands[0]
        return first in {".", "..", "/"} or first.startswith(("/", "~/", "./", "../")) or any(
            operand.startswith("-") for operand in operands
        )

    if base == "grep":
        return any(operand.startswith("-") for operand in operands) or any(
            _looks_like_path(operand) for operand in operands
        )

    min_operands = {
        "ls": 0,
        "cat": 1,
        "head": 1,
        "tail": 1,
        "du": 0,
        "stat": 1,
        "mkdir": 1,
        "cp": 2,
        "mv": 2,
        "chmod": 2,
        "touch": 1,
        "rm": 1,
        "chown": 2,
        "sudo": 1,
    }
    return len(operands) >= min_operands.get(base, 0)


def _looks_like_path(value: str) -> bool:
    return (
        value in {".", "..", "~"}
        or value.startswith(("/", "~/", "./", "../"))
        or "/" in value
        or "." in value
    )

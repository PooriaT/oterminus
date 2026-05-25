from __future__ import annotations

import shlex

from oterminus.commands import get_enabled_command_spec, looks_like_direct_invocation
from oterminus.models import ActionType, Proposal, ProposalMode
from oterminus.structured_commands import StructuredCommandError, parse_raw_command_as_structured


def detect_direct_command(
    request: str, *, disabled_pack_ids: frozenset[str] | None = None, platform_id: str | None = None
) -> Proposal | None:
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
    project_health_arguments = _parse_project_health_direct(args)
    if project_health_arguments is not None:
        spec = get_enabled_command_spec("project_health", disabled_pack_ids, platform_id)
        if spec is None:
            return None
        return Proposal(
            action_type=ActionType.SHELL_COMMAND,
            mode=ProposalMode.STRUCTURED,
            command_family="project_health",
            arguments=project_health_arguments,
            command=command,
            summary="Run direct command: project_health",
            explanation=(
                "Input already matches a curated project health command, so it will be validated "
                "locally and rendered deterministically."
            ),
            needs_confirmation=True,
            notes=["Detected as a direct shell command; skipped the LLM planner.", *spec.notes],
        )

    spec = get_enabled_command_spec(base, disabled_pack_ids, platform_id)
    if spec is None or not spec.direct_supported:
        return None

    if not looks_like_direct_invocation(base, args[1:], disabled_pack_ids, platform_id):
        if base not in {"tar", "unzip", "zip"}:
            return None
        if _looks_like_natural_language_archive_request(args[1:]):
            return None
        return Proposal(
            action_type=ActionType.SHELL_COMMAND,
            mode=ProposalMode.EXPERIMENTAL,
            command_family=base,
            command=command,
            summary=f"Run direct command: {spec.name}",
            explanation=(
                "Input already looks like an archive command, so it will be validated locally "
                "against guarded archive constraints."
            ),
            needs_confirmation=True,
            notes=[
                "Detected as a direct shell command; skipped the LLM planner.",
                *spec.notes,
                "Unsupported archive forms are rejected by validation.",
            ],
        )

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
            explanation=(
                "Input already looks like a shell command, so it will be validated locally and "
                "rendered deterministically when possible."
            ),
            needs_confirmation=True,
            notes=notes,
        )

    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command_family=base,
        command=command,
        summary=f"Run direct command: {spec.name}",
        explanation=(
            "Input already looks like a shell command, so it will be validated locally and "
            "executed as an experimental fallback."
        ),
        needs_confirmation=True,
        notes=notes,
    )


def _looks_like_natural_language_archive_request(operands: list[str]) -> bool:
    return any(
        operand.lower() in {"into", "to", "in", "this", "everything", "files", "project"}
        for operand in operands
    )


def _parse_project_health_direct(args: list[str]) -> dict[str, str] | None:
    mapping = {
        ("poetry", "run", "pytest"): "run_tests",
        ("poetry", "run", "ruff", "check", "."): "lint_check",
        ("poetry", "run", "ruff", "format", "--check", "."): "format_check",
        ("poetry", "run", "mkdocs", "build", "--strict"): "build_docs",
        ("poetry", "run", "oterminus-evals"): "run_evals",
    }
    operation = mapping.get(tuple(args))
    if operation is None:
        return None
    return {"operation": operation}

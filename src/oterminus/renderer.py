from __future__ import annotations

import json

from oterminus.messages import EXPERIMENTAL_USER_WARNING, EXPERIMENTAL_VERBOSE_EXPLANATION
from oterminus.models import Proposal, ProposalMode, ValidationResult
from oterminus.policies import ConfirmationLevel, confirmation_level

_DIRECT_DEBUG_NOTE_PREFIXES = (
    "Detected as a direct shell command;",
    "Structured parsing skipped:",
)


def render_preview(
    proposal: Proposal,
    validation: ValidationResult,
    *,
    verbose: bool = False,
    direct_command: bool = False,
) -> str:
    if direct_command and not verbose:
        return _render_direct_preview(proposal, validation)

    return _render_detailed_preview(proposal, validation, verbose=verbose)


def _render_detailed_preview(
    proposal: Proposal, validation: ValidationResult, *, verbose: bool
) -> str:
    level = confirmation_level(proposal.mode, validation.risk_level)
    header = (
        "--- oterminus proposal (EXPERIMENTAL) ---"
        if proposal.is_experimental
        else "--- oterminus proposal ---"
    )
    lines = [
        header,
        f"Summary      : {proposal.summary}",
        f"Mode         : {proposal.mode.value}",
        f"Experimental : {'yes' if proposal.is_experimental else 'no'}",
        f"Risk level   : {validation.risk_level.value}",
        f"Explanation  : {proposal.explanation}",
        f"Confirmation : {_format_confirmation_level(level)}",
    ]

    command = validation.rendered_command or proposal.command
    if command is not None:
        lines.insert(3, f"Command      : {command}")

    if proposal.command_family is not None:
        lines.insert(
            3 if proposal.command is None else 4, f"Command fam. : {proposal.command_family}"
        )

    if proposal.mode == ProposalMode.STRUCTURED and proposal.command:
        lines.append(f"Legacy cmd   : {proposal.command} (deprecated in structured mode)")

    if proposal.arguments:
        formatted = json.dumps(proposal.arguments, indent=2, sort_keys=True)
        argument_lines = formatted.splitlines()
        if len(argument_lines) == 1:
            lines.append(f"Arguments    : {formatted}")
        else:
            lines.append("Arguments    :")
            lines.extend(f"  {line}" for line in argument_lines)

    display_notes = _display_notes(proposal.notes, include_debug=verbose)
    if (
        verbose
        and proposal.is_experimental
        and not _has_equivalent_message(display_notes, EXPERIMENTAL_VERBOSE_EXPLANATION)
    ):
        display_notes.append(EXPERIMENTAL_VERBOSE_EXPLANATION)
    if display_notes:
        lines.append("Notes        : " + "; ".join(display_notes))

    display_warnings = _display_warnings(proposal, validation.warnings)
    if display_warnings:
        lines.append("Warnings     : " + "; ".join(display_warnings))

    if validation.reasons:
        lines.append("Rejections   : " + "; ".join(validation.reasons))

    return "\n".join(lines)


def _render_direct_preview(proposal: Proposal, validation: ValidationResult) -> str:
    command = validation.rendered_command or proposal.command or "(unavailable)"
    lines = [
        "--- command preview ---",
        f"Command: {command}",
        f"Risk: {validation.risk_level.value}",
    ]
    level = confirmation_level(proposal.mode, validation.risk_level)
    if level == ConfirmationLevel.VERY_STRONG:
        lines.append(f"Confirmation: {_format_confirmation_level(level)}")

    display_notes = _display_notes(proposal.notes, include_debug=False)
    if display_notes:
        lines.append("Notes: " + "; ".join(display_notes))

    display_warnings = _display_warnings(proposal, validation.warnings)
    if display_warnings:
        lines.append("Warnings: " + "; ".join(display_warnings))

    if validation.reasons:
        lines.append("Rejections: " + "; ".join(validation.reasons))

    return "\n".join(lines)


def _format_confirmation_level(level: ConfirmationLevel) -> str:
    if level == ConfirmationLevel.VERY_STRONG:
        return "very strong; type EXECUTE EXPERIMENTAL to run"
    return level.value


def _display_notes(notes: list[str], *, include_debug: bool) -> list[str]:
    notes = [
        note
        for note in notes
        if not _has_same_message(note, EXPERIMENTAL_USER_WARNING)
        and (include_debug or not _has_equivalent_message([note], EXPERIMENTAL_VERBOSE_EXPLANATION))
    ]
    if include_debug:
        return notes
    return [note for note in notes if not note.startswith(_DIRECT_DEBUG_NOTE_PREFIXES)]


def _display_warnings(proposal: Proposal, warnings: list[str]) -> list[str]:
    display_warnings = [
        warning
        for warning in warnings
        if not _has_equivalent_message([warning], EXPERIMENTAL_VERBOSE_EXPLANATION)
        and (proposal.is_experimental or not _has_same_message(warning, EXPERIMENTAL_USER_WARNING))
    ]
    if proposal.is_experimental and not _has_equivalent_message(
        display_warnings, EXPERIMENTAL_USER_WARNING
    ):
        display_warnings.insert(0, EXPERIMENTAL_USER_WARNING)
    return _unique_messages(display_warnings)


def _unique_messages(messages: list[str]) -> list[str]:
    unique: list[str] = []
    for message in messages:
        if not _has_same_message(message, *unique):
            unique.append(message)
    return unique


def _has_equivalent_message(messages: list[str], expected: str) -> bool:
    if expected == EXPERIMENTAL_VERBOSE_EXPLANATION:
        return any(
            _has_same_message(message, expected)
            or (
                "outside deterministic structured rendering" in message.lower()
                and "stricter confirmation" in message.lower()
            )
            for message in messages
        )
    return any(_has_same_message(message, expected) for message in messages)


def _has_same_message(message: str, *expected_messages: str) -> bool:
    normalized_message = _normalize_message(message)
    return any(normalized_message == _normalize_message(expected) for expected in expected_messages)


def _normalize_message(message: str) -> str:
    return " ".join(message.strip().lower().split())


def render_failure_explanation(explanation) -> str:
    lines = [
        "\n--- failure explanation ---",
        f"Command: {explanation.command}",
        f"Exit code: {explanation.exit_code}",
        f"Likely cause: {explanation.likely_cause}",
        f"stderr summary: {explanation.stderr_summary}",
        "",
    ]
    if explanation.suggested_next_action and explanation.suggested_next_action_mode.value != "none":
        lines.append("Safe next inspection:")
        lines.append(explanation.suggested_next_action)
    else:
        lines.append("No safe next action suggestion available.")
    lines.append("No next action was executed.")
    return "\n".join(lines)

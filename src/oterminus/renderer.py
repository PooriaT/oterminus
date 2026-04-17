from __future__ import annotations

import json

from oterminus.models import Proposal, ValidationResult
from oterminus.policies import ConfirmationLevel, confirmation_level


def render_preview(proposal: Proposal, validation: ValidationResult) -> str:
    level = confirmation_level(proposal.mode, validation.risk_level)
    header = "--- oterminus proposal (EXPERIMENTAL) ---" if proposal.is_experimental else "--- oterminus proposal ---"
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
        lines.insert(3 if proposal.command is None else 4, f"Command fam. : {proposal.command_family}")

    if proposal.arguments:
        formatted = json.dumps(proposal.arguments, indent=2, sort_keys=True)
        argument_lines = formatted.splitlines()
        if len(argument_lines) == 1:
            lines.append(f"Arguments    : {formatted}")
        else:
            lines.append("Arguments    :")
            lines.extend(f"  {line}" for line in argument_lines)

    if proposal.notes:
        lines.append("Notes        : " + "; ".join(proposal.notes))

    if validation.warnings:
        lines.append("Warnings     : " + "; ".join(validation.warnings))

    if validation.reasons:
        lines.append("Rejections   : " + "; ".join(validation.reasons))

    return "\n".join(lines)


def _format_confirmation_level(level: ConfirmationLevel) -> str:
    if level == ConfirmationLevel.VERY_STRONG:
        return "very strong"
    return level.value

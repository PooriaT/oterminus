from __future__ import annotations

from oterminus.models import Proposal, ValidationResult
from oterminus.policies import requires_strong_confirmation


def render_preview(proposal: Proposal, validation: ValidationResult) -> str:
    lines = [
        "--- oterminus proposal ---",
        f"Summary      : {proposal.summary}",
        f"Command      : {proposal.command}",
        f"Risk level   : {validation.risk_level.value}",
        f"Explanation  : {proposal.explanation}",
        f"Confirmation : {'strong' if requires_strong_confirmation(validation.risk_level) else 'standard'}",
    ]

    if proposal.notes:
        lines.append("Notes        : " + "; ".join(proposal.notes))

    if validation.warnings:
        lines.append("Warnings     : " + "; ".join(validation.warnings))

    if validation.reasons:
        lines.append("Rejections   : " + "; ".join(validation.reasons))

    return "\n".join(lines)

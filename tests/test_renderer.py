from oterminus.models import ActionType, Proposal, RiskLevel, ValidationResult
from oterminus.renderer import render_preview


def test_render_includes_sections() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        command="ls -lh",
        summary="List files with sizes",
        explanation="Uses long listing in human-readable format",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=["Current directory only"],
    )
    validation = ValidationResult(accepted=True, risk_level=RiskLevel.SAFE, warnings=["demo warning"])

    text = render_preview(proposal, validation)

    assert "Summary" in text
    assert "Command" in text
    assert "Risk level" in text
    assert "demo warning" in text

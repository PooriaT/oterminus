from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel, ValidationResult
from oterminus.renderer import render_preview


def test_render_includes_sections() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.RAW,
        command_family="ls",
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
    assert "Mode" in text
    assert "Command" in text
    assert "Command fam." in text
    assert "Risk level" in text
    assert "demo warning" in text


def test_render_structured_preview_without_raw_command() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"root": ".", "name": "*.py"},
        summary="Find Python files",
        explanation="Structured command proposal",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validation = ValidationResult(accepted=False, risk_level=RiskLevel.SAFE)

    text = render_preview(proposal, validation)

    assert "Mode         : structured" in text
    assert "Command fam. : find" in text
    assert "Arguments" in text
    assert '"name": "*.py"' in text

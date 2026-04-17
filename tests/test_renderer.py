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
        arguments={"path": ".", "name": "*.py"},
        summary="Find Python files",
        explanation="Structured command proposal",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validation = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )

    text = render_preview(proposal, validation)

    assert "Mode         : structured" in text
    assert "Command      : find . -name '*.py'" in text
    assert "Command fam. : find" in text
    assert "Arguments" in text
    assert '"name": "*.py"' in text


def test_render_experimental_preview_is_clearly_labeled() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command_family="cat",
        command="cat README.md",
        summary="Show readme",
        explanation="Experimental fallback",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=["Outside deterministic structured rendering"],
    )
    validation = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        warnings=["Experimental mode stays outside deterministic structured rendering and uses stricter confirmation."],
        rendered_command="cat README.md",
        argv=["cat", "README.md"],
    )

    text = render_preview(proposal, validation)

    assert "--- oterminus proposal (EXPERIMENTAL) ---" in text
    assert "Mode         : experimental" in text
    assert "Experimental : yes" in text
    assert "Confirmation : very strong" in text
    assert "Warnings" in text

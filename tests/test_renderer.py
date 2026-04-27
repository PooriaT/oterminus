from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel, ValidationResult
from oterminus.renderer import render_preview


def test_render_includes_sections() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
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


def test_render_structured_preview_with_legacy_raw_command() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        command="find src -name '*.py'",
        summary="Find Python files",
        explanation="Structured command proposal",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validation = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        warnings=["Structured mode ignores the deprecated raw command field and uses deterministic rendering."],
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )

    text = render_preview(proposal, validation)

    assert "Command      : find . -name '*.py'" in text
    assert "Legacy cmd   : find src -name '*.py' (deprecated in structured mode)" in text


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


def test_render_direct_command_default_is_concise() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="ls",
        arguments={
            "path": ".",
            "long": True,
            "human_readable": True,
            "all": False,
            "recursive": False,
        },
        summary="Run direct command: ls",
        explanation="Input already looks like a shell command.",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=["Detected as a direct shell command; skipped the LLM planner."],
    )
    validation = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls -lh",
        argv=["ls", "-lh"],
    )

    text = render_preview(proposal, validation, direct_command=True)

    assert "--- command preview ---" in text
    assert "Command: ls -lh" in text
    assert "Risk: safe" in text
    assert "Summary" not in text
    assert "Explanation" not in text
    assert "LLM planner" not in text


def test_render_direct_command_verbose_shows_debug_notes() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command_family="cd",
        command="cd src",
        summary="Run direct command: cd",
        explanation="Input already looks like a shell command.",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=["Detected as a direct shell command; skipped the LLM planner."],
    )
    validation = ValidationResult(accepted=True, risk_level=RiskLevel.SAFE, rendered_command="cd src", argv=["cd", "src"])

    text = render_preview(proposal, validation, verbose=True, direct_command=True)

    assert "Summary      : Run direct command: cd" in text
    assert "Explanation  : Input already looks like a shell command." in text
    assert "Notes        : Detected as a direct shell command; skipped the LLM planner." in text


def test_render_natural_language_default_remains_informative() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        summary="Find Python files",
        explanation="Translated natural-language request to deterministic command.",
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

    assert "Summary      : Find Python files" in text
    assert "Explanation  : Translated natural-language request to deterministic command." in text
    assert "Arguments" in text


def test_render_direct_command_non_verbose_keeps_safety_warnings() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command_family="rm",
        command="rm -rf tmp",
        summary="Run direct command: rm",
        explanation="Input already looks like a shell command.",
        risk_level=RiskLevel.DANGEROUS,
        needs_confirmation=True,
        notes=["Detected as a direct shell command; skipped the LLM planner."],
    )
    validation = ValidationResult(
        accepted=False,
        risk_level=RiskLevel.DANGEROUS,
        warnings=["Dangerous recursive deletion requested."],
        reasons=["Refusing to run recursive delete outside allowed roots."],
        rendered_command="rm -rf tmp",
        argv=["rm", "-rf", "tmp"],
    )

    text = render_preview(proposal, validation, direct_command=True)

    assert "Command: rm -rf tmp" in text
    assert "Risk: dangerous" in text
    assert "Dangerous recursive deletion requested." in text
    assert "Refusing to run recursive delete outside allowed roots." in text

from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel
from oterminus.policies import PolicyConfig
from oterminus.validator import Validator


def make_proposal(command: str, *, mode: ProposalMode = ProposalMode.RAW, command_family: str | None = None) -> Proposal:
    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=mode,
        command_family=command_family or command.split()[0],
        command=command,
        summary="test",
        explanation="test",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )


def test_accept_safe_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("ls -lh"))
    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE


def test_accept_cd_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("cd src"))
    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE


def test_reject_chained_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.DANGEROUS, allow_dangerous=True))
    result = validator.validate(make_proposal("ls && pwd"))
    assert result.accepted is False
    assert any("blocked command chaining" in reason for reason in result.reasons)


def test_reject_background_execution() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.DANGEROUS, allow_dangerous=True))
    result = validator.validate(make_proposal("sleep 1 &"))
    assert result.accepted is False
    assert any("blocked background execution" in reason for reason in result.reasons)


def test_policy_blocks_dangerous() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("rm -rf tmp"))
    assert result.accepted is False
    assert result.risk_level == RiskLevel.DANGEROUS


def test_reject_unsupported_flag_for_curated_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("cat -n README.md"))

    assert result.accepted is False
    assert any("Unsupported flag '-n' for command 'cat'." in reason for reason in result.reasons)


def test_reject_missing_required_operands() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("mv draft.txt"))

    assert result.accepted is False
    assert any("requires at least 2 operand" in reason for reason in result.reasons)


def test_accept_short_flag_clusters_for_curated_safe_commands() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("grep -Finr -m2 TODO src"))

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE


def test_accept_inline_value_flag_for_curated_safe_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("tail -c32 README.md"))

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE


def test_reject_open_url_target() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("open https://example.com"))

    assert result.accepted is False
    assert any("does not allow these operand targets" in reason for reason in result.reasons)


def test_allowed_roots_find_checks_only_search_roots() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("find /allowed -name '*.py'"))
    assert result.accepted is True


def test_allowed_roots_find_with_leading_option_still_checks_path_operands() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("find -L /etc -name '*.conf'"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_find_without_explicit_path_does_not_treat_predicate_arg_as_root() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("find -path '/etc/*'"))
    assert result.accepted is True


def test_allowed_roots_blocks_disallowed_path_operand() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("cat /etc/passwd"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_chmod_reference_equals_validates_target_path() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("chmod --reference=/allowed/ref /etc/shadow"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_grep_pattern_file_is_checked() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("grep -f /etc/patterns /allowed/input.txt"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_grep_pattern_file_stdin_sentinel_is_not_treated_as_path() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("grep -f - /allowed/input.txt"))
    assert result.accepted is True


def test_allowed_roots_cp_checks_both_source_and_destination() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("cp /allowed/in.txt /etc/out.txt"))

    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_allowed_roots_chmod_reference_path_is_checked() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    result = validator.validate(make_proposal("chmod --reference=/etc/ref /allowed/target.txt"))
    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_structured_only_proposal_is_previewable_but_not_executable() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="grep",
        arguments={
            "pattern": "TODO",
            "paths": ["src"],
            "ignore_case": True,
            "line_number": True,
            "fixed_strings": False,
            "recursive": True,
            "files_with_matches": False,
            "max_count": 2,
        },
        summary="find todo markers",
        explanation="structured grep plan",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE
    assert result.rendered_command == "grep -i -n -r -m 2 TODO src"
    assert result.argv == ["grep", "-i", "-n", "-r", "-m", "2", "TODO", "src"]


def test_reject_unknown_command_family() -> None:
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.RAW,
        command_family="python",
        command="python script.py",
        summary="unknown family",
        explanation="not allowlisted",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    validator = Validator(PolicyConfig(mode=RiskLevel.DANGEROUS, allow_dangerous=True))
    result = validator.validate(proposal)

    assert result.accepted is False
    assert any("Command family 'python' is not in the v1 allowlist." in reason for reason in result.reasons)


def test_structured_command_with_disallowed_root_is_rejected() -> None:
    validator = Validator(
        PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False, allowed_roots=["/allowed"])
    )
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="open",
        arguments={"path": "/etc/hosts", "reveal": False},
        summary="open hosts file",
        explanation="structured open",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is False
    assert any("Paths outside allowed roots" in reason for reason in result.reasons)


def test_accept_experimental_raw_command_with_warning() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("stat -f %z README.md", mode=ProposalMode.EXPERIMENTAL))

    assert result.accepted is True
    assert result.risk_level == RiskLevel.SAFE
    assert any(
        "Experimental mode stays outside deterministic structured rendering" in warning
        for warning in result.warnings
    )


def test_structured_command_ignores_legacy_raw_command() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        command="find src -name '*.py'",
        summary="find python files",
        explanation="structured find stays authoritative",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is True
    assert result.rendered_command == "find . -name '*.py'"
    assert any(
        "Structured mode ignores the deprecated raw command field" in warning
        for warning in result.warnings
    )
    assert any(
        "Legacy raw command differs from deterministic structured rendering and was ignored." in warning
        for warning in result.warnings
    )


def test_reject_experimental_when_structured_rendering_is_available() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(
        make_proposal("find . -name '*.py'", mode=ProposalMode.EXPERIMENTAL)
    )

    assert result.accepted is False
    assert any(
        "Experimental mode is not allowed when deterministic structured rendering is available."
        in reason
        for reason in result.reasons
    )

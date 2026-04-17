from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel
from oterminus.policies import PolicyConfig
from oterminus.validator import Validator


def make_proposal(command: str) -> Proposal:
    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.RAW,
        command_family=command.split()[0],
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
    assert any("blocked shell operators" in reason for reason in result.reasons)


def test_policy_blocks_dangerous() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    result = validator.validate(make_proposal("rm -rf tmp"))
    assert result.accepted is False
    assert result.risk_level == RiskLevel.DANGEROUS


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
        command_family="find",
        arguments={"root": ".", "name": "*.py"},
        summary="find files",
        explanation="structured plan",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is False
    assert result.risk_level == RiskLevel.SAFE
    assert any("no executable raw command" in reason for reason in result.reasons)


def test_reject_unknown_command_family() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.DANGEROUS, allow_dangerous=True))
    proposal = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="python",
        summary="unknown family",
        explanation="not allowlisted",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    result = validator.validate(proposal)

    assert result.accepted is False
    assert any("Command family 'python' is not in the v1 allowlist." in reason for reason in result.reasons)

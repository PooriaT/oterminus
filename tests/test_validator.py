from oterminus.models import ActionType, Proposal, RiskLevel
from oterminus.policies import PolicyConfig
from oterminus.validator import Validator


def make_proposal(command: str) -> Proposal:
    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
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

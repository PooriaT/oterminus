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

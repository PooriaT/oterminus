from unittest.mock import Mock

import subprocess

from oterminus.cli import parse_args
from oterminus.models import ActionType, Proposal, RiskLevel, ValidationResult


def test_parse_args_one_shot() -> None:
    args = parse_args(["show", "files"])
    assert args.request == ["show", "files"]


def test_handle_request_cancel(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        command="ls -lh",
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(accepted=True, risk_level=RiskLevel.SAFE)
    executor = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    code = handle_request("show files", planner, validator, executor)
    assert code == 0
    executor.run.assert_not_called()


def test_handle_request_timeout(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        command="find . -name '*.py'",
        summary="find files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(accepted=True, risk_level=RiskLevel.SAFE)
    executor = Mock()
    executor.timeout_seconds = 1
    executor.run.side_effect = subprocess.TimeoutExpired(cmd=["find"], timeout=1)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request("find files", planner, validator, executor)
    assert code == 124

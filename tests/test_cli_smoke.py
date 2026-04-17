from unittest.mock import Mock

import subprocess

from oterminus.cli import ask_confirmation, parse_args
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel, ValidationResult
from oterminus.policies import ConfirmationLevel


def test_parse_args_one_shot() -> None:
    args = parse_args(["show", "files"])
    assert args.request == ["show", "files"]


def test_handle_request_cancel(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
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
        command="ls -lh",
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls -lh",
        argv=["ls", "-lh"],
    )
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
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        command="find . -name '*.py'",
        summary="find files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )
    executor = Mock()
    executor.timeout_seconds = 1
    executor.run.side_effect = subprocess.TimeoutExpired(cmd=["find"], timeout=1)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request("find files", planner, validator, executor)
    assert code == 124


def test_handle_request_direct_command_skips_planner(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="cd /tmp",
        argv=["cd", "/tmp"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = "/tmp\n"
    executor.run.return_value.stderr = ""
    monkeypatch.setattr("builtins.input", lambda _: "EXECUTE EXPERIMENTAL")

    code = handle_request("cd /tmp", planner, validator, executor)

    assert code == 0
    planner.plan.assert_not_called()
    executor.run.assert_called_once_with(["cd", "/tmp"], display_command="cd /tmp")


def test_handle_request_natural_language_uses_planner(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = ""
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request("show files in this directory", planner, validator, executor)

    assert code == 0
    planner.plan.assert_called_once_with("show files in this directory")
    executor.run.assert_called_once_with(
        ["find", ".", "-name", "*.py"],
        display_command="find . -name '*.py'",
    )


def test_ask_confirmation_requires_experimental_phrase(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "EXECUTE")
    assert ask_confirmation(ConfirmationLevel.VERY_STRONG) is False

    monkeypatch.setattr("builtins.input", lambda _: "EXECUTE EXPERIMENTAL")
    assert ask_confirmation(ConfirmationLevel.VERY_STRONG) is True


def test_handle_request_experimental_requires_very_strong_confirmation(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command_family="cat",
        command="cat README.md",
        summary="show readme",
        explanation="experimental fallback",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=["experimental"],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        warnings=["experimental warning"],
        rendered_command="cat README.md",
        argv=["cat", "README.md"],
    )
    executor = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "EXECUTE")

    code = handle_request("show the readme", planner, validator, executor)

    assert code == 0
    executor.run.assert_not_called()

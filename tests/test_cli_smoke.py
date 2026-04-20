from unittest.mock import Mock

import subprocess

from oterminus.cli import ask_confirmation, parse_args
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel, ValidationResult
from oterminus.ollama_client import parse_ollama_list_output
from oterminus.policies import ConfirmationLevel


def test_parse_args_one_shot() -> None:
    args = parse_args(["show", "files"])
    assert args.request == ["show", "files"]


def test_parse_ollama_list_output_returns_model_names() -> None:
    output = (
        "NAME                ID              SIZE      MODIFIED\n"
        "gemma3:latest       abc123          3.3 GB    2 days ago\n"
        "llama3.2:latest     def456          2.0 GB    1 day ago\n"
    )

    assert parse_ollama_list_output(output) == ["gemma3:latest", "llama3.2:latest"]


def test_main_repl_startup_validates_once(monkeypatch) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", Mock())
    setup_check = Mock(return_value="gemma3:latest")
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", setup_check)
    monkeypatch.setattr("oterminus.cli.repl", lambda repl_planner, repl_validator, repl_executor: 0)

    code = main(["--verbose"])

    assert code == 0
    setup_check.assert_called_once()


def test_main_request_exits_when_startup_setup_fails(monkeypatch, capsys) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", Mock())

    def fail_setup() -> str:
        from oterminus.setup import SetupError

        raise SetupError("Ollama is installed but not running. Please start it using `ollama serve`.")

    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", fail_setup)

    code = main(["--verbose", "show", "files"])

    assert code == 2
    assert "Ollama is installed but not running." in capsys.readouterr().out


def test_main_uses_selected_model(monkeypatch) -> None:
    from oterminus.cli import main

    planner_client = Mock()
    planner = Mock()
    validator = Mock()
    executor = Mock()
    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 45

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", lambda: "llama3.2:latest")
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", planner_client)
    monkeypatch.setattr("oterminus.cli.Planner", lambda client: planner)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    monkeypatch.setattr(
        "oterminus.cli.handle_request",
        lambda request, planner_factory, req_validator, req_executor: (
            planner_factory().plan(request),
            17,
        )[1],
    )

    code = main(["--verbose", "show", "files"])

    assert code == 17
    planner_client.assert_called_once_with(model="llama3.2:latest")
    assert planner_client.call_args.kwargs == {"model": "llama3.2:latest"}


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

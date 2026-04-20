from unittest.mock import Mock

import subprocess

from oterminus.cli import ask_confirmation, choose_model, parse_args, resolve_model_name
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel, ValidationResult
from oterminus.ollama_client import OllamaClientError, parse_ollama_list_output
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


def test_choose_model_retries_until_valid_selection(monkeypatch, capsys) -> None:
    answers = iter(["0", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    selected = choose_model(["gemma3:latest", "llama3.2:latest"])

    assert selected == "llama3.2:latest"
    output = capsys.readouterr().out
    assert "Available Ollama models:" in output
    assert "1. gemma3:latest" in output
    assert "2. llama3.2:latest" in output
    assert "Please enter a number between 1 and 2." in output


def test_resolve_model_name_returns_none_when_no_models(monkeypatch) -> None:
    monkeypatch.setattr("oterminus.cli.list_installed_models", lambda: [])

    assert resolve_model_name() is None


def test_resolve_model_name_propagates_ollama_errors(monkeypatch) -> None:
    def raise_error() -> list[str]:
        raise OllamaClientError("boom")

    monkeypatch.setattr("oterminus.cli.list_installed_models", raise_error)

    try:
        resolve_model_name()
    except OllamaClientError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("resolve_model_name should propagate OllamaClientError")


def test_main_exits_when_no_models_are_installed(monkeypatch, capsys) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.is_ollama_installed", lambda: True)
    monkeypatch.setattr("oterminus.cli.load_config", Mock())
    monkeypatch.setattr("oterminus.cli.resolve_model_name", lambda: None)

    code = main(["--verbose"])

    assert code == 1
    assert "No Ollama models are installed on this machine." in capsys.readouterr().out


def test_main_exits_when_ollama_is_not_installed(monkeypatch, capsys) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.is_ollama_installed", lambda: False)

    code = main(["--verbose"])

    assert code == 1
    assert "Ollama is not installed on this machine." in capsys.readouterr().out


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
    monkeypatch.setattr("oterminus.cli.is_ollama_installed", lambda: True)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.resolve_model_name", lambda: "llama3.2:latest")
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", planner_client)
    monkeypatch.setattr("oterminus.cli.Planner", lambda client: planner)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    monkeypatch.setattr("oterminus.cli.repl", lambda repl_planner, repl_validator, repl_executor: 17)

    code = main(["--verbose"])

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

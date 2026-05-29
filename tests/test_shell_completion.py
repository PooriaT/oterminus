from __future__ import annotations

from unittest.mock import Mock

import pytest

from oterminus.shell_completion import render_shell_completion, supported_shells


def test_parse_args_completion_command() -> None:
    from oterminus.cli import parse_args

    args = parse_args(["completion", "zsh"])

    assert args.cli_mode == "completion"
    assert args.completion_shell == "zsh"


@pytest.mark.parametrize("shell", supported_shells())
def test_render_shell_completion_returns_static_script(shell: str) -> None:
    script = render_shell_completion(shell)

    assert script
    assert "oterminus" in script
    assert "completion" in script
    assert "zsh" in script
    assert "bash" in script
    assert "fish" in script


def test_render_shell_completion_rejects_unsupported_shell() -> None:
    with pytest.raises(ValueError, match="Unsupported shell"):
        render_shell_completion("powershell")


@pytest.mark.parametrize(
    ("shell", "expected"),
    (
        ("zsh", "#compdef oterminus"),
        ("bash", "complete -F _oterminus_completion oterminus"),
        ("fish", "complete -c oterminus"),
    ),
)
def test_main_completion_prints_script_and_exits_zero(
    monkeypatch, capsys, shell: str, expected: str
) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", Mock(side_effect=AssertionError("no config")))
    monkeypatch.setattr(
        "oterminus.cli.run_doctor_cli", Mock(side_effect=AssertionError("no doctor"))
    )
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("no startup checks")),
    )
    monkeypatch.setattr("oterminus.cli.repl", Mock(side_effect=AssertionError("no REPL")))
    monkeypatch.setattr("oterminus.cli.Executor", Mock(side_effect=AssertionError("no executor")))
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr(
        "oterminus.cli.OllamaPlannerClient",
        Mock(side_effect=AssertionError("no Ollama client")),
    )
    monkeypatch.setattr(
        "oterminus.cli.handle_request", Mock(side_effect=AssertionError("no request handling"))
    )
    monkeypatch.setattr(
        "oterminus.cli.AuditLogger", Mock(side_effect=AssertionError("no audit logger"))
    )
    monkeypatch.setattr(
        "oterminus.cli.PersistentHistoryStore",
        Mock(side_effect=AssertionError("no history store")),
    )

    code = main(["completion", shell])

    assert code == 0
    output = capsys.readouterr().out
    assert expected in output
    assert "Ollama" not in output


@pytest.mark.parametrize("argv", (["completion"], ["completion", "powershell"]))
def test_main_completion_invalid_invocations_exit_nonzero(argv, capsys) -> None:
    from oterminus.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2
    assert "completion requires one shell" in capsys.readouterr().err

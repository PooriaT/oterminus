from __future__ import annotations

from unittest.mock import Mock

import pytest

from oterminus.config_settings import SUPPORTED_MUTABLE_CONFIG_KEYS
from oterminus.shell_completion import render_shell_completion, supported_shells

EXPECTED_FLAGS = ("--dry-run", "--explain", "--version", "--verbose", "--help")
EXPECTED_COMMANDS = ("doctor", "version", "completion", "config")
EXPECTED_CONFIG_COMMANDS = ("path", "show", "init", "validate", "edit", "get", "set")
EXPECTED_CONFIG_INIT_OPTIONS = ("--defaults", "--force")
EXPECTED_SHELLS = ("zsh", "bash", "fish")


def test_parse_args_completion_command() -> None:
    from oterminus.cli import parse_args

    args = parse_args(["completion", "zsh"])

    assert args.cli_mode == "completion"
    assert args.completion_shell == "zsh"


@pytest.mark.parametrize(
    "argv",
    (
        ["completion", "of", "git", "status"],
        ["completion", "script", "for", "bash"],
    ),
)
def test_parse_args_completion_prefixed_natural_language_stays_request(argv: list[str]) -> None:
    from oterminus.cli import parse_args

    args = parse_args(argv)

    assert args.request == argv
    assert args.cli_mode == "request"
    assert args.completion_shell is None


@pytest.mark.parametrize("shell", supported_shells())
def test_render_shell_completion_returns_static_script(shell: str) -> None:
    script = render_shell_completion(shell)

    assert script
    assert "oterminus" in script
    assert "completion" in script
    assert "zsh" in script
    assert "bash" in script
    assert "fish" in script


@pytest.mark.parametrize(
    ("shell", "markers"),
    (
        (
            "zsh",
            (
                "#compdef oterminus",
                "_oterminus()",
                "_arguments -C",
                "_describe -t commands",
                "_describe -t shells",
            ),
        ),
        (
            "bash",
            (
                "# bash completion for oterminus",
                "_oterminus_completion()",
                "COMPREPLY",
                "compgen -W",
                "complete -F _oterminus_completion oterminus",
            ),
        ),
        (
            "fish",
            (
                "# fish completion for oterminus",
                "complete -c oterminus",
                "__fish_seen_subcommand_from completion",
            ),
        ),
    ),
)
def test_render_shell_completion_contains_shell_specific_markers(
    shell: str, markers: tuple[str, ...]
) -> None:
    script = render_shell_completion(shell)

    for marker in markers:
        assert marker in script


@pytest.mark.parametrize("shell", supported_shells())
def test_render_shell_completion_includes_top_level_commands(shell: str) -> None:
    script = render_shell_completion(shell)

    for command in EXPECTED_COMMANDS:
        assert command in script


@pytest.mark.parametrize("shell", supported_shells())
def test_render_shell_completion_includes_config_subcommands(shell: str) -> None:
    script = render_shell_completion(shell)

    for command in EXPECTED_CONFIG_COMMANDS:
        assert command in script


@pytest.mark.parametrize("shell", supported_shells())
def test_render_shell_completion_includes_supported_config_keys_only(shell: str) -> None:
    script = render_shell_completion(shell)

    for key in SUPPORTED_MUTABLE_CONFIG_KEYS:
        assert key in script
    assert "allow_dangerous" not in script
    assert "policy.allow_dangerous" not in script
    assert "schema_version" not in script


@pytest.mark.parametrize("shell", ("zsh", "bash"))
def test_render_shell_completion_includes_config_init_options_for_zsh_and_bash(
    shell: str,
) -> None:
    script = render_shell_completion(shell)

    for option in EXPECTED_CONFIG_INIT_OPTIONS:
        assert option in script


def test_render_shell_completion_includes_config_init_options_for_fish() -> None:
    script = render_shell_completion("fish")

    for option in EXPECTED_CONFIG_INIT_OPTIONS:
        assert f"-l {option.removeprefix('--')}" in script


@pytest.mark.parametrize("shell", ("zsh", "bash"))
def test_render_shell_completion_includes_long_flags_for_zsh_and_bash(shell: str) -> None:
    script = render_shell_completion(shell)

    for flag in EXPECTED_FLAGS:
        assert flag in script


def test_render_shell_completion_includes_long_flags_for_fish() -> None:
    script = render_shell_completion("fish")

    for flag in EXPECTED_FLAGS:
        assert f"-l {flag.removeprefix('--')}" in script


@pytest.mark.parametrize(
    ("shell", "completion_context"),
    (
        ("zsh", "if [[ $words[2] == completion ]]"),
        ("bash", 'if [[ $prev == "completion" ]]'),
        ("fish", "__fish_seen_subcommand_from completion"),
    ),
)
def test_render_shell_completion_includes_shell_choices_after_completion(
    shell: str, completion_context: str
) -> None:
    script = render_shell_completion(shell)

    assert completion_context in script
    for completion_shell in EXPECTED_SHELLS:
        assert completion_shell in script


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
    monkeypatch, tmp_path, capsys, shell: str, expected: str
) -> None:
    from oterminus.cli import main

    config_path = tmp_path / "config" / "config.json"
    audit_path = tmp_path / "audit" / "audit.jsonl"
    history_path = tmp_path / "history" / "history.jsonl"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("OTERMINUS_AUDIT_LOG_PATH", str(audit_path))
    monkeypatch.setenv("OTERMINUS_HISTORY_PATH", str(history_path))
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
    ollama_client = Mock(side_effect=AssertionError("no Ollama client"))
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", ollama_client)
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
    assert not ollama_client.called
    assert not config_path.exists()
    assert not audit_path.exists()
    assert not history_path.exists()


@pytest.mark.parametrize("argv", (["completion"], ["completion", "powershell"]))
def test_main_completion_invalid_invocations_exit_nonzero(argv, capsys) -> None:
    from oterminus.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2
    assert "completion requires one shell" in capsys.readouterr().err

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from oterminus.config import (
    AppConfig,
    ConfigError,
    ConfigValueSource,
    ResolvedConfig,
)
from oterminus.models_cli import run_models_cli
from oterminus.setup import OllamaModelStatus


def _resolved(model: str | None) -> ResolvedConfig:
    return ResolvedConfig(
        app_config=AppConfig(model=model),
        sources={"model": ConfigValueSource.USER_CONFIG if model else ConfigValueSource.DEFAULT},
        user_config=None,
        config_path=Path("/tmp/oterminus-config.json"),
        config_exists=model is not None,
    )


def test_healthy_state_lists_models_and_marks_selection(capsys) -> None:
    status = OllamaModelStatus(
        cli_installed=True,
        service_available=True,
        models=("gemma4:latest", "llama3.2:latest"),
    )

    code = run_models_cli(
        [], status_provider=lambda: status, config_resolver=lambda: _resolved("gemma4:latest")
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "CLI: installed" in output
    assert "Service: reachable" in output
    assert "Installed models: 2" in output
    assert "Model: gemma4:latest" in output
    assert "Source: user_config" in output
    assert "Installed: yes" in output
    assert "* gemma4:latest  selected" in output
    assert "llama3.2:latest" in output


def test_no_selected_model_reports_selection_guidance(capsys) -> None:
    status = OllamaModelStatus(True, True, ("gemma4:latest",))

    code = run_models_cli(
        [], status_provider=lambda: status, config_resolver=lambda: _resolved(None)
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Model: not configured" in output
    assert "Source: default" in output
    assert "Installed: not applicable" in output
    assert "oterminus config set model <model-name>" in output


def test_selected_model_not_installed_exits_one(capsys) -> None:
    status = OllamaModelStatus(True, True, ("llama3.2:latest",))

    code = run_models_cli(
        [], status_provider=lambda: status, config_resolver=lambda: _resolved("gemma4:latest")
    )

    assert code == 1
    output = capsys.readouterr().out
    assert "Installed: no" in output
    assert "ollama pull gemma4:latest" in output
    assert "* llama3.2:latest" not in output


def test_no_installed_models_is_successful_report(capsys) -> None:
    status = OllamaModelStatus(True, True)

    code = run_models_cli(
        [], status_provider=lambda: status, config_resolver=lambda: _resolved(None)
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Installed models: 0" in output
    assert "Models:\n  (none)" in output
    assert "ollama pull <model>" in output


def test_missing_ollama_cli_exits_one(capsys) -> None:
    status = OllamaModelStatus(False, False, error="not found")

    code = run_models_cli(
        [], status_provider=lambda: status, config_resolver=lambda: _resolved("gemma4:latest")
    )

    assert code == 1
    output = capsys.readouterr().out
    assert "CLI: missing" in output
    assert "Service: unavailable" in output
    assert "Installed models: unavailable" in output
    assert "Installed: unknown" in output
    assert "Install Ollama" in output


def test_unavailable_ollama_service_exits_one(capsys) -> None:
    status = OllamaModelStatus(True, False, error="connection refused")

    code = run_models_cli(
        [], status_provider=lambda: status, config_resolver=lambda: _resolved("gemma4:latest")
    )

    assert code == 1
    output = capsys.readouterr().out
    assert "CLI: installed" in output
    assert "Service: unavailable" in output
    assert "ollama serve" in output


def test_config_error_exits_two_without_checking_ollama(capsys) -> None:
    status_provider = Mock(side_effect=AssertionError("status must not be queried"))

    code = run_models_cli(
        [],
        status_provider=status_provider,
        config_resolver=Mock(side_effect=ConfigError(Path("bad.json"), "invalid JSON")),
    )

    assert code == 2
    assert "Configuration error:" in capsys.readouterr().out
    status_provider.assert_not_called()


@pytest.mark.parametrize("argv", ([], ["list"]))
def test_bare_and_explicit_list_have_equivalent_output(argv, capsys) -> None:
    status = OllamaModelStatus(True, True, ("gemma4:latest",))

    code = run_models_cli(
        argv,
        status_provider=lambda: status,
        config_resolver=lambda: _resolved("gemma4:latest"),
    )

    assert code == 0
    assert "* gemma4:latest  selected" in capsys.readouterr().out


def test_models_help_does_not_query_config_or_ollama(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_models_cli(
            ["--help"],
            status_provider=Mock(side_effect=AssertionError("no status")),
            config_resolver=Mock(side_effect=AssertionError("no config")),
        )

    assert exc_info.value.code == 0
    assert "oterminus models" in capsys.readouterr().out


def test_top_level_routing_bypasses_request_lifecycle(monkeypatch) -> None:
    from oterminus.cli import main

    models_runner = Mock(return_value=0)
    monkeypatch.setattr("oterminus.cli.configure_logging", Mock())
    monkeypatch.setattr("oterminus.cli.run_models_cli", models_runner)
    monkeypatch.setattr("oterminus.cli.load_config", Mock(side_effect=AssertionError("no config")))
    monkeypatch.setattr("oterminus.cli.repl", Mock(side_effect=AssertionError("no REPL")))
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr("oterminus.cli.Executor", Mock(side_effect=AssertionError("no executor")))
    monkeypatch.setattr("oterminus.cli.AuditLogger", Mock(side_effect=AssertionError("no audit")))
    monkeypatch.setattr(
        "oterminus.cli.PersistentHistoryStore", Mock(side_effect=AssertionError("no history"))
    )
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready", Mock(side_effect=AssertionError("no startup"))
    )

    assert main(["models", "list"]) == 0
    models_runner.assert_called_once_with(["list"])


def test_top_level_models_help_bypasses_request_lifecycle(monkeypatch, capsys) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", Mock())
    monkeypatch.setattr("oterminus.cli.load_config", Mock(side_effect=AssertionError("no config")))
    monkeypatch.setattr("oterminus.cli.repl", Mock(side_effect=AssertionError("no REPL")))
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr("oterminus.cli.Executor", Mock(side_effect=AssertionError("no executor")))
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready", Mock(side_effect=AssertionError("no startup"))
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["models", "--help"])

    assert exc_info.value.code == 0
    assert "oterminus models" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv", (["--dry-run", "models"], ["--explain", "models"], ["models", "--dry-run"])
)
def test_models_rejects_request_run_modes(argv) -> None:
    from oterminus.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2

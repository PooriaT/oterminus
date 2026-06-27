from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from oterminus.config import AppConfig
from oterminus.policies import PolicyConfig


def _release_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        policy=PolicyConfig(),
        audit_enabled=False,
        audit_log_path=tmp_path / "audit.jsonl",
        history_enabled=False,
        history_path=tmp_path / "history.jsonl",
    )


def _install_cli_release_dependencies(monkeypatch, config: AppConfig) -> Mock:
    from oterminus.validator import Validator

    executor = Mock()
    executor.timeout_seconds = config.timeout_seconds
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: Validator(policy))
    monkeypatch.setattr(
        "oterminus.cli.Executor",
        lambda timeout_seconds, max_output_chars=20000: executor,
    )
    return executor


def test_release_smoke_version_flag_uses_metadata_and_exits_before_runtime_setup(
    monkeypatch, capsys
) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.version.metadata.version", lambda _name: "1.2.3")
    monkeypatch.setattr("oterminus.cli.load_config", Mock(side_effect=AssertionError("no config")))
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("no Ollama startup check")),
    )

    assert main(["--version"]) == 0
    assert capsys.readouterr().out == "oterminus 1.2.3\n"


def test_release_smoke_version_command_uses_metadata_and_exits_before_runtime_setup(
    monkeypatch, capsys
) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.version.metadata.version", lambda _name: "1.2.3")
    monkeypatch.setattr("oterminus.cli.load_config", Mock(side_effect=AssertionError("no config")))
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("no Ollama startup check")),
    )

    assert main(["version"]) == 0
    assert capsys.readouterr().out == "oterminus 1.2.3\n"


def test_release_smoke_doctor_runs_without_planner_or_executor(monkeypatch) -> None:
    from oterminus.cli import main

    doctor_cli = Mock(return_value=2)
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.run_doctor_cli", doctor_cli)
    monkeypatch.setattr("oterminus.cli.load_config", Mock(side_effect=AssertionError("no config")))
    monkeypatch.setattr("oterminus.cli.Executor", Mock(side_effect=AssertionError("no executor")))
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr(
        "oterminus.cli.OllamaPlannerClient",
        Mock(side_effect=AssertionError("no planner client")),
    )

    assert main(["doctor"]) == 2
    doctor_cli.assert_called_once_with()


@pytest.mark.parametrize("flag", ("--dry-run", "--explain"))
def test_release_smoke_direct_inspection_modes_skip_startup_planner_and_execution(
    monkeypatch, tmp_path: Path, flag: str
) -> None:
    from oterminus.cli import main

    executor = _install_cli_release_dependencies(monkeypatch, _release_config(tmp_path))
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

    assert main([flag, "pwd"]) == 0
    executor.run.assert_not_called()


def test_release_smoke_deterministic_shortcut_request_skips_ollama_and_execution(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    executor = _install_cli_release_dependencies(monkeypatch, _release_config(tmp_path))
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("deterministic shortcut should not need Ollama")),
    )
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

    assert main(["--dry-run", "show", "current", "directory"]) == 0
    output = capsys.readouterr().out
    assert "pwd" in output
    assert "Dry-run mode: execution skipped" in output
    executor.run.assert_not_called()


def test_release_smoke_ambiguity_block_skips_planner_validation_and_execution(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _release_config(tmp_path)
    executor = Mock()
    validator = Mock()
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", Mock(return_value=validator))
    monkeypatch.setattr(
        "oterminus.cli.Executor",
        lambda timeout_seconds, max_output_chars=20000: executor,
    )
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("ambiguous request should not need Ollama")),
    )
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))

    assert main(["fix", "this", "project"]) == 0
    assert "This request is ambiguous." in capsys.readouterr().out
    validator.validate.assert_not_called()
    executor.run.assert_not_called()

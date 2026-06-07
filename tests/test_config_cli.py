import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from oterminus.config import CURRENT_USER_CONFIG_SCHEMA_VERSION, read_user_config
from oterminus.config_cli import run_config_cli
from oterminus.setup import OllamaModelStatus


@pytest.fixture(autouse=True)
def _isolate_dotenv_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


def test_config_path_prints_active_path_without_creating_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "cfg" / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["path"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == f"{config_path}\n"
    assert captured.err == ""
    assert not config_path.exists()
    assert "\x1b[" not in captured.out


def test_config_path_uses_dotenv_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("OTERMINUS_CONFIG_PATH", raising=False)
    config_path = tmp_path / "dotenv-config.json"
    (tmp_path / ".env").write_text(f"OTERMINUS_CONFIG_PATH={config_path}\n", encoding="utf-8")

    code = run_config_cli(["path"])

    assert code == 0
    assert capsys.readouterr().out == f"{config_path}\n"
    assert not config_path.exists()


def test_config_init_defaults_creates_safe_valid_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["init", "--defaults"])

    assert code == 0
    assert f"Created config: {config_path}" in capsys.readouterr().out
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == CURRENT_USER_CONFIG_SCHEMA_VERSION
    assert payload["onboarding_completed"] is True
    assert payload["command_profile"] == "safe"
    assert payload["policy_mode"] == "write"
    assert payload["auto_execute_safe"] is False
    assert payload["audit_enabled"] is True
    assert payload["audit_redact"] is True
    assert payload["history_enabled"] is False
    assert payload["history_redact"] is True
    assert payload["explain_failures"] is False
    assert payload["model"] is None
    assert "allow_dangerous" not in payload
    assert read_user_config().config is not None


def test_config_init_interactive_runs_wizard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(
        "oterminus.onboarding.get_ollama_model_status",
        lambda: OllamaModelStatus(True, True, ("gemma3:latest",)),
    )
    answers = iter(["", "", "", "", "", "", "1", ""])

    code = run_config_cli(
        ["init"],
        input_fn=lambda _: next(answers),
        stdin_isatty=lambda: True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "Configuration summary" in output
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["command_profile"] == "safe"
    assert payload["model"] == "gemma3:latest"
    assert payload["onboarding_completed"] is True


def test_config_init_non_tty_requires_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1, "model": "gemma4"}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["init"])

    assert code == 1
    output = capsys.readouterr().out
    assert "requires a TTY" in output
    assert "--defaults" in output
    assert json.loads(config_path.read_text(encoding="utf-8"))["model"] == "gemma4"


def test_config_init_defaults_preserves_existing_valid_file_without_force(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1, "model": "gemma4"}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["init", "--defaults"])

    assert code == 1
    assert "not overwritten" in capsys.readouterr().out
    assert json.loads(config_path.read_text(encoding="utf-8"))["model"] == "gemma4"


def test_config_init_force_replaces_existing_valid_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1, "model": "gemma4"}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["init", "--defaults", "--force"])

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["model"] is None
    assert payload["command_profile"] == "safe"


def test_config_init_force_refuses_invalid_existing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    original = '{"audit_log_path": 123}'
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["init", "--defaults", "--force"])

    output = capsys.readouterr().out
    assert code == 2
    assert "Existing config is invalid" in output
    assert config_path.read_text(encoding="utf-8") == original


def test_config_init_defaults_reports_write_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    def fail_save(*_: object, **__: object) -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("oterminus.config_cli.save_user_config", fail_save)

    code = run_config_cli(["init", "--defaults"])

    output = capsys.readouterr().out
    assert code == 2
    assert "Config init failed: Unable to write safe default config: permission denied" in output
    assert f"Path: {config_path}" in output
    assert "Traceback" not in output


def test_config_validate_valid_missing_and_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    assert run_config_cli(["validate"]) == 1
    assert "config init" in capsys.readouterr().out

    config_path.write_text('{"schema_version": 1}\n', encoding="utf-8")
    assert run_config_cli(["validate"]) == 0
    assert "Status: valid" in capsys.readouterr().out

    config_path.write_text('{"schema_version": 999}\n', encoding="utf-8")
    assert run_config_cli(["validate"]) == 2
    output = capsys.readouterr().out
    assert "unsupported_schema" in output
    assert "schema_version 999" in output


def test_config_show_reports_sources_and_omits_unrelated_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"schema_version": 1, "timeout_seconds": 42, "command_profile": "developer"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("OTERMINUS_AUDIT_ENABLED", "false")
    monkeypatch.setenv("OTERMINUS_COMMAND_PROFILE", "power")
    monkeypatch.setenv("SOME_SECRET_TOKEN", "do-not-print")
    (tmp_path / ".env").write_text(
        "OTERMINUS_HISTORY_ENABLED=true\nOTERMINUS_DISABLED_COMMAND_PACKS=macos\n",
        encoding="utf-8",
    )

    code = run_config_cli(["show"])

    output = capsys.readouterr().out
    assert code == 0
    assert f"Active config path: {config_path}" in output
    assert "timeout_seconds: 42 [source: user config]" in output
    assert "audit_enabled: false [source: environment]" in output
    assert "history_enabled: true [source: .env]" in output
    assert "command_profile: power [source: environment]" in output
    assert "disabled_command_packs: [macos] [source: .env]" in output
    assert "policy.allow_dangerous" in output
    assert "environment-only" in output
    assert "policy.disabled_command_packs" in output
    assert "derived union" in output
    assert "OTERMINUS_CONFIG_PATH" in output
    assert "external path selector" in output
    assert "SOME_SECRET_TOKEN" not in output
    assert "do-not-print" not in output
    assert "\x1b[" not in output


def test_config_edit_uses_visual_before_editor_and_preserves_args(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("VISUAL", "code --wait")
    monkeypatch.setenv("EDITOR", "vim")
    calls: list[tuple[list[str], bool, bool]] = []

    def fake_run(argv: list[str], *, shell: bool, check: bool) -> subprocess.CompletedProcess[str]:
        calls.append((argv, shell, check))
        return subprocess.CompletedProcess(argv, 0)

    code = run_config_cli(["edit"], run_editor=fake_run)

    assert code == 0
    assert calls == [(["code", "--wait", str(config_path)], False, False)]
    assert "Config is valid" in capsys.readouterr().out


def test_config_edit_missing_editor_creates_defaults_and_prints_manual_guidance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)

    code = run_config_cli(["edit"], run_editor=Mock(side_effect=AssertionError("no editor")))

    output = capsys.readouterr().out
    assert code == 1
    assert config_path.exists()
    assert "No editor configured" in output
    assert str(config_path) in output


def test_config_edit_auto_create_reports_write_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    def fail_save(*_: object, **__: object) -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("oterminus.config_cli.save_user_config", fail_save)

    code = run_config_cli(["edit"], run_editor=Mock(side_effect=AssertionError("no editor")))

    output = capsys.readouterr().out
    assert code == 2
    assert (
        "Config edit failed during initialization: "
        "Unable to write safe default config: permission denied"
    ) in output
    assert f"Path: {config_path}" in output
    assert "Traceback" not in output


def test_config_edit_preserves_invalid_edits_after_successful_editor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("EDITOR", "edit")

    def fake_run(argv: list[str], *, shell: bool, check: bool) -> subprocess.CompletedProcess[str]:
        config_path.write_text('{"audit_log_path": 123}', encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0)

    code = run_config_cli(["edit"], run_editor=fake_run)

    assert code == 2
    assert config_path.read_text(encoding="utf-8") == '{"audit_log_path": 123}'
    assert "Invalid edits were preserved" in capsys.readouterr().out


def test_config_edit_nonzero_editor_exit_does_not_validate_or_modify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    original = '{"schema_version": 1}\n'
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("EDITOR", "edit")

    def fake_run(argv: list[str], *, shell: bool, check: bool) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 17)

    code = run_config_cli(["edit"], run_editor=fake_run)

    assert code == 17
    assert config_path.read_text(encoding="utf-8") == original
    assert "status 17" in capsys.readouterr().out


@pytest.mark.parametrize("argv", (["nope"], ["init", "--json"], ["show", "--force"]))
def test_config_unknown_subcommand_or_invalid_options_exit_nonzero(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_config_cli(argv)

    assert exc_info.value.code == 2

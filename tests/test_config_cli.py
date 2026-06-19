import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from oterminus.config import CURRENT_USER_CONFIG_SCHEMA_VERSION, read_user_config
from oterminus.config_settings import SUPPORTED_MUTABLE_CONFIG_KEYS
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
    assert payload["color_mode"] == "auto"
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
    assert payload["color_mode"] == "auto"
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
    assert "color_mode: auto [source: default]" in output
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


def test_config_get_reads_default_when_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)

    code = run_config_cli(["get", "color_mode"])

    output = capsys.readouterr().out
    assert code == 0
    assert output == "color_mode=auto\n"
    assert "\x1b[" not in output


def test_config_get_reads_user_config_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"schema_version": 1, "auto_execute_safe": True, "model": "gemma4"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_AUTO_EXECUTE_SAFE", raising=False)

    assert run_config_cli(["get", "auto_execute_safe"]) == 0
    assert capsys.readouterr().out == "auto_execute_safe=true\n"
    assert run_config_cli(["get", "model"]) == 0
    assert capsys.readouterr().out == "model=gemma4\n"


def test_config_get_reflects_dotenv_and_environment_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"schema_version": 1, "auto_execute_safe": False}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_AUTO_EXECUTE_SAFE", raising=False)
    (tmp_path / ".env").write_text("OTERMINUS_AUTO_EXECUTE_SAFE=true\n", encoding="utf-8")

    assert run_config_cli(["get", "auto_execute_safe"]) == 0
    assert capsys.readouterr().out == "auto_execute_safe=true\n"

    monkeypatch.setenv("OTERMINUS_AUTO_EXECUTE_SAFE", "false")
    assert run_config_cli(["get", "auto_execute_safe"]) == 0
    assert capsys.readouterr().out == "auto_execute_safe=false\n"


def test_config_get_prints_empty_model_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "missing.json"))

    assert run_config_cli(["get", "model"]) == 0

    assert capsys.readouterr().out == "model=\n"


def test_config_set_creates_minimal_config_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["set", "timeout_seconds", "12"])

    output = capsys.readouterr().out
    assert code == 0
    assert output == f"Updated timeout_seconds=12 in {config_path}\n"
    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "schema_version": CURRENT_USER_CONFIG_SCHEMA_VERSION,
        "timeout_seconds": 12,
    }


def test_config_set_updates_existing_valid_config_and_preserves_unrelated_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    audit_path = tmp_path / "audit.jsonl"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "model": "old:model",
                "audit_log_path": str(audit_path),
                "history_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["set", "model", "new:model"])

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert code == 0
    assert f"Updated model=new:model in {config_path}" in capsys.readouterr().out
    assert saved["model"] == "new:model"
    assert saved["audit_log_path"] == str(audit_path)
    assert saved["history_enabled"] is True


def test_config_set_rejects_invalid_existing_config_without_overwriting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    original = '{"audit_log_path": 123}'
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["set", "color_mode", "never"])

    output = capsys.readouterr().out
    assert code == 2
    assert "Config set failed" in output
    assert "config validate" in output
    assert config_path.read_text(encoding="utf-8") == original


def test_config_set_reports_override_note_when_environment_still_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("OTERMINUS_COLOR", "always")

    code = run_config_cli(["set", "color_mode", "never"])

    output = capsys.readouterr().out
    assert code == 0
    assert f"Updated color_mode=never in {config_path}" in output
    assert (
        "Note: effective value is currently overridden by OTERMINUS_COLOR from environment."
        in output
    )
    assert json.loads(config_path.read_text(encoding="utf-8"))["color_mode"] == "never"


def test_config_set_reports_override_note_when_dotenv_still_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)
    (tmp_path / ".env").write_text("OTERMINUS_COLOR=auto\n", encoding="utf-8")

    code = run_config_cli(["set", "color_mode", "never"])

    output = capsys.readouterr().out
    assert code == 0
    assert f"Updated color_mode=never in {config_path}" in output
    assert "Note: effective value is currently overridden by OTERMINUS_COLOR from .env." in output
    assert json.loads(config_path.read_text(encoding="utf-8"))["color_mode"] == "never"


def test_config_set_does_not_modify_dotenv_or_shell_startup_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    shell_files = [home / ".zshrc", home / ".bashrc", home / ".config" / "fish" / "config.fish"]
    for path in shell_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"original {path.name}\n", encoding="utf-8")
    dotenv_path = tmp_path / ".env"
    dotenv_text = "OTERMINUS_HISTORY_ENABLED=true\n"
    dotenv_path.write_text(dotenv_text, encoding="utf-8")
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    assert run_config_cli(["set", "history_enabled", "false"]) == 0

    assert dotenv_path.read_text(encoding="utf-8") == dotenv_text
    for path in shell_files:
        assert path.read_text(encoding="utf-8") == f"original {path.name}\n"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("no", False),
        ("on", True),
        ("off", False),
    ],
)
def test_config_set_boolean_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    raw: str,
    expected: bool,
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    assert run_config_cli(["set", "auto_execute_safe", raw]) == 0

    assert json.loads(config_path.read_text(encoding="utf-8"))["auto_execute_safe"] is expected


@pytest.mark.parametrize("raw", ["auto", "always", "never", "ALWAYS"])
def test_config_set_color_modes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: str) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    assert run_config_cli(["set", "color_mode", raw]) == 0

    assert json.loads(config_path.read_text(encoding="utf-8"))["color_mode"] == raw.lower()


@pytest.mark.parametrize("raw", ["beginner", "safe", "developer", "power", "DEVELOPER"])
def test_config_set_command_profiles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: str
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    assert run_config_cli(["set", "command_profile", raw]) == 0

    assert json.loads(config_path.read_text(encoding="utf-8"))["command_profile"] == raw.lower()


@pytest.mark.parametrize("raw", ["1", "42"])
def test_config_set_positive_integer_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: str
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    assert run_config_cli(["set", "max_output_chars", raw]) == 0

    assert json.loads(config_path.read_text(encoding="utf-8"))["max_output_chars"] == int(raw)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["set", "auto_execute_safe", "sometimes"], "boolean"),
        (["set", "color_mode", "sparkles"], "color_mode must be one of"),
        (["set", "command_profile", "devv"], "command_profile must be one of"),
        (["set", "timeout_seconds", "0"], "greater than zero"),
        (["set", "timeout_seconds", "-1"], "positive base-10 integer"),
        (["set", "timeout_seconds", "1.5"], "positive base-10 integer"),
        (["set", "timeout_seconds", "abc"], "positive base-10 integer"),
    ],
)
def test_config_set_rejects_invalid_values_without_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    expected: str,
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(argv)

    assert code == 2
    assert expected in capsys.readouterr().out
    assert not config_path.exists()


@pytest.mark.parametrize("raw", ["none", "null", "NONE", "NULL"])
def test_config_set_model_clearing_tokens_remove_persisted_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raw: str
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1, "model": "gemma4"}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    assert run_config_cli(["set", "model", raw]) == 0

    assert "model" not in json.loads(config_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "key",
    [
        "allow_dangerous",
        "policy.allow_dangerous",
        "allowed_roots",
        "disabled_command_packs",
        "policy.mode",
        "audit_log_path",
        "history_path",
        "history_limit",
        "failure_explanation_max_chars",
        "schema_version",
        "onboarding_completed",
    ],
)
def test_config_set_rejects_unsupported_and_dangerous_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    key: str,
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["set", key, "true"])

    output = capsys.readouterr().out
    assert code == 2
    assert "Unsupported config key" in output
    if "allow_dangerous" in key:
        assert "environment-only" in output
    assert not config_path.exists()


def test_config_get_rejects_unsupported_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))

    assert run_config_cli(["get", "schema_version"]) == 2

    output = capsys.readouterr().out
    assert "Unsupported config key" in output
    assert "schema_version" in output


def test_config_reset_removes_persisted_key_and_preserves_unrelated_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "onboarding_completed": True,
                "model": "gemma4",
                "color_mode": "never",
                "audit_enabled": False,
                "audit_log_path": str(tmp_path / "audit.jsonl"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)

    code = run_config_cli(["reset", "color_mode"])

    output = capsys.readouterr().out
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert code == 0
    assert f"Reset color_mode in {config_path}" in output
    assert "color_mode" not in saved
    assert saved["schema_version"] == CURRENT_USER_CONFIG_SCHEMA_VERSION
    assert saved["onboarding_completed"] is True
    assert saved["model"] == "gemma4"
    assert saved["audit_enabled"] is False
    assert saved["audit_log_path"] == str(tmp_path / "audit.jsonl")
    assert run_config_cli(["get", "color_mode"]) == 0
    assert capsys.readouterr().out == "color_mode=auto\n"


def test_config_reset_non_persisted_key_succeeds_without_rewriting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    original = '{\n  "schema_version": 1,\n  "audit_enabled": false\n}\n'
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["reset", "color_mode"])

    output = capsys.readouterr().out
    assert code == 0
    assert f"No persisted value for color_mode in {config_path}; nothing to reset." in output
    assert config_path.read_text(encoding="utf-8") == original


def test_config_reset_missing_config_does_not_create_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "missing.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["reset", "color_mode"])

    output = capsys.readouterr().out
    assert code == 0
    assert "No config file exists" in output
    assert "color_mode" in output
    assert not config_path.exists()


def test_config_reset_all_safe_missing_config_does_not_create_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "missing.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["reset", "--all-safe"])

    output = capsys.readouterr().out
    assert code == 0
    assert "No config file exists" in output
    assert "safe settings" in output
    assert not config_path.exists()


def test_config_reset_rejects_invalid_existing_config_without_overwriting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    original = '{"audit_log_path": 123}'
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["reset", "color_mode"])

    output = capsys.readouterr().out
    assert code == 2
    assert "Config reset failed" in output
    assert "config validate" in output
    assert config_path.read_text(encoding="utf-8") == original


def test_config_reset_all_safe_resets_documented_set_and_preserves_internal_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    payload = {
        "schema_version": 1,
        "onboarding_completed": True,
        "model": "gemma4",
        "command_profile": "developer",
        "auto_execute_safe": True,
        "audit_enabled": False,
        "audit_redact": False,
        "history_enabled": True,
        "history_redact": False,
        "explain_failures": True,
        "color_mode": "never",
        "timeout_seconds": 7,
        "max_output_chars": 1234,
        "allowed_roots": [str(tmp_path)],
        "disabled_command_packs": ["network"],
        "policy_mode": "safe",
        "audit_log_path": str(tmp_path / "audit.jsonl"),
        "history_path": str(tmp_path / "history.jsonl"),
        "history_limit": 9,
        "failure_explanation_max_chars": 111,
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["reset", "--all-safe"])

    output = capsys.readouterr().out
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert code == 0
    assert "Reset safe config keys" in output
    for key in SUPPORTED_MUTABLE_CONFIG_KEYS:
        assert key not in saved
        assert key in output
    assert saved["schema_version"] == CURRENT_USER_CONFIG_SCHEMA_VERSION
    assert saved["onboarding_completed"] is True
    assert saved["allowed_roots"] == [str(tmp_path)]
    assert saved["disabled_command_packs"] == ["network"]
    assert saved["policy_mode"] == "safe"
    assert saved["audit_log_path"] == str(tmp_path / "audit.jsonl")
    assert saved["history_path"] == str(tmp_path / "history.jsonl")
    assert saved["history_limit"] == 9
    assert saved["failure_explanation_max_chars"] == 111
    assert read_user_config().config is not None


def test_config_reset_all_safe_with_no_persisted_safe_values_succeeds_without_rewriting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    original = '{"schema_version": 1, "allowed_roots": ["/tmp"]}\n'
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["reset", "--all-safe"])

    output = capsys.readouterr().out
    assert code == 0
    assert f"No persisted safe config values in {config_path}; nothing to reset." in output
    assert config_path.read_text(encoding="utf-8") == original


def test_config_reset_reports_override_note_when_environment_still_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1, "color_mode": "never"}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("OTERMINUS_COLOR", "always")

    code = run_config_cli(["reset", "color_mode"])

    output = capsys.readouterr().out
    assert code == 0
    assert f"Reset color_mode in {config_path}" in output
    assert (
        "Note: effective value is currently overridden by OTERMINUS_COLOR from environment."
        in output
    )


def test_config_reset_reports_override_note_when_dotenv_still_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1, "color_mode": "never"}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)
    (tmp_path / ".env").write_text("OTERMINUS_COLOR=always\n", encoding="utf-8")

    code = run_config_cli(["reset", "color_mode"])

    output = capsys.readouterr().out
    assert code == 0
    assert "Note: effective value is currently overridden by OTERMINUS_COLOR from .env." in output


@pytest.mark.parametrize(
    "key",
    [
        "allow_dangerous",
        "policy.allow_dangerous",
        "allowed_roots",
        "disabled_command_packs",
        "policy.mode",
        "audit_log_path",
        "history_path",
        "history_limit",
        "failure_explanation_max_chars",
        "schema_version",
        "onboarding_completed",
    ],
)
def test_config_reset_rejects_unsupported_and_dangerous_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    key: str,
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    code = run_config_cli(["reset", key])

    output = capsys.readouterr().out
    assert code == 2
    assert "Unsupported config key" in output
    if "allow_dangerous" in key:
        assert "environment-only" in output
    assert not config_path.exists()


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


@pytest.mark.parametrize(
    "argv",
    (
        ["get"],
        ["set", "color_mode"],
        ["set", "color_mode", "never", "extra"],
        ["reset"],
        ["reset", "color_mode", "--all-safe"],
        ["reset", "color_mode", "extra"],
    ),
)
def test_config_get_set_missing_or_extra_arguments_fail(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_config_cli(argv)

    assert exc_info.value.code == 2


def test_main_config_get_set_and_reset_bypass_request_lifecycle_and_ollama(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from oterminus.cli import main

    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", Mock(side_effect=AssertionError("no config")))
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("no startup checks")),
    )
    monkeypatch.setattr("oterminus.cli.Executor", Mock(side_effect=AssertionError("no executor")))
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr(
        "oterminus.cli.OllamaPlannerClient", Mock(side_effect=AssertionError("no Ollama client"))
    )
    monkeypatch.setattr(
        "oterminus.cli.handle_request", Mock(side_effect=AssertionError("no request lifecycle"))
    )
    monkeypatch.setattr(
        "oterminus.cli.AuditLogger", Mock(side_effect=AssertionError("no audit logger"))
    )
    monkeypatch.setattr(
        "oterminus.cli.PersistentHistoryStore",
        Mock(side_effect=AssertionError("no history store")),
    )

    assert main(["config", "set", "color_mode", "never"]) == 0
    assert main(["config", "get", "color_mode"]) == 0
    assert main(["config", "reset", "color_mode"]) == 0

    output = capsys.readouterr().out
    assert "color_mode=never" in output
    assert f"Reset color_mode in {config_path}" in output
    assert "color_mode" not in json.loads(config_path.read_text(encoding="utf-8"))
    assert "allow_dangerous" not in SUPPORTED_MUTABLE_CONFIG_KEYS

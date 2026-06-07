import json
from pathlib import Path

import pytest

from oterminus.config import UserConfig, read_user_config
from oterminus.models import RiskLevel
from oterminus.onboarding import run_onboarding, save_declined_onboarding
from oterminus.setup import OllamaModelStatus


@pytest.fixture(autouse=True)
def _isolate_dotenv_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


def test_onboarding_accepts_safe_defaults_and_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    answers = iter(["", "", "", "", "", "", "2", ""])

    result = run_onboarding(
        existing=None,
        input_fn=lambda _: next(answers),
        model_status_fn=lambda: OllamaModelStatus(
            cli_installed=True,
            service_available=True,
            models=("gemma3:latest", "llama3.2:latest"),
        ),
    )

    output = capsys.readouterr().out
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.completed is True
    assert result.saved is True
    assert payload["onboarding_completed"] is True
    assert payload["command_profile"] == "safe"
    assert payload["auto_execute_safe"] is False
    assert payload["audit_enabled"] is True
    assert payload["audit_redact"] is True
    assert payload["history_enabled"] is False
    assert payload["history_redact"] is True
    assert payload["explain_failures"] is False
    assert payload["model"] == "llama3.2:latest"
    assert "allow_dangerous" not in payload
    assert "Configuration summary" in output
    assert str(config_path) in output
    assert read_user_config().config is not None


def test_onboarding_summary_cancel_does_not_overwrite_existing_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    original = {
        "schema_version": 1,
        "command_profile": "developer",
        "timeout_seconds": 17,
    }
    config_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    existing = read_user_config().config
    assert existing is not None
    answers = iter(["power", "y", "n", "n", "y", "skip", "n"])

    result = run_onboarding(
        existing=existing,
        input_fn=lambda _: next(answers),
        model_status_fn=lambda: OllamaModelStatus(True, True, ("gemma3:latest",)),
    )

    assert result.completed is False
    assert result.saved is False
    assert json.loads(config_path.read_text(encoding="utf-8")) == original


def test_onboarding_preserves_unmanaged_existing_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "onboarding_completed": False,
                "command_profile": "beginner",
                "disabled_command_packs": ["macos"],
                "policy_mode": "safe",
                "allowed_roots": [str(tmp_path)],
                "timeout_seconds": 11,
                "max_output_chars": 222,
                "audit_log_path": str(tmp_path / "audit.jsonl"),
                "history_path": str(tmp_path / "history.jsonl"),
                "history_limit": 5,
                "failure_explanation_max_chars": 333,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    existing = read_user_config().config
    assert existing is not None
    answers = iter(["developer", "y", "n", "y", "", "y", ""])

    result = run_onboarding(
        existing=existing,
        input_fn=lambda _: next(answers),
        model_status_fn=lambda: OllamaModelStatus(False, False, (), "missing"),
    )

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.saved is True
    assert payload["schema_version"] == 1
    assert payload["onboarding_completed"] is True
    assert payload["command_profile"] == "developer"
    assert payload["auto_execute_safe"] is True
    assert payload["audit_enabled"] is False
    assert payload["audit_redact"] is True
    assert payload["history_enabled"] is True
    assert payload["history_redact"] is True
    assert payload["explain_failures"] is True
    assert payload["disabled_command_packs"] == ["macos"]
    assert payload["policy_mode"] == RiskLevel.SAFE.value
    assert payload["allowed_roots"] == [str(tmp_path)]
    assert payload["timeout_seconds"] == 11
    assert payload["max_output_chars"] == 222
    assert payload["audit_log_path"] == str(tmp_path / "audit.jsonl")
    assert payload["history_path"] == str(tmp_path / "history.jsonl")
    assert payload["history_limit"] == 5
    assert payload["failure_explanation_max_chars"] == 333


def test_declined_onboarding_saves_completed_safe_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    result = save_declined_onboarding()

    output = capsys.readouterr().out
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.completed is True
    assert result.saved is True
    assert payload["onboarding_completed"] is True
    assert payload["command_profile"] == "safe"
    assert "config init" in output


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (OllamaModelStatus(False, False, (), "missing"), "Ollama CLI was not found"),
        (OllamaModelStatus(True, False, (), "connection refused"), "service is unavailable"),
        (OllamaModelStatus(True, True, ()), "No installed Ollama models"),
    ),
)
def test_onboarding_ollama_unavailable_states_do_not_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    status: OllamaModelStatus,
    expected: str,
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    answers = iter(["", "", "", "", "", "", ""])

    result = run_onboarding(
        existing=None,
        input_fn=lambda _: next(answers),
        model_status_fn=lambda: status,
    )

    output = capsys.readouterr().out
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.saved is True
    assert payload["model"] is None
    assert expected in output
    assert "Direct commands and deterministic local paths remain usable" in output


def test_onboarding_existing_valid_model_is_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    existing = UserConfig(model="gemma3:latest", command_profile="power")
    answers = iter(["", "", "", "", "", "", "", "", ""])

    result = run_onboarding(
        existing=existing,
        input_fn=lambda _: next(answers),
        model_status_fn=lambda: OllamaModelStatus(
            True, True, ("llama3.2:latest", "gemma3:latest")
        ),
    )

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.saved is True
    assert payload["command_profile"] == "power"
    assert payload["model"] == "gemma3:latest"


def test_onboarding_existing_missing_model_can_be_skipped_to_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    existing = UserConfig(model="removed:model", command_profile="safe")
    answers = iter(["", "", "", "", "", "", "skip", ""])

    result = run_onboarding(
        existing=existing,
        input_fn=lambda _: next(answers),
        model_status_fn=lambda: OllamaModelStatus(True, True, ("gemma3:latest",)),
    )

    output = capsys.readouterr().out
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.saved is True
    assert payload["model"] is None
    assert "no longer installed" in output

import json
from pathlib import Path

import pytest

from oterminus import setup
from oterminus.ollama_client import OllamaClientError


class DummyCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_missing_ollama_cli(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)

    with pytest.raises(setup.SetupError) as exc:
        setup.ensure_startup_ready(input_fn=lambda _: "1")

    assert "Ollama is not installed" in str(exc.value)


def test_no_models_available(monkeypatch) -> None:
    monkeypatch.setattr(setup, "check_ollama_installed", lambda: True)
    monkeypatch.setattr(setup, "check_ollama_running", lambda: True)
    monkeypatch.setattr(setup, "get_available_models", lambda: [])

    with pytest.raises(setup.SetupError) as exc:
        setup.ensure_startup_ready(input_fn=lambda _: "1")

    assert "No models found" in str(exc.value)


def test_model_selection_flow(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    answers = iter(["bad", "2"])

    selected = setup.run_first_time_setup(["gemma3:latest", "llama3.2:latest"], input_fn=lambda _: next(answers))

    assert selected == "llama3.2:latest"
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["model"] == "llama3.2:latest"


def test_config_persistence_skips_prompt_when_model_is_valid(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"model": "gemma3:latest"}), encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    def fail_prompt(_: str) -> str:
        raise AssertionError("prompt should not be called")

    selected = setup.run_first_time_setup(["gemma3:latest", "llama3.2:latest"], input_fn=fail_prompt)
    assert selected == "gemma3:latest"


def test_missing_configured_model_reprompts(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"model": "removed:model"}), encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    selected = setup.run_first_time_setup(["gemma3:latest", "llama3.2:latest"], input_fn=lambda _: "1")

    assert selected == "gemma3:latest"
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["model"] == "gemma3:latest"


def test_config_save_failure_raises_setup_error(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    def failing_save(_: dict[str, object]) -> None:
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(setup, "save_config", failing_save)

    with pytest.raises(setup.SetupError) as exc:
        setup.run_first_time_setup(["gemma3:latest", "llama3.2:latest"], input_fn=lambda _: "1")

    assert "Failed to save setup configuration" in str(exc.value)


def test_get_available_models_raises_on_ollama_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return DummyCompletedProcess(returncode=1, stderr="connection refused")

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(OllamaClientError):
        setup.get_available_models()

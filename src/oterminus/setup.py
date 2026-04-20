from __future__ import annotations

import shutil
import subprocess
from typing import Any, Callable

from oterminus.config import load_user_config, save_user_config
from oterminus.ollama_client import OllamaClientError, parse_ollama_list_output


class SetupError(RuntimeError):
    pass


def check_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def check_ollama_running() -> bool:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=False)
    except OSError:
        return False
    return result.returncode == 0


def get_available_models() -> list[str]:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise OllamaClientError(
            "Unable to run `ollama list`. Ensure Ollama is installed and available on PATH."
        ) from exc

    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or "`ollama list` failed."
        raise OllamaClientError(message)

    return parse_ollama_list_output(result.stdout)


def load_config() -> dict[str, Any]:
    return load_user_config()


def save_config(payload: dict[str, Any]) -> None:
    save_user_config(payload)


def _choose_model(models: list[str], input_fn: Callable[[str], str]) -> str:
    print("Available Ollama models:")
    for index, model in enumerate(models, start=1):
        print(f"{index}. {model}")

    while True:
        answer = input_fn("Select a model by number: ").strip()
        if answer.isdigit():
            selected_index = int(answer)
            if 1 <= selected_index <= len(models):
                return models[selected_index - 1]
        print(f"Please enter a number between 1 and {len(models)}.")


def run_first_time_setup(models: list[str], input_fn: Callable[[str], str] = input) -> str:
    config = load_config()
    configured_model = config.get("model")

    if isinstance(configured_model, str) and configured_model in models:
        return configured_model

    if isinstance(configured_model, str) and configured_model:
        print(f"Warning: configured model '{configured_model}' is no longer installed.")

    selected_model = _choose_model(models, input_fn=input_fn)
    config["model"] = selected_model
    save_config(config)
    print(f"Saved model: {selected_model}")
    return selected_model


def ensure_startup_ready(input_fn: Callable[[str], str] = input) -> str:
    if not check_ollama_installed():
        raise SetupError(
            "Ollama is not installed. Install it from https://ollama.com/download and then run oterminus again."
        )

    if not check_ollama_running():
        raise SetupError("Ollama is installed but not running. Please start it using `ollama serve`.")

    try:
        models = get_available_models()
    except OllamaClientError as exc:
        raise SetupError(f"Unable to read installed Ollama models: {exc}") from exc

    if not models:
        raise SetupError(
            "No models found. Please run: ollama pull <model> (for example: ollama pull gemma4)."
        )

    return run_first_time_setup(models, input_fn=input_fn)

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from oterminus.config import UserConfig, load_user_config, merge_user_config, save_user_config
from oterminus.ollama_client import OllamaClientError, parse_ollama_list_output


class SetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaModelStatus:
    cli_installed: bool
    service_available: bool
    models: tuple[str, ...] = ()
    error: str | None = None


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


def get_ollama_model_status() -> OllamaModelStatus:
    if not check_ollama_installed():
        return OllamaModelStatus(
            cli_installed=False,
            service_available=False,
            error="Ollama CLI was not found on PATH.",
        )
    if not check_ollama_running():
        return OllamaModelStatus(
            cli_installed=True,
            service_available=False,
            error="Ollama is installed but the service is not available.",
        )
    try:
        models = tuple(get_available_models())
    except OllamaClientError as exc:
        return OllamaModelStatus(
            cli_installed=True,
            service_available=False,
            error=str(exc),
        )
    return OllamaModelStatus(cli_installed=True, service_available=True, models=models)


def load_config() -> UserConfig | None:
    return load_user_config()


def save_config(config: UserConfig) -> None:
    save_user_config(config)


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
    configured_model = config.model if config is not None else None

    if configured_model in models:
        return configured_model

    if configured_model:
        print(f"Warning: configured model '{configured_model}' is no longer installed.")

    selected_model = _choose_model(models, input_fn=input_fn)
    updated_config = merge_user_config(config, model=selected_model)
    try:
        save_config(updated_config)
    except OSError as exc:
        raise SetupError(
            "Failed to save setup configuration. Check write permissions for your config path and try again."
        ) from exc
    print(f"Saved model: {selected_model}")
    return selected_model


def ensure_startup_ready(input_fn: Callable[[str], str] = input) -> str:
    if not check_ollama_installed():
        raise SetupError(
            "Ollama is not installed. Install it from https://ollama.com/download and then run oterminus again."
        )

    if not check_ollama_running():
        raise SetupError(
            "Ollama is installed but not running. Please start it using `ollama serve`."
        )

    try:
        models = get_available_models()
    except OllamaClientError as exc:
        raise SetupError(f"Unable to read installed Ollama models: {exc}") from exc

    if not models:
        raise SetupError(
            "No models found. Please run: ollama pull <model> (for example: ollama pull gemma4)."
        )

    return run_first_time_setup(models, input_fn=input_fn)

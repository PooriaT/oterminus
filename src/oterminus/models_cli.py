from __future__ import annotations

import argparse
from collections.abc import Callable

from oterminus.config import ConfigError, ResolvedConfig, resolve_config
from oterminus.setup import OllamaModelStatus, get_ollama_model_status


MODELS_COMMANDS: tuple[str, ...] = ("list",)


def parse_models_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="oterminus models",
        description=(
            "Inspect installed Ollama models and the selected OTerminus model without "
            "starting the request lifecycle."
        ),
    )
    subparsers = parser.add_subparsers(dest="models_command")
    subparsers.add_parser("list", help="List installed models and show the selected model.")
    return parser.parse_args(argv)


def run_models_cli(
    argv: list[str],
    *,
    status_provider: Callable[[], OllamaModelStatus] = get_ollama_model_status,
    config_resolver: Callable[[], ResolvedConfig] = resolve_config,
) -> int:
    args = parse_models_args(argv)
    if args.models_command not in {None, "list"}:  # pragma: no cover - argparse enforces this
        return 2

    try:
        resolved = config_resolver()
    except (ConfigError, ValueError) as exc:
        print(f"Configuration error: {exc}")
        return 2

    status = status_provider()
    selected_model = resolved.app_config.model
    source = resolved.sources.get("model")
    source_value = getattr(source, "value", str(source) if source is not None else "unknown")
    list_available = status.cli_installed and status.service_available
    matched_model = (
        _matching_installed_model(selected_model, status.models)
        if selected_model is not None and list_available
        else None
    )
    selected_installed = (
        matched_model is not None if selected_model is not None and list_available else None
    )

    print("OTerminus models")
    print()
    print("Ollama:")
    print(f"  CLI: {'installed' if status.cli_installed else 'missing'}")
    print(f"  Service: {'reachable' if status.service_available else 'unavailable'}")
    installed_count = str(len(status.models)) if list_available else "unavailable"
    print(f"  Installed models: {installed_count}")
    print()
    print("Selection:")
    print(f"  Model: {selected_model or 'not configured'}")
    print(f"  Source: {source_value}")
    print(f"  Config path: {resolved.config_path}")
    print(f"  Installed: {_installed_label(selected_model, selected_installed)}")

    if list_available:
        print()
        print("Models:")
        if status.models:
            for model in status.models:
                if model == matched_model:
                    print(f"  * {model}  selected")
                else:
                    print(f"    {model}")
        else:
            print("  (none)")

    guidance = _guidance(status, selected_model, selected_installed)
    if guidance:
        print()
        print(f"Guidance: {guidance}")

    if not list_available or selected_installed is False:
        return 1
    return 0


def _matching_installed_model(selected_model: str, installed_models: tuple[str, ...]) -> str | None:
    if selected_model in installed_models:
        return selected_model
    if ":" in selected_model.rsplit("/", maxsplit=1)[-1]:
        return None
    latest_name = f"{selected_model}:latest"
    return latest_name if latest_name in installed_models else None


def _installed_label(selected_model: str | None, selected_installed: bool | None) -> str:
    if selected_model is None:
        return "not applicable"
    if selected_installed is None:
        return "unknown"
    return "yes" if selected_installed else "no"


def _guidance(
    status: OllamaModelStatus,
    selected_model: str | None,
    selected_installed: bool | None,
) -> str | None:
    if not status.cli_installed:
        return "Install Ollama, then rerun `oterminus models`."
    if not status.service_available:
        return "Start Ollama with `ollama serve`, then rerun `oterminus models`."
    if not status.models:
        return "Pull a model with `ollama pull <model>`."
    if selected_model is None:
        return "Select one with `oterminus config set model <model-name>`."
    if selected_installed is False:
        return (
            f"Pull it with `ollama pull {selected_model}` or select an installed model with "
            "`oterminus config set model <model-name>`."
        )
    return None

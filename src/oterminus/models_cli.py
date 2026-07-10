from __future__ import annotations

import argparse
from collections.abc import Callable

from oterminus.config import ConfigError, ResolvedConfig, resolve_config
from oterminus.model_diagnostics import (
    ModelDiagnosticError,
    ModelDiagnosticReport,
    run_model_diagnostics,
)
from oterminus.ollama_client import OllamaClientError
from oterminus.setup import OllamaModelStatus, get_ollama_model_status


MODELS_COMMANDS: tuple[str, ...] = ("list", "test")


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
    test_parser = subparsers.add_parser(
        "test",
        help="Test a model against OTerminus's strict planner proposal schema.",
        description=(
            "Send fixed read-only planning probes to a configured or explicitly named model. "
            "No proposed command is executed."
        ),
    )
    test_parser.add_argument(
        "model",
        nargs="?",
        help="Installed model to test without changing the saved configuration.",
    )
    return parser.parse_args(argv)


def run_models_cli(
    argv: list[str],
    *,
    status_provider: Callable[[], OllamaModelStatus] = get_ollama_model_status,
    config_resolver: Callable[[], ResolvedConfig] = resolve_config,
    diagnostic_runner: Callable[[str], ModelDiagnosticReport] = run_model_diagnostics,
) -> int:
    args = parse_models_args(argv)
    if args.models_command == "test":
        return _run_model_test(
            args.model,
            status_provider=status_provider,
            config_resolver=config_resolver,
            diagnostic_runner=diagnostic_runner,
        )
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


def _run_model_test(
    requested_model: str | None,
    *,
    status_provider: Callable[[], OllamaModelStatus],
    config_resolver: Callable[[], ResolvedConfig],
    diagnostic_runner: Callable[[str], ModelDiagnosticReport],
) -> int:
    if requested_model is None:
        try:
            resolved = config_resolver()
        except (ConfigError, ValueError) as exc:
            print(f"Configuration error: {exc}")
            return 2
        model = resolved.app_config.model
        source = resolved.sources.get("model")
        source_value = getattr(source, "value", str(source) if source is not None else "unknown")
        source_label = f"configuration ({source_value})"
        if model is None:
            print("No model is configured. Supply an installed model or configure one:")
            print("  oterminus models test <model-name>")
            print("  oterminus config set model <model-name>")
            return 2
    else:
        model = requested_model
        source_label = "command line"

    status = status_provider()
    readiness_error = _model_test_readiness_error(status, model)
    if readiness_error is not None:
        print(f"Cannot run model schema test: {readiness_error}")
        print()
        _print_test_next_steps()
        return 2

    print("OTerminus model schema test")
    print(f"Model: {model}")
    print(f"Source: {source_label}")
    print()

    try:
        report = diagnostic_runner(model)
    except (ModelDiagnosticError, OllamaClientError) as exc:
        print(f"ERROR Model test could not complete: {exc}")
        print()
        _print_test_next_steps()
        return 2

    passed = sum(result.passed for result in report.results)
    failed = len(report.results) - passed
    repaired = sum(result.passed and result.repaired for result in report.results)

    for result in report.results:
        if result.passed:
            shape = f"{result.mode or 'unknown'}/{result.command_family or 'none'}"
            suffix = " (after repair)" if result.repaired else ""
            print(f"PASS  {result.probe_id:<28} {shape}{suffix}")
        else:
            reason = result.failure_reason or "unknown failure"
            print(f"FAIL  {result.probe_id:<28} {reason}")

    print()
    print(f"Summary: {passed} passed, {failed} failed, {repaired} required repair")
    if failed:
        print()
        _print_test_next_steps()
        return 1
    return 0


def _model_test_readiness_error(status: OllamaModelStatus, model: str) -> str | None:
    if not status.cli_installed:
        return "Ollama is not installed. Install Ollama and try again."
    if not status.service_available:
        return "Ollama is not reachable. Start it with `ollama serve` and try again."
    if not status.models:
        return "no installed models were found. Pull one with `ollama pull <model>`."
    if _matching_installed_model(model, status.models) is None:
        return f"model '{model}' is not installed."
    return None


def _print_test_next_steps() -> None:
    print("Try another installed model:")
    print("  oterminus models")
    print("  oterminus config set model <model-name>")
    print()
    print("Check the environment:")
    print("  oterminus doctor")


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

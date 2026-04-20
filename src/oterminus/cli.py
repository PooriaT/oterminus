from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Callable

from oterminus.config import load_config
from oterminus.direct_commands import detect_direct_command
from oterminus.executor import Executor
from oterminus.logging_utils import configure_logging
from oterminus.ollama_client import OllamaClientError, OllamaPlannerClient, is_ollama_installed, list_installed_models
from oterminus.planner import Planner, PlannerError
from oterminus.policies import ConfirmationLevel, confirmation_level
from oterminus.renderer import render_preview
from oterminus.validator import Validator

LOGGER = logging.getLogger("oterminus")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="oterminus: local AI terminal assistant")
    parser.add_argument("request", nargs="*", help="Natural-language terminal request")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def ask_confirmation(level: ConfirmationLevel) -> bool:
    if level == ConfirmationLevel.VERY_STRONG:
        prompt = "Type EXECUTE EXPERIMENTAL to proceed: "
    elif level == ConfirmationLevel.STRONG:
        prompt = "Type EXECUTE to proceed: "
    else:
        prompt = "Run command? [y/N]: "

    answer = input(prompt).strip()
    if level == ConfirmationLevel.VERY_STRONG:
        return answer == "EXECUTE EXPERIMENTAL"
    if level == ConfirmationLevel.STRONG:
        return answer == "EXECUTE"
    return answer.lower() in {"y", "yes"}


def choose_model(models: list[str]) -> str:
    print("Available Ollama models:")
    for index, model in enumerate(models, start=1):
        print(f"{index}. {model}")

    while True:
        answer = input("Select a model by number: ").strip()
        if answer.isdigit():
            selection = int(answer)
            if 1 <= selection <= len(models):
                return models[selection - 1]
        print(f"Please enter a number between 1 and {len(models)}.")


def resolve_model_name() -> str | None:
    models = list_installed_models()
    if not models:
        return None
    return choose_model(models)


def handle_request(
    request: str, planner_factory: Planner | Callable[[], Planner], validator: Validator, executor: Executor
) -> int:
    LOGGER.info("request=%s", request)

    proposal = detect_direct_command(request)
    try:
        if proposal is None:
            planner = planner_factory if hasattr(planner_factory, "plan") else planner_factory()
            proposal = planner.plan(request)
    except (PlannerError, OllamaClientError) as exc:
        print(f"Planning failed: {exc}")
        return 2

    validation = validator.validate(proposal)
    print(render_preview(proposal, validation))

    if not validation.accepted:
        LOGGER.warning("proposal_rejected reasons=%s", validation.reasons)
        return 3

    confirmed = ask_confirmation(confirmation_level(proposal.mode, validation.risk_level))
    command = validation.rendered_command
    LOGGER.info("confirmed=%s command=%s", confirmed, command)
    if not confirmed:
        print("Cancelled.")
        return 0

    if command is None or not validation.argv:
        print("Proposal cannot be executed because it could not be rendered into a safe command.")
        return 3

    try:
        result = executor.run(validation.argv, display_command=command)
    except subprocess.TimeoutExpired:
        print(f"Execution timed out after {executor.timeout_seconds}s.")
        return 124
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Execution failed: {exc}")
        return 1
    except KeyboardInterrupt:
        print("Execution interrupted.")
        return 130

    print("\n--- execution output ---")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    print(f"Exit code: {result.returncode}")

    LOGGER.info("exit_code=%s", result.returncode)
    return result.returncode


def repl(planner_factory: Planner | Callable[[], Planner], validator: Validator, executor: Executor) -> int:
    print("oterminus REPL. Type 'help' for guidance, 'exit' or 'quit' to leave.")
    while True:
        try:
            request = input("oterminus> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not request:
            continue
        if request.lower() in {"exit", "quit"}:
            return 0
        if request.lower() == "help":
            print(
                "Enter either a natural-language terminal request or a direct shell command.\n"
                "Examples: 'find all .py files', 'ls -lh', 'cd src'"
            )
            continue

        handle_request(request, planner_factory, validator, executor)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(verbose=args.verbose)

    config = load_config()
    validator = Validator(config.policy)
    executor = Executor(timeout_seconds=config.timeout_seconds)
    planner: Planner | None = None

    def get_planner() -> Planner:
        nonlocal planner
        if planner is not None:
            return planner

        if not is_ollama_installed():
            raise OllamaClientError("Ollama is not installed on this machine. Install Ollama first, then run oterminus again.")

        try:
            model_name = resolve_model_name()
        except OllamaClientError as exc:
            raise OllamaClientError(f"Unable to determine installed Ollama models: {exc}") from exc

        if model_name is None:
            raise OllamaClientError(
                "No Ollama models are installed on this machine. Pull a model with `ollama pull <model>` and try again."
            )

        client = OllamaPlannerClient(model=model_name)
        planner = Planner(client)
        return planner

    if args.request:
        request = " ".join(args.request)
        return handle_request(request, get_planner, validator, executor)
    return repl(get_planner, validator, executor)


if __name__ == "__main__":
    raise SystemExit(main())

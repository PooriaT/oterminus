from __future__ import annotations

import argparse
import logging
import subprocess
import sys

from oterminus.config import load_config
from oterminus.direct_commands import detect_direct_command
from oterminus.executor import Executor
from oterminus.logging_utils import configure_logging
from oterminus.ollama_client import OllamaClientError, OllamaPlannerClient
from oterminus.planner import Planner, PlannerError
from oterminus.renderer import render_preview
from oterminus.validator import Validator

LOGGER = logging.getLogger("oterminus")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="oterminus: local AI terminal assistant")
    parser.add_argument("request", nargs="*", help="Natural-language terminal request")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def ask_confirmation(is_dangerous: bool) -> bool:
    prompt = "Type EXECUTE to proceed: " if is_dangerous else "Run command? [y/N]: "
    answer = input(prompt).strip()
    if is_dangerous:
        return answer == "EXECUTE"
    return answer.lower() in {"y", "yes"}


def handle_request(request: str, planner: Planner, validator: Validator, executor: Executor) -> int:
    LOGGER.info("request=%s", request)

    proposal = detect_direct_command(request)
    try:
        if proposal is None:
            proposal = planner.plan(request)
    except (PlannerError, OllamaClientError) as exc:
        print(f"Planning failed: {exc}")
        return 2

    validation = validator.validate(proposal)
    print(render_preview(proposal, validation))

    if not validation.accepted:
        LOGGER.warning("proposal_rejected reasons=%s", validation.reasons)
        return 3

    confirmed = ask_confirmation(is_dangerous=validation.risk_level.value == "dangerous")
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


def repl(planner: Planner, validator: Validator, executor: Executor) -> int:
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

        handle_request(request, planner, validator, executor)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(verbose=args.verbose)

    config = load_config()
    client = OllamaPlannerClient(model=config.model_name)
    planner = Planner(client)
    validator = Validator(config.policy)
    executor = Executor(timeout_seconds=config.timeout_seconds)

    if args.request:
        request = " ".join(args.request)
        return handle_request(request, planner, validator, executor)
    return repl(planner, validator, executor)


if __name__ == "__main__":
    raise SystemExit(main())

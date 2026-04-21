from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from collections.abc import Callable

from oterminus.audit import AuditEvent, AuditLogger
from oterminus.config import load_config
from oterminus.direct_commands import detect_direct_command
from oterminus.executor import Executor
from oterminus.logging_utils import configure_logging
from oterminus.ollama_client import OllamaClientError, OllamaPlannerClient
from oterminus.planner import Planner, PlannerError
from oterminus.setup import SetupError, ensure_startup_ready
from oterminus.policies import ConfirmationLevel, confirmation_level
from oterminus.renderer import render_preview
from oterminus.router import route_request
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



def handle_request(
    request: str,
    planner_factory: Planner | Callable[[], Planner],
    validator: Validator,
    executor: Executor,
    *,
    audit_logger: AuditLogger | None = None,
    debug_trace: bool = False,
) -> int:
    started_at = datetime.now(tz=timezone.utc)
    event = AuditEvent.start(user_input=request)
    LOGGER.info("request=%s", request)

    proposal = detect_direct_command(request)
    event.direct_command_detected = proposal is not None
    try:
        if proposal is None:
            route = route_request(request)
            event.routed_category = route.category
            if debug_trace:
                print(f"[trace] route category={route.category} confidence={route.confidence:.2f}")
            planner = planner_factory if hasattr(planner_factory, "plan") else planner_factory()
            proposal = planner.plan(request)
    except (PlannerError, OllamaClientError) as exc:
        print(f"Planning failed: {exc}")
        event.confirmation_result = "planner_error"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 2

    event.proposal_mode = proposal.mode.value
    event.command_family = proposal.command_family
    if debug_trace:
        print(f"[trace] proposal mode={proposal.mode.value} family={proposal.command_family}")

    validation = validator.validate(proposal)
    event.validation_accepted = validation.accepted
    event.warnings = list(validation.warnings)
    event.rejection_reasons = list(validation.reasons)
    event.rendered_command = validation.rendered_command
    event.argv = list(validation.argv)
    print(render_preview(proposal, validation))
    if debug_trace:
        print(
            f"[trace] validation accepted={validation.accepted} "
            f"warnings={len(validation.warnings)} rejections={len(validation.reasons)}"
        )

    if not validation.accepted:
        LOGGER.warning("proposal_rejected reasons=%s", validation.reasons)
        event.confirmation_result = "not_prompted_rejected"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 3

    confirmed = ask_confirmation(confirmation_level(proposal.mode, validation.risk_level))
    event.confirmation_result = "confirmed" if confirmed else "cancelled"
    command = validation.rendered_command
    LOGGER.info("confirmed=%s command=%s", confirmed, command)
    if debug_trace:
        print(f"[trace] confirmation={event.confirmation_result}")
    if not confirmed:
        print("Cancelled.")
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 0

    if command is None or not validation.argv:
        print("Proposal cannot be executed because it could not be rendered into a safe command.")
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 3

    try:
        result = executor.run(validation.argv, display_command=command)
    except subprocess.TimeoutExpired:
        print(f"Execution timed out after {executor.timeout_seconds}s.")
        event.execution_exit_code = 124
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 124
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Execution failed: {exc}")
        event.execution_exit_code = 1
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 1
    except KeyboardInterrupt:
        print("Execution interrupted.")
        event.execution_exit_code = 130
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 130

    print("\n--- execution output ---")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    print(f"Exit code: {result.returncode}")

    LOGGER.info("exit_code=%s", result.returncode)
    event.execution_exit_code = result.returncode
    event.duration_ms = _duration_ms_since(started_at)
    _write_audit_event(audit_logger, event)
    return result.returncode


def repl(
    planner_factory: Planner | Callable[[], Planner],
    validator: Validator,
    executor: Executor,
    *,
    audit_logger: AuditLogger | None = None,
    debug_trace: bool = False,
) -> int:
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

        handle_request(
            request,
            planner_factory,
            validator,
            executor,
            audit_logger=audit_logger,
            debug_trace=debug_trace,
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(verbose=args.verbose)

    config = load_config()
    validator = Validator(config.policy)
    executor = Executor(timeout_seconds=config.timeout_seconds)
    audit_logger = AuditLogger(config.audit_log_path)
    try:
        model_name = ensure_startup_ready()
    except SetupError as exc:
        print(exc)
        return 2

    planner: Planner | None = None

    def get_planner() -> Planner:
        nonlocal planner
        if planner is not None:
            return planner

        client = OllamaPlannerClient(model=model_name)
        planner = Planner(client)
        return planner

    if args.request:
        request = " ".join(args.request)
        return handle_request(request, get_planner, validator, executor, audit_logger=audit_logger, debug_trace=args.verbose)
    return repl(get_planner, validator, executor, audit_logger=audit_logger, debug_trace=args.verbose)


def _duration_ms_since(started_at: datetime) -> int:
    return int((datetime.now(tz=timezone.utc) - started_at).total_seconds() * 1000)


def _write_audit_event(audit_logger: AuditLogger | None, event: AuditEvent) -> None:
    if audit_logger is None:
        return
    try:
        audit_logger.write(event)
    except OSError as exc:
        LOGGER.debug("failed_to_write_audit_event error=%s", exc)


if __name__ == "__main__":
    raise SystemExit(main())

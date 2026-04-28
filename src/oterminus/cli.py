from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from collections.abc import Callable
from enum import Enum

from oterminus.audit import AuditEvent, AuditLogger
from oterminus.commands import get_command_spec
from oterminus.config import load_config
from oterminus.completion import prompt_toolkit_completer
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


class RunMode(str, Enum):
    EXECUTE = "execute"
    DRY_RUN = "dry-run"
    EXPLAIN = "explain"


_FLAG_EXPLANATIONS: dict[str, str] = {
    "-A": "show all entries/processes (often including hidden/system items)",
    "-a": "show all entries/processes (often including hidden/system items)",
    "-d": "show directory itself / use delimiter-oriented behavior depending on command",
    "-f": "use full command line or force behavior depending on command",
    "-h": "human-readable output or help depending on command",
    "-l": "long format output",
    "-n": "limit to N items/lines when paired with a value",
    "-r": "recursive processing",
    "-R": "recursive processing",
    "-s": "summary or short-name output depending on command",
    "-u": "user-oriented filtering/output depending on command",
    "-x": "stay on one filesystem or exact matching depending on command",
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="oterminus: local AI terminal assistant")
    parser.add_argument("request", nargs="*", help="Natural-language terminal request")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Plan + validate, but never execute.")
    group.add_argument("--explain", action="store_true", help="Explain command choice and safety decision, without executing.")
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
    run_mode: RunMode = RunMode.EXECUTE,
) -> int:
    started_at = datetime.now(tz=timezone.utc)
    event = AuditEvent.start(user_input=request)
    LOGGER.info("request=%s", request)

    proposal = detect_direct_command(request)
    is_direct_command = proposal is not None
    event.direct_command_detected = is_direct_command
    try:
        if proposal is None:
            route = route_request(request)
            event.routed_category = route.category
            if debug_trace:
                print(f"[trace] route category={route.category} confidence={route.confidence:.2f}")
            planner = planner_factory if hasattr(planner_factory, "plan") else planner_factory()
            proposal = planner.plan(request)
        elif debug_trace:
            print("[trace] Detected as direct shell command.")
            print("[trace] Skipped Ollama planner.")
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
    print(render_preview(proposal, validation, verbose=debug_trace, direct_command=is_direct_command))
    if debug_trace:
        if is_direct_command:
            print("[trace] Validation accepted." if validation.accepted else "[trace] Validation rejected.")
        print(
            f"[trace] validation accepted={validation.accepted} "
            f"warnings={len(validation.warnings)} rejections={len(validation.reasons)}"
        )

    if not validation.accepted:
        LOGGER.warning("proposal_rejected reasons=%s", validation.reasons)
        if run_mode == RunMode.EXPLAIN:
            print(render_explanation(proposal, validation, selected_mode=run_mode, direct_command=is_direct_command))
        event.confirmation_result = "not_prompted_rejected"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 3

    if run_mode == RunMode.DRY_RUN:
        print("Dry-run mode: execution skipped after successful planning and validation.")
        LOGGER.info("dry_run_skipped_execution command=%s", validation.rendered_command)
        event.confirmation_result = "skipped_dry_run"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 0

    if run_mode == RunMode.EXPLAIN:
        print(render_explanation(proposal, validation, selected_mode=run_mode, direct_command=is_direct_command))
        LOGGER.info("explain_mode_skipped_execution command=%s", validation.rendered_command)
        event.confirmation_result = "skipped_explain"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 0

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

    if validation.argv[0] == "clear":
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
        LOGGER.info("exit_code=%s", result.returncode)
        event.execution_exit_code = result.returncode
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return result.returncode

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
    default_run_mode: RunMode = RunMode.EXECUTE,
) -> int:
    print("oterminus REPL. Type 'help' for guidance, 'exit' or 'quit' to leave.")

    prompt_session = None
    completer = prompt_toolkit_completer()
    if completer is not None:
        try:
            from prompt_toolkit import PromptSession

            prompt_session = PromptSession(completer=completer)
        except ImportError:
            prompt_session = None

    while True:
        try:
            if prompt_session is None:
                request = input("oterminus> ").strip()
            else:
                request = prompt_session.prompt("oterminus> ").strip()
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
                "Examples: 'find all .py files', 'ls -lh', 'cd src'\n"
                "Built-ins: dry-run <request>, explain <request>, help, exit, quit"
            )
            continue

        run_mode = default_run_mode
        lowered = request.lower()
        if lowered.startswith("dry-run "):
            run_mode = RunMode.DRY_RUN
            request = request[8:].strip()
        elif lowered.startswith("explain "):
            run_mode = RunMode.EXPLAIN
            request = request[8:].strip()
        if not request:
            print("Please provide a request after the REPL command prefix.")
            continue

        handle_request(
            request,
            planner_factory,
            validator,
            executor,
            audit_logger=audit_logger,
            debug_trace=debug_trace,
            run_mode=run_mode,
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(verbose=args.verbose)
    run_mode = _run_mode_from_args(args)

    config = load_config()
    validator = Validator(config.policy)
    executor = Executor(timeout_seconds=config.timeout_seconds)
    audit_logger = AuditLogger(config.audit_log_path)
    planner: Planner | None = None
    model_name: str | None = None

    def ensure_planner_ready() -> str:
        nonlocal model_name
        if model_name is not None:
            return model_name
        model_name = ensure_startup_ready()
        return model_name

    def get_planner() -> Planner:
        nonlocal planner
        if planner is not None:
            return planner

        selected_model = ensure_planner_ready()
        client = OllamaPlannerClient(model=selected_model)
        planner = Planner(client)
        return planner

    if args.request:
        request = " ".join(args.request)
        direct = detect_direct_command(request) is not None
        if not direct:
            try:
                ensure_planner_ready()
            except SetupError as exc:
                print(exc)
                return 2
        return handle_request(
            request,
            get_planner,
            validator,
            executor,
            audit_logger=audit_logger,
            debug_trace=args.verbose,
            run_mode=run_mode,
        )
    try:
        ensure_planner_ready()
    except SetupError as exc:
        print(exc)
        return 2
    return repl(
        get_planner,
        validator,
        executor,
        audit_logger=audit_logger,
        debug_trace=args.verbose,
        default_run_mode=run_mode,
    )


def _duration_ms_since(started_at: datetime) -> int:
    return int((datetime.now(tz=timezone.utc) - started_at).total_seconds() * 1000)


def _run_mode_from_args(args: argparse.Namespace) -> RunMode:
    if args.dry_run:
        return RunMode.DRY_RUN
    if args.explain:
        return RunMode.EXPLAIN
    return RunMode.EXECUTE


def render_explanation(proposal, validation, *, selected_mode: RunMode, direct_command: bool) -> str:
    command = validation.rendered_command or proposal.command or "(unavailable)"
    family = proposal.command_family or "(unknown)"
    spec = get_command_spec(family) if proposal.command_family else None
    lines = [
        "--- oterminus explanation ---",
        f"Selected mode : {selected_mode.value}",
        f"Proposal mode : {proposal.mode.value}",
        f"Direct input  : {'yes' if direct_command else 'no'}",
        f"Command family: {family}",
        f"Rendered cmd  : {command}",
        f"Risk level    : {validation.risk_level.value}",
    ]
    if spec is not None:
        lines.append(f"Family domain : {spec.capability_id} ({spec.capability_label})")

    flag_notes = _describe_flags(validation.argv)
    if flag_notes:
        lines.append("Flags         : " + "; ".join(flag_notes))

    if validation.warnings:
        lines.append("Warnings      : " + "; ".join(validation.warnings))

    if validation.accepted:
        lines.append("Policy        : Allowed by current policy checks.")
        lines.append("Execution     : Blocked by explain mode (intentionally not executed).")
    else:
        lines.append("Policy        : Blocked by current policy checks.")
        if validation.reasons:
            lines.append("Rejections    : " + "; ".join(validation.reasons))
        lines.append("Execution     : Not executable due to validation failure.")

    return "\n".join(lines)


def _describe_flags(argv: list[str]) -> list[str]:
    descriptions: list[str] = []
    for token in argv[1:]:
        if not token.startswith("-"):
            continue
        key = token.split("=", 1)[0]
        if key in _FLAG_EXPLANATIONS:
            descriptions.append(f"{key}: {_FLAG_EXPLANATIONS[key]}")
            continue
        if key.startswith("--"):
            descriptions.append(f"{key}: long-form option")
        elif key.startswith("-") and len(key) > 2:
            short_keys = [f"-{short_flag}" for short_flag in key[1:]]
            if not all(short_key in _FLAG_EXPLANATIONS for short_key in short_keys):
                continue
            for short_key in short_keys:
                descriptions.append(f"{short_key}: {_FLAG_EXPLANATIONS[short_key]}")
    return sorted(set(descriptions))


def _write_audit_event(audit_logger: AuditLogger | None, event: AuditEvent) -> None:
    if audit_logger is None:
        return
    try:
        audit_logger.write(event)
    except OSError as exc:
        LOGGER.debug("failed_to_write_audit_event error=%s", exc)


if __name__ == "__main__":
    raise SystemExit(main())

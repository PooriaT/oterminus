from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from collections.abc import Callable
from enum import Enum

from oterminus.ambiguity import AmbiguityResult, detect_ambiguity
from oterminus.audit import AuditEvent, AuditLogger
from oterminus.commands import get_command_spec, supported_capabilities
from oterminus.discovery import (
    render_capabilities,
    render_capability_help,
    render_command_help,
    render_commands,
    render_examples,
    render_help,
    render_help_capabilities,
    render_unknown_help_target,
    render_examples_for_capability,
)
from oterminus.config import load_config
from oterminus.completion import get_completion_backend_status
from oterminus.direct_commands import detect_direct_command
from oterminus.history import PersistentHistoryStore, SessionHistory
from oterminus.doctor import print_report, run_doctor
from oterminus.executor import Executor
from oterminus.failure_explainer import FailureExplainer
from oterminus.logging_utils import configure_logging
from oterminus.ollama_client import OllamaClientError, OllamaPlannerClient
from oterminus.planner import Planner, PlannerError
from oterminus.setup import SetupError, ensure_startup_ready
from oterminus.policies import ConfirmationLevel, confirmation_level
from oterminus.renderer import render_failure_explanation, render_preview
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
    group.add_argument(
        "--explain",
        action="store_true",
        help="Explain command choice and safety decision, without executing.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args(argv)
    args.cli_mode = _cli_mode_from_request(args.request)
    if args.cli_mode == "doctor" and (args.dry_run or args.explain):
        parser.error("doctor cannot be combined with --dry-run or --explain")
    return args


def _cli_mode_from_request(request: list[str]) -> str:
    return "doctor" if " ".join(request).strip().lower() == "doctor" else "request"


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
    session_history: SessionHistory | None = None,
    rerun_source_history_id: int | None = None,
    persistent_store: PersistentHistoryStore | None = None,
    disabled_pack_ids: frozenset[str] | None = None,
    failure_explainer: FailureExplainer | None = None,
    failure_explainer_factory: Callable[[], FailureExplainer] | None = None,
) -> int:
    started_at = datetime.now(tz=timezone.utc)
    event = AuditEvent.start(user_input=request)
    event.rerun_source_history_id = rerun_source_history_id
    LOGGER.info("request=%s", request)
    history_item = session_history.start(request) if session_history is not None else None

    def _persist_if_needed() -> None:
        if history_item is not None and persistent_store is not None:
            persistent_store.append(history_item)

    effective_disabled_pack_ids = (
        disabled_pack_ids
        if disabled_pack_ids is not None
        else getattr(validator.policy, "disabled_command_packs", frozenset())
    )

    proposal = detect_direct_command(request, disabled_pack_ids=effective_disabled_pack_ids)
    is_direct_command = proposal is not None
    event.direct_command_detected = is_direct_command
    if history_item is not None:
        history_item.direct_command_detected = is_direct_command
        history_item.execution_status = "planning"
    try:
        if proposal is None:
            ambiguity = detect_ambiguity(request)
            event.ambiguity_detected = ambiguity.is_ambiguous
            event.ambiguity_reason = ambiguity.reason if ambiguity.is_ambiguous else None
            event.ambiguity_safe_options = (
                list(ambiguity.suggested_safe_options) if ambiguity.is_ambiguous else []
            )
            if ambiguity.is_ambiguous:
                print(render_ambiguity_response(ambiguity))
                if history_item is not None:
                    history_item.execution_status = "blocked_ambiguous"
                event.confirmation_result = "blocked_ambiguous"
                event.duration_ms = _duration_ms_since(started_at)
                _write_audit_event(audit_logger, event)
                _persist_if_needed()
                return 0
            route = route_request(request)
            event.routed_category = route.category
            if history_item is not None:
                history_item.routed_category = route.category
            if debug_trace:
                print(f"[trace] route category={route.category} confidence={route.confidence:.2f}")
            planner = planner_factory if hasattr(planner_factory, "plan") else planner_factory()
            proposal = planner.plan(request)
        elif debug_trace:
            print("[trace] Detected as direct shell command.")
            print("[trace] Skipped Ollama planner.")
    except (PlannerError, OllamaClientError, SetupError) as exc:
        print(f"Planning failed: {exc}")
        if history_item is not None:
            history_item.execution_status = "planner_error"
        event.confirmation_result = "planner_error"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        _persist_if_needed()
        return 2

    event.proposal_mode = proposal.mode.value
    event.command_family = proposal.command_family
    if history_item is not None:
        history_item.proposal_mode = proposal.mode.value
        history_item.command_family = proposal.command_family
        history_item.proposal = proposal
    if debug_trace:
        print(f"[trace] proposal mode={proposal.mode.value} family={proposal.command_family}")

    validation = validator.validate(proposal)
    event.validation_accepted = validation.accepted
    event.warnings = list(validation.warnings)
    event.rejection_reasons = list(validation.reasons)
    event.rendered_command = validation.rendered_command
    event.argv = list(validation.argv)
    if history_item is not None:
        history_item.rendered_command = validation.rendered_command
        history_item.risk_level = validation.risk_level.value
        history_item.validation_status = "accepted" if validation.accepted else "rejected"
        history_item.validation = validation
    print(
        render_preview(proposal, validation, verbose=debug_trace, direct_command=is_direct_command)
    )
    if debug_trace:
        if is_direct_command:
            print(
                "[trace] Validation accepted."
                if validation.accepted
                else "[trace] Validation rejected."
            )
        print(
            f"[trace] validation accepted={validation.accepted} "
            f"warnings={len(validation.warnings)} rejections={len(validation.reasons)}"
        )

    if not validation.accepted:
        LOGGER.warning("proposal_rejected reasons=%s", validation.reasons)
        if run_mode == RunMode.EXPLAIN:
            print(
                render_explanation(
                    proposal, validation, selected_mode=run_mode, direct_command=is_direct_command
                )
            )
        if history_item is not None:
            history_item.execution_status = "rejected"
        event.confirmation_result = "not_prompted_rejected"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        _persist_if_needed()
        return 3

    if run_mode == RunMode.DRY_RUN:
        print("Dry-run mode: execution skipped after successful planning and validation.")
        LOGGER.info("dry_run_skipped_execution command=%s", validation.rendered_command)
        if history_item is not None:
            history_item.execution_status = "skipped_dry_run"
        event.confirmation_result = "skipped_dry_run"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        _persist_if_needed()
        return 0

    if run_mode == RunMode.EXPLAIN:
        print(
            render_explanation(
                proposal, validation, selected_mode=run_mode, direct_command=is_direct_command
            )
        )
        LOGGER.info("explain_mode_skipped_execution command=%s", validation.rendered_command)
        if history_item is not None:
            history_item.execution_status = "skipped_explain"
        event.confirmation_result = "skipped_explain"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        _persist_if_needed()
        return 0

    confirmed = ask_confirmation(confirmation_level(proposal.mode, validation.risk_level))
    event.confirmation_result = "confirmed" if confirmed else "cancelled"
    command = validation.rendered_command
    LOGGER.info("confirmed=%s command=%s", confirmed, command)
    if debug_trace:
        print(f"[trace] confirmation={event.confirmation_result}")
    if not confirmed:
        print("Cancelled.")
        if history_item is not None:
            history_item.execution_status = "cancelled"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        _persist_if_needed()
        return 0

    if command is None or not validation.argv:
        print("Proposal cannot be executed because it could not be rendered into a safe command.")
        if history_item is not None:
            history_item.execution_status = "not_executable"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        _persist_if_needed()
        return 3

    try:
        result = executor.run(validation.argv, display_command=command)
    except subprocess.TimeoutExpired:
        print(f"Execution timed out after {executor.timeout_seconds}s.")
        if history_item is not None:
            history_item.execution_status = "timed_out"
            history_item.exit_code = 124
        event.execution_exit_code = 124
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 124
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Execution failed: {exc}")
        if history_item is not None:
            history_item.execution_status = "execution_failed"
            history_item.exit_code = 1
        event.execution_exit_code = 1
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 1
    except KeyboardInterrupt:
        print("Execution interrupted.")
        if history_item is not None:
            history_item.execution_status = "interrupted"
            history_item.exit_code = 130
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
        if history_item is not None:
            history_item.execution_status = "executed"
            history_item.exit_code = result.returncode
        event.execution_exit_code = result.returncode
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return result.returncode

    print("\n--- execution output ---")
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    max_output_chars = getattr(executor, "max_output_chars", 20000)
    if bool(getattr(result, "stdout_truncated", False)):
        print(f"[oterminus] stdout truncated to {max_output_chars} characters.")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if bool(getattr(result, "stderr_truncated", False)):
        print(f"[oterminus] stderr truncated to {max_output_chars} characters.")
    print(f"Exit code: {result.returncode}")

    if result.returncode != 0 and (failure_explainer is not None or failure_explainer_factory is not None):
        event.failure_explanation_requested = True
        try:
            active_failure_explainer = failure_explainer
            if active_failure_explainer is None and failure_explainer_factory is not None:
                active_failure_explainer = failure_explainer_factory()
            if active_failure_explainer is not None:
                explanation = active_failure_explainer.explain(
                    command=command,
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                event.failure_explanation_generated = True
                event.failure_suggested_next_action = explanation.suggested_next_action
                event.failure_stderr_summary = explanation.stderr_summary
                print(render_failure_explanation(explanation))
        except Exception as exc:  # noqa: BLE001
            event.failure_explanation_error = str(exc)

    LOGGER.info("exit_code=%s", result.returncode)
    if history_item is not None:
        history_item.execution_status = "executed"
        history_item.exit_code = result.returncode
    event.execution_exit_code = result.returncode
    event.stdout_truncated = bool(getattr(result, "stdout_truncated", False))
    event.stderr_truncated = bool(getattr(result, "stderr_truncated", False))
    stdout_original_chars = getattr(result, "stdout_original_chars", None)
    stderr_original_chars = getattr(result, "stderr_original_chars", None)
    event.stdout_original_chars = (
        stdout_original_chars if isinstance(stdout_original_chars, int) else len(result.stdout)
    )
    event.stderr_original_chars = (
        stderr_original_chars if isinstance(stderr_original_chars, int) else len(result.stderr)
    )
    event.stdout_visible_chars = len(result.stdout)
    event.stderr_visible_chars = len(result.stderr)
    event.duration_ms = _duration_ms_since(started_at)
    _write_audit_event(audit_logger, event)
    _persist_if_needed()
    return result.returncode


def repl(
    planner_factory: Planner | Callable[[], Planner],
    validator: Validator,
    executor: Executor,
    *,
    audit_logger: AuditLogger | None = None,
    audit_enabled: bool = True,
    debug_trace: bool = False,
    default_run_mode: RunMode = RunMode.EXECUTE,
    persistent_store: PersistentHistoryStore | None = None,
    disabled_pack_ids: frozenset[str] | None = None,
    failure_explainer: FailureExplainer | None = None,
    failure_explainer_factory: Callable[[], FailureExplainer] | None = None,
) -> int:
    print("oterminus REPL. Type 'help' for guidance, 'exit' or 'quit' to leave.")
    session_history = SessionHistory()
    if persistent_store is not None:
        for item in persistent_store.load():
            session_history.add_persisted(item)

    effective_disabled_pack_ids = (
        disabled_pack_ids
        if disabled_pack_ids is not None
        else getattr(validator.policy, "disabled_command_packs", frozenset())
    )

    try:
        prompt_session, backend_name = create_prompt_session(
            disabled_pack_ids=effective_disabled_pack_ids
        )
    except TypeError:
        prompt_session, backend_name = create_prompt_session()
    if debug_trace:
        if backend_name == "prompt_toolkit":
            print("[trace] prompt_toolkit completion enabled")
        else:
            print("[trace] prompt_toolkit unavailable; falling back to plain input()")

    while True:
        try:
            request = read_repl_input(prompt_session).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not request:
            continue
        if request.lower() in {"exit", "quit"}:
            return 0
        audit_response = handle_audit_command(
            request, audit_logger=audit_logger, audit_enabled=audit_enabled
        )
        if audit_response is not None:
            print(audit_response)
            continue
        discovery_response = handle_repl_discovery_command(request)
        if discovery_response is not None:
            print(discovery_response)
            continue
        history_response = handle_repl_history_command(
            request,
            session_history=session_history,
            planner_factory=planner_factory,
            validator=validator,
            executor=executor,
            audit_logger=audit_logger,
            debug_trace=debug_trace,
            persistent_store=persistent_store,
            failure_explainer=failure_explainer,
            failure_explainer_factory=failure_explainer_factory,
        )
        if history_response is not None:
            if isinstance(history_response, str):
                print(history_response)
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
            session_history=session_history,
            persistent_store=persistent_store,
            disabled_pack_ids=disabled_pack_ids,
            failure_explainer=failure_explainer,
            failure_explainer_factory=failure_explainer_factory,
        )


def create_prompt_session(
    *, disabled_pack_ids: frozenset[str] | None = None
) -> tuple[object | None, str]:
    try:
        backend_name, completer = get_completion_backend_status(disabled_pack_ids=disabled_pack_ids)
    except TypeError:
        backend_name, completer = get_completion_backend_status()
    if completer is None:
        return None, backend_name
    try:
        from prompt_toolkit import PromptSession
    except ImportError:
        return None, "plain_input"
    return PromptSession(completer=completer), backend_name


def read_repl_input(prompt_session: object | None) -> str:
    if prompt_session is None:
        return input("oterminus> ")
    return prompt_session.prompt("oterminus> ")


def handle_repl_discovery_command(request: str) -> str | None:
    lowered = request.lower().strip()
    capabilities = supported_capabilities()
    capability_map = {capability.capability_id: capability for capability in capabilities}

    if lowered == "help":
        return render_help()

    if lowered == "capabilities":
        return render_capabilities()

    if lowered == "commands":
        return render_commands()

    if lowered == "examples":
        return render_examples()

    if lowered.startswith("examples "):
        target = lowered.split(maxsplit=1)[1]
        if target not in capability_map:
            return render_unknown_help_target(target)
        return render_examples_for_capability(target)

    if lowered == "help capabilities":
        return render_help_capabilities()

    if lowered.startswith("help "):
        target = lowered.split(maxsplit=1)[1]
        if target in capability_map:
            return render_capability_help(target)
        if get_command_spec(target) is not None:
            return render_command_help(target)
        return render_unknown_help_target(target)

    return None


def handle_repl_history_command(
    request: str,
    *,
    session_history: SessionHistory,
    planner_factory: Planner | Callable[[], Planner],
    validator: Validator,
    executor: Executor,
    audit_logger: AuditLogger | None,
    debug_trace: bool,
    persistent_store: PersistentHistoryStore | None = None,
    failure_explainer: FailureExplainer | None = None,
    failure_explainer_factory: Callable[[], FailureExplainer] | None = None,
) -> str | None:
    lowered = request.lower().strip()
    if lowered == "history":
        return session_history.render_table()

    if lowered == "history session":
        return session_history.render_table(source="session")

    if lowered == "history persisted":
        return session_history.render_table(source="persisted")

    if lowered.startswith("history "):
        count = _parse_positive_int(lowered.split(maxsplit=1)[1])
        if count is None:
            return "Usage: history | history <n>"
        return session_history.render_table(limit=count)

    if lowered.startswith("explain "):
        explain_target = request.strip().split(maxsplit=1)[1].strip()
        history_id = _parse_positive_int(explain_target)
        if history_id is None:
            if _looks_like_history_id(explain_target):
                return "Usage: explain <history_id> | explain <request>"
            return None
        return _render_history_explanation(session_history, history_id)

    if lowered.startswith("rerun "):
        history_id = _parse_positive_int(lowered.split(maxsplit=1)[1])
        if history_id is None:
            return "Usage: rerun <history_id>"
        history_item = session_history.find(history_id)
        if history_item is None:
            return f"History id {history_id} not found."
        handle_request(
            history_item.user_input,
            planner_factory,
            validator,
            executor,
            audit_logger=audit_logger,
            debug_trace=debug_trace,
            run_mode=RunMode.EXECUTE,
            session_history=session_history,
            rerun_source_history_id=(
                history_item.persisted_id if history_item.source == "persisted" else history_id
            ),
            persistent_store=persistent_store,
            failure_explainer=failure_explainer,
            failure_explainer_factory=failure_explainer_factory,
        )
        return ""
    return None


def _render_history_explanation(session_history: SessionHistory, history_id: int) -> str:
    history_item = session_history.find(history_id)
    if history_item is None:
        return f"History id {history_id} not found."

    if history_item.proposal is None or history_item.validation is None:
        return (
            f"History id {history_id} has limited details.\n"
            f"Input: {history_item.user_input}\n"
            f"Status: {history_item.execution_status}"
        )
    return render_explanation(
        history_item.proposal,
        history_item.validation,
        selected_mode=RunMode.EXPLAIN,
        direct_command=history_item.direct_command_detected,
    )


def run_doctor_cli() -> int:
    report = run_doctor()
    print_report(report)
    return report.exit_code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(verbose=args.verbose)
    run_mode = _run_mode_from_args(args)

    if args.cli_mode == "doctor":
        return run_doctor_cli()

    config = load_config()
    validator = Validator(config.policy)
    try:
        executor = Executor(
            timeout_seconds=config.timeout_seconds,
            max_output_chars=getattr(config, "max_output_chars", 20000),
        )
    except TypeError:
        executor = Executor(timeout_seconds=config.timeout_seconds)
    audit_logger = (
        AuditLogger(config.audit_log_path, redact=config.audit_redact)
        if config.audit_enabled
        else None
    )
    planner: Planner | None = None
    model_name: str | None = None
    failure_explainer: FailureExplainer | None = None
    failure_explainer_factory: Callable[[], FailureExplainer] | None = None
    raw_history_path = getattr(config, "history_path", Path.home() / ".oterminus" / "history.jsonl")
    if isinstance(raw_history_path, Path):
        history_path = raw_history_path
    elif isinstance(raw_history_path, str):
        history_path = Path(raw_history_path).expanduser()
    else:
        history_path = Path.home() / ".oterminus" / "history.jsonl"
    raw_history_limit = getattr(config, "history_limit", 100)
    history_limit = raw_history_limit if isinstance(raw_history_limit, int) else 100
    persistent_store = PersistentHistoryStore(
        history_path,
        enabled=bool(getattr(config, "history_enabled", False)),
        limit=history_limit,
        redact=bool(getattr(config, "history_redact", getattr(config, "audit_redact", True))),
    )

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

        try:
            planner = Planner(client, policy=config.policy)
        except TypeError:
            planner = Planner(client)
        return planner

    if args.request:
        request = " ".join(args.request)
        audit_response = handle_audit_command(
            request, audit_logger=audit_logger, audit_enabled=config.audit_enabled
        )
        if audit_response is not None:
            print(audit_response)
            return 0
        explain_failures_enabled = getattr(config, "explain_failures", False) is True
        if explain_failures_enabled:
            def get_failure_explainer() -> FailureExplainer:
                nonlocal failure_explainer
                if failure_explainer is not None:
                    return failure_explainer
                failure_explainer = FailureExplainer(
                    OllamaPlannerClient(model=ensure_planner_ready()),
                    max_chars=getattr(config, "failure_explanation_max_chars", 4000),
                )
                return failure_explainer

            failure_explainer_factory = get_failure_explainer
        return handle_request(
            request,
            get_planner,
            validator,
            executor,
            audit_logger=audit_logger,
            debug_trace=args.verbose,
            run_mode=run_mode,
            persistent_store=persistent_store,
            disabled_pack_ids=validator.policy.disabled_command_packs,
            failure_explainer=failure_explainer,
            failure_explainer_factory=failure_explainer_factory,
        )
    return repl(
        get_planner,
        validator,
        executor,
        audit_logger=audit_logger,
        audit_enabled=config.audit_enabled,
        debug_trace=args.verbose,
        default_run_mode=run_mode,
        persistent_store=persistent_store,
        disabled_pack_ids=validator.policy.disabled_command_packs,
        failure_explainer=failure_explainer,
        failure_explainer_factory=failure_explainer_factory,
    )


def _duration_ms_since(started_at: datetime) -> int:
    return int((datetime.now(tz=timezone.utc) - started_at).total_seconds() * 1000)


def _truncate(value: str, width: int) -> str:
    value = " ".join(value.split())
    if len(value) <= width:
        return value
    return value[: width - 1] + "…"


def _parse_positive_int(raw: str) -> int | None:
    try:
        parsed = int(raw.strip())
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _looks_like_history_id(raw: str) -> bool:
    candidate = raw.strip()
    if not candidate:
        return False
    if candidate[0] in "+-":
        return candidate[1:].isdigit()
    return candidate.isdigit()


def _run_mode_from_args(args: argparse.Namespace) -> RunMode:
    if args.dry_run:
        return RunMode.DRY_RUN
    if args.explain:
        return RunMode.EXPLAIN
    return RunMode.EXECUTE


def render_explanation(
    proposal, validation, *, selected_mode: RunMode, direct_command: bool
) -> str:
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


def render_audit_status(audit_logger: AuditLogger | None, *, enabled: bool = True) -> str:
    lines = [f"audit enabled: {'yes' if enabled else 'no'}"]
    if not enabled:
        lines.append("audit logging is disabled by OTERMINUS_AUDIT_ENABLED=false")
        return "\n".join(lines)
    if audit_logger is None:
        lines.append("audit logger unavailable")
        return "\n".join(lines)
    details = audit_logger.status()
    lines.append(f"audit log path: {details['path']}")
    lines.append(f"log file exists: {'true' if details['exists'] == 'yes' else 'false'}")
    lines.append(f"redaction enabled: {'true' if audit_logger.redact else 'false'}")
    return "\n".join(lines)


def handle_audit_command(
    request: str, *, audit_logger: AuditLogger | None, audit_enabled: bool
) -> str | None:
    lowered = request.lower().strip()
    if lowered == "audit status":
        return render_audit_status(audit_logger, enabled=audit_enabled)
    if lowered.startswith("audit tail"):
        return render_audit_tail(request, audit_logger=audit_logger, enabled=audit_enabled)
    if lowered == "audit clear":
        return clear_audit_log(audit_logger, enabled=audit_enabled)
    return None


def render_audit_tail(request: str, *, audit_logger: AuditLogger | None, enabled: bool) -> str:
    if not enabled or audit_logger is None:
        return "Audit logging is disabled."
    parts = request.strip().split()
    limit = 10
    if len(parts) == 3:
        parsed = _parse_positive_int(parts[2])
        if parsed is None:
            return "Usage: audit tail [n]"
        limit = parsed
    elif len(parts) > 3:
        return "Usage: audit tail [n]"

    path = audit_logger.path
    if not path.exists():
        return f"Audit log not found at {path}."
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return f"Unable to read audit log at {path}: {exc.strerror or exc.__class__.__name__}."
    if not lines:
        return "Audit log is empty."
    selected = lines[-limit:]
    output = [f"Showing {len(selected)} most recent audit event(s):"]
    for raw in selected:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            output.append(f"- {raw}")
            continue
        timestamp = event.get("timestamp", "?")
        user_input = event.get("user_input", "")
        confirmation_result = event.get("confirmation_result")
        exit_code = event.get("execution_exit_code")
        output.append(
            f"- {timestamp} | input={user_input!r} | confirmation={confirmation_result} | exit={exit_code}"
        )
    return "\n".join(output)


def clear_audit_log(audit_logger: AuditLogger | None, *, enabled: bool) -> str:
    if not enabled or audit_logger is None:
        return "Audit logging is disabled."
    path = audit_logger.path
    if not path.exists():
        return f"Audit log not found at {path}."
    answer = input("Type CLEAR AUDIT to delete the local audit log: ").strip()
    if answer != "CLEAR AUDIT":
        return "Audit clear cancelled."
    try:
        path.write_text("", encoding="utf-8")
    except OSError as exc:
        return f"Unable to clear audit log at {path}: {exc.strerror or exc.__class__.__name__}."
    return f"Cleared audit log at {path}."


def render_ambiguity_response(result: AmbiguityResult) -> str:
    lines = ["This request is ambiguous."]
    if result.reason:
        lines.append(f"Reason: {result.reason}")
    lines.append("Safer inspections I can do instead:")
    lines.extend(f"- {option}" for option in result.suggested_safe_options)
    if result.follow_up_questions:
        lines.append("Helpful clarifying questions:")
        lines.extend(f"- {question}" for question in result.follow_up_questions)
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

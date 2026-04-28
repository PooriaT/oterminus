from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from collections.abc import Callable
from enum import Enum

from oterminus.ambiguity import AmbiguityResult, detect_ambiguity
from oterminus.audit import AuditEvent, AuditLogger
from oterminus.commands import get_command_spec, supported_capabilities
from oterminus.commands.types import MaturityLevel
from oterminus.config import load_config
from oterminus.completion import prompt_toolkit_completer
from oterminus.direct_commands import detect_direct_command
from oterminus.doctor import print_report, run_doctor
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


@dataclass
class SessionHistoryItem:
    id: int
    user_input: str
    direct_command_detected: bool = False
    routed_category: str | None = None
    proposal_mode: str | None = None
    command_family: str | None = None
    rendered_command: str | None = None
    risk_level: str | None = None
    validation_status: str | None = None
    execution_status: str = "pending"
    exit_code: int | None = None
    proposal: object | None = None
    validation: object | None = None


class SessionHistory:
    def __init__(self) -> None:
        self._items: list[SessionHistoryItem] = []
        self._next_id = 1

    def start(self, user_input: str) -> SessionHistoryItem:
        item = SessionHistoryItem(id=self._next_id, user_input=user_input)
        self._next_id += 1
        self._items.append(item)
        return item

    def all_items(self) -> list[SessionHistoryItem]:
        return list(self._items)

    def find(self, history_id: int) -> SessionHistoryItem | None:
        for item in self._items:
            if item.id == history_id:
                return item
        return None

    def render_table(self, limit: int | None = None) -> str:
        items = self._items if limit is None else self._items[-limit:]
        if not items:
            return "No session history yet."

        rows = [
            (
                str(item.id),
                _truncate(item.user_input, 34),
                _truncate(item.rendered_command or "(none)", 34),
                item.risk_level or "-",
                item.execution_status,
            )
            for item in items
        ]
        headers = ("id", "input", "command", "risk", "status")
        widths = [
            max(len(headers[idx]), *(len(row[idx]) for row in rows))
            for idx in range(len(headers))
        ]

        def _line(values: tuple[str, ...]) -> str:
            return "  ".join(value.ljust(widths[idx]) for idx, value in enumerate(values))

        output = [_line(headers), _line(tuple("-" * width for width in widths))]
        output.extend(_line(row) for row in rows)
        return "\n".join(output)


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
    session_history: SessionHistory | None = None,
    rerun_source_history_id: int | None = None,
) -> int:
    started_at = datetime.now(tz=timezone.utc)
    event = AuditEvent.start(user_input=request)
    event.rerun_source_history_id = rerun_source_history_id
    LOGGER.info("request=%s", request)
    history_item = session_history.start(request) if session_history is not None else None

    proposal = detect_direct_command(request)
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
            event.ambiguity_safe_options = list(ambiguity.suggested_safe_options) if ambiguity.is_ambiguous else []
            if ambiguity.is_ambiguous:
                print(render_ambiguity_response(ambiguity))
                if history_item is not None:
                    history_item.execution_status = "blocked_ambiguous"
                event.confirmation_result = "blocked_ambiguous"
                event.duration_ms = _duration_ms_since(started_at)
                _write_audit_event(audit_logger, event)
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
    except (PlannerError, OllamaClientError) as exc:
        print(f"Planning failed: {exc}")
        if history_item is not None:
            history_item.execution_status = "planner_error"
        event.confirmation_result = "planner_error"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
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
        if history_item is not None:
            history_item.execution_status = "rejected"
        event.confirmation_result = "not_prompted_rejected"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 3

    if run_mode == RunMode.DRY_RUN:
        print("Dry-run mode: execution skipped after successful planning and validation.")
        LOGGER.info("dry_run_skipped_execution command=%s", validation.rendered_command)
        if history_item is not None:
            history_item.execution_status = "skipped_dry_run"
        event.confirmation_result = "skipped_dry_run"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 0

    if run_mode == RunMode.EXPLAIN:
        print(render_explanation(proposal, validation, selected_mode=run_mode, direct_command=is_direct_command))
        LOGGER.info("explain_mode_skipped_execution command=%s", validation.rendered_command)
        if history_item is not None:
            history_item.execution_status = "skipped_explain"
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
        if history_item is not None:
            history_item.execution_status = "cancelled"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
        return 0

    if command is None or not validation.argv:
        print("Proposal cannot be executed because it could not be rendered into a safe command.")
        if history_item is not None:
            history_item.execution_status = "not_executable"
        event.duration_ms = _duration_ms_since(started_at)
        _write_audit_event(audit_logger, event)
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
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    print(f"Exit code: {result.returncode}")

    LOGGER.info("exit_code=%s", result.returncode)
    if history_item is not None:
        history_item.execution_status = "executed"
        history_item.exit_code = result.returncode
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
    audit_enabled: bool = True,
    debug_trace: bool = False,
    default_run_mode: RunMode = RunMode.EXECUTE,
) -> int:
    print("oterminus REPL. Type 'help' for guidance, 'exit' or 'quit' to leave.")
    session_history = SessionHistory()

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
        if request.lower().strip() == "audit status":
            print(render_audit_status(audit_logger, enabled=audit_enabled))
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
        )


def handle_repl_discovery_command(request: str) -> str | None:
    lowered = request.lower().strip()
    capabilities = supported_capabilities()
    capability_map = {capability.capability_id: capability for capability in capabilities}

    if lowered == "help":
        return (
            "Enter either a natural-language terminal request or a direct shell command.\n"
            "Examples: 'find all .py files', 'ls -lh', 'cd src'\n"
            "Built-ins: help, capabilities, commands, examples, history, history <n>, explain <request>, explain <history_id>, rerun <history_id>, dry-run <request>, audit status, exit, quit\n"
            "Try: help capabilities | help <capability_id> | help <command_family> | examples <capability_id>"
        )

    if lowered == "capabilities":
        lines = ["Supported capabilities:"]
        lines.extend(f"- {capability.capability_id}: {capability.capability_label}" for capability in capabilities)
        return "\n".join(lines)

    if lowered == "commands":
        lines = ["Supported command families by capability:"]
        for capability in capabilities:
            lines.append(f"- {capability.capability_id}: {', '.join(capability.commands)}")
        return "\n".join(lines)

    if lowered == "examples":
        return _render_examples_by_capability()

    if lowered.startswith("examples "):
        target = lowered.split(maxsplit=1)[1]
        if target not in capability_map:
            return _unknown_help_target(target)
        return _render_examples_for_capability(target)

    if lowered == "help capabilities":
        return (
            "OTerminus is capability-first: command families are grouped by workflow capability.\n"
            "The command registry answers both: which command families are allowed and which workflow they belong to.\n"
            "Maturity levels: structured, direct-only, and experimental-only."
        )

    if lowered.startswith("help "):
        target = lowered.split(maxsplit=1)[1]
        if target in capability_map:
            return _render_capability_help(target)
        if get_command_spec(target) is not None:
            return _render_command_family_help(target)
        return _unknown_help_target(target)

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
) -> str | None:
    lowered = request.lower().strip()
    if lowered == "history":
        return session_history.render_table()

    if lowered.startswith("history "):
        count = _parse_positive_int(lowered.split(maxsplit=1)[1])
        if count is None:
            return "Usage: history | history <n>"
        return session_history.render_table(limit=count)

    if lowered.startswith("explain "):
        history_id = _parse_positive_int(lowered.split(maxsplit=1)[1])
        if history_id is None:
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
            rerun_source_history_id=history_id,
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


def _render_capability_help(capability_id: str) -> str:
    capability = next(item for item in supported_capabilities() if item.capability_id == capability_id)
    lines = [
        f"Capability: {capability.capability_id}",
        f"Label: {capability.capability_label}",
        f"Description: {capability.capability_description}",
        f"Maturity in registry: {', '.join(capability.maturity_levels)}",
        f"Supported command families: {', '.join(capability.commands)}",
        "Example requests:",
    ]
    for command_name in capability.commands:
        spec = get_command_spec(command_name)
        if spec is not None and spec.examples:
            lines.append(f"- {spec.examples[0]}")
    return "\n".join(lines)


def _render_command_family_help(command_family: str) -> str:
    spec = get_command_spec(command_family)
    if spec is None:
        return _unknown_help_target(command_family)

    lines = [
        f"Command family: {spec.name}",
        f"Capability: {spec.capability_id} ({spec.capability_label})",
        f"Risk level: {spec.risk_level.value}",
        f"Maturity: {_maturity_label(spec.maturity_level)}",
    ]
    if spec.examples:
        lines.append("Examples:")
        lines.extend(f"- {example}" for example in spec.examples)
    if spec.notes:
        lines.append("Warnings / notes:")
        lines.extend(f"- {note}" for note in spec.notes)
    return "\n".join(lines)


def _render_examples_by_capability() -> str:
    lines = ["Common example requests by capability:"]
    for capability in supported_capabilities():
        samples: list[str] = []
        for command_name in capability.commands:
            spec = get_command_spec(command_name)
            if spec is None or not spec.examples:
                continue
            samples.append(spec.examples[0])
            if len(samples) >= 2:
                break
        if samples:
            lines.append(f"- {capability.capability_id}: {' | '.join(samples)}")
    return "\n".join(lines)


def _render_examples_for_capability(capability_id: str) -> str:
    capability = next(item for item in supported_capabilities() if item.capability_id == capability_id)
    lines = [f"Examples for {capability.capability_id}:"]
    for command_name in capability.commands:
        spec = get_command_spec(command_name)
        if spec is not None and spec.examples:
            lines.append(f"- {spec.examples[0]}")
    return "\n".join(lines)


def _unknown_help_target(target: str) -> str:
    return (
        f"Unknown help target: {target}\n"
        "Try one of: help capabilities | help <capability_id> | help <command_family> | capabilities | commands | examples"
    )


def _maturity_label(level: MaturityLevel) -> str:
    if level is MaturityLevel.STRUCTURED:
        return "structured"
    if level is MaturityLevel.DIRECT_ONLY:
        return "direct-only"
    if level is MaturityLevel.EXPERIMENTAL_ONLY:
        return "experimental-only"
    return "blocked"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(verbose=args.verbose)
    run_mode = _run_mode_from_args(args)

    if args.request and " ".join(args.request).strip().lower() == "doctor":
        report = run_doctor()
        print_report(report)
        return report.exit_code

    config = load_config()
    validator = Validator(config.policy)
    executor = Executor(timeout_seconds=config.timeout_seconds)
    audit_logger = (
        AuditLogger(config.audit_log_path, redact=config.audit_redact)
        if config.audit_enabled
        else None
    )
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
        if request.lower().strip() == "audit status":
            print(render_audit_status(audit_logger, enabled=config.audit_enabled))
            return 0
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
        audit_enabled=config.audit_enabled,
        debug_trace=args.verbose,
        default_run_mode=run_mode,
    )


def _duration_ms_since(started_at: datetime) -> int:
    return int((datetime.now(tz=timezone.utc) - started_at).total_seconds() * 1000)


def _truncate(value: str, width: int) -> str:
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


def render_audit_status(audit_logger: AuditLogger | None, *, enabled: bool = True) -> str:
    lines = [f"audit enabled: {'yes' if enabled else 'no'}"]
    if not enabled:
        lines.append("audit logging is disabled by OTERMINUS_AUDIT_ENABLED=false")
        return "\n".join(lines)
    if audit_logger is None:
        lines.append("audit logger unavailable")
        return "\n".join(lines)
    details = audit_logger.status()
    lines.append(f"path: {details['path']}")
    lines.append(f"log file exists: {details['exists']}")
    lines.append(f"redaction: {details['redaction']}")
    return "\n".join(lines)


def render_ambiguity_response(result: AmbiguityResult) -> str:
    lines = [
        "This request is ambiguous. I can help with one of these safer inspections:",
        *(f"- {option}" for option in result.suggested_safe_options),
    ]
    if result.follow_up_questions:
        lines.append("Helpful clarifying questions:")
        lines.extend(f"- {question}" for question in result.follow_up_questions)
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

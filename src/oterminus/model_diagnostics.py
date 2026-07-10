from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from oterminus.models import ProposalMode
from oterminus.ollama_client import OllamaClientError, OllamaPlannerClient
from oterminus.planner import Planner, PlannerError


@dataclass(frozen=True, slots=True)
class ModelProbe:
    probe_id: str
    request: str
    expected_mode: ProposalMode | None = None
    expected_command_family: str | None = None


@dataclass(frozen=True, slots=True)
class ModelProbeResult:
    probe_id: str
    passed: bool
    repaired: bool
    mode: str | None
    command_family: str | None
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class ModelDiagnosticReport:
    model: str
    results: tuple[ModelProbeResult, ...]


class ModelDiagnosticError(RuntimeError):
    """A client or service failure prevented the diagnostic from completing."""


DEFAULT_MODEL_PROBES: tuple[ModelProbe, ...] = (
    ModelProbe(
        probe_id="ls-current-directory",
        request="list files in the current directory",
        expected_mode=ProposalMode.STRUCTURED,
        expected_command_family="ls",
    ),
    ModelProbe(
        probe_id="du-current-directory",
        request="show disk usage for the current directory",
        expected_mode=ProposalMode.STRUCTURED,
        expected_command_family="du",
    ),
    ModelProbe(
        probe_id="man-grep",
        request="show the manual page for grep",
        expected_mode=ProposalMode.STRUCTURED,
        expected_command_family="man",
    ),
)

PlannerFactory = Callable[[str], Planner]


def run_model_diagnostics(
    model: str,
    *,
    probes: Sequence[ModelProbe] = DEFAULT_MODEL_PROBES,
    planner_factory: PlannerFactory | None = None,
) -> ModelDiagnosticReport:
    """Test planner schema compliance without rendering or executing proposals."""

    make_planner = planner_factory or _default_planner_factory
    results: list[ModelProbeResult] = []
    for probe in probes:
        traces: list[str] = []
        try:
            planner = make_planner(model)
            proposal = planner.plan(probe.request, trace_callback=traces.append)
        except OllamaClientError as exc:
            raise ModelDiagnosticError(str(exc)) from exc
        except PlannerError as exc:
            results.append(
                ModelProbeResult(
                    probe_id=probe.probe_id,
                    passed=False,
                    repaired=False,
                    mode=None,
                    command_family=None,
                    failure_reason=_planner_failure_reason(exc, traces),
                )
            )
            continue

        mode = proposal.mode.value
        command_family = proposal.command_family
        repaired = "planner=repair_attempt succeeded" in traces
        failure_reason = _semantic_failure_reason(
            probe,
            mode=proposal.mode,
            command_family=command_family,
            needs_confirmation=proposal.needs_confirmation,
        )
        results.append(
            ModelProbeResult(
                probe_id=probe.probe_id,
                passed=failure_reason is None,
                repaired=repaired,
                mode=mode,
                command_family=command_family,
                failure_reason=failure_reason,
            )
        )

    return ModelDiagnosticReport(model=model, results=tuple(results))


def _default_planner_factory(model: str) -> Planner:
    return Planner(OllamaPlannerClient(model=model))


def _semantic_failure_reason(
    probe: ModelProbe,
    *,
    mode: ProposalMode,
    command_family: str | None,
    needs_confirmation: bool,
) -> str | None:
    expected_mode = probe.expected_mode
    if expected_mode is not None and mode is not expected_mode:
        return f"expected mode {expected_mode.value}, got {mode.value}"
    if (
        probe.expected_command_family is not None
        and command_family != probe.expected_command_family
    ):
        actual = command_family or "none"
        return f"expected family {probe.expected_command_family}, got {actual}"
    if not needs_confirmation:
        return "expected needs_confirmation=true"
    return None


def _planner_failure_reason(exc: PlannerError, traces: Sequence[str]) -> str:
    repair_detail = _schema_trace_detail(traces, stage="repair")
    if repair_detail:
        return f"schema mismatch after repair: {repair_detail}"

    detail = str(exc).strip().replace("\x00", "")
    details_marker = "Details: "
    if details_marker in detail:
        detail = detail.rsplit(details_marker, maxsplit=1)[-1]
    return _truncate(detail, 1200)


def _schema_trace_detail(traces: Sequence[str], *, stage: str) -> str | None:
    marker = f"planner=schema_validation_failed stage={stage} detail="
    for trace in reversed(traces):
        if trace.startswith(marker):
            return trace.removeprefix(marker)
    return None


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3] + "..."

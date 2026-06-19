from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from oterminus.ambiguity import detect_ambiguity
from oterminus.commands import registry as command_registry
from oterminus.direct_commands import detect_direct_command
from oterminus.local_planner import plan_locally
from oterminus.models import ProposalMode, RiskLevel
from oterminus.planner import Planner, PlannerError
from oterminus.policies import PolicyConfig
from oterminus.router import route_request
from oterminus.validator import ProposalOrigin, Validator


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    planner_proposal: dict[str, Any] | None = None
    expected_mode: ProposalMode | None = None
    expected_command_family: str | None = None
    expected_risk_level: RiskLevel | None = None
    expected_acceptance: bool | None = None
    expected_rendered_command: str | None = None
    expected_argv: list[str] | None = None
    expected_planner_error_contains: str | None = None
    expected_ambiguity_detected: bool | None = None
    expected_ambiguity_reason_contains: str | None = None
    expected_ambiguity_safe_options: list[str] | None = None
    platform_id: str | None = None
    optional_notes: str | None = None

    @model_validator(mode="after")
    def validate_expectations(self) -> EvalCase:
        if self.expected_planner_error_contains or self.expected_ambiguity_detected is True:
            return self
        if (
            self.expected_mode is None
            or self.expected_risk_level is None
            or self.expected_acceptance is None
        ):
            raise ValueError(
                "expected_mode, expected_risk_level, and expected_acceptance are required "
                "unless expected_planner_error_contains is set or expected_ambiguity_detected "
                "is true."
            )
        return self


class EvalCandidateValidationError(ValueError):
    def __init__(self, path: Path, messages: list[str]) -> None:
        self.path = path
        self.messages = messages
        super().__init__(self._format())

    def _format(self) -> str:
        lines = [f"Invalid eval candidate: {self.path}"]
        lines.extend(f"- {message}" for message in self.messages)
        return "\n".join(lines)


@dataclass(slots=True)
class EvalMismatch:
    field: str
    expected: Any
    actual: Any


@dataclass(slots=True)
class EvalResult:
    case_id: str
    passed: bool
    mismatches: list[EvalMismatch]


@dataclass(slots=True)
class EvalSummary:
    total: int
    passed: int
    failed: int


def default_fixtures_dir() -> Path:
    module_root = Path(__file__).resolve().parent
    package_fixtures = module_root / "eval_fixtures"
    if package_fixtures.exists():
        return package_fixtures

    repo_fixtures = module_root.parent.parent / "evals" / "cases"
    return repo_fixtures


def load_eval_cases(fixtures_dir: Path) -> list[EvalCase]:
    if not fixtures_dir.exists():
        raise FileNotFoundError(f"Eval fixtures directory does not exist: {fixtures_dir}")

    cases: list[EvalCase] = []
    seen_ids: dict[str, Path] = {}

    for path in sorted(fixtures_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in eval fixture file {path}: {exc}") from exc

        if not isinstance(payload, list):
            raise ValueError(f"Fixture file must contain a JSON array: {path}")

        for index, raw_case in enumerate(payload):
            try:
                case = EvalCase.model_validate(raw_case)
            except ValidationError as exc:
                raise ValueError(f"Invalid eval fixture in {path} at index {index}: {exc}") from exc

            if case.id in seen_ids:
                first_path = seen_ids[case.id]
                raise ValueError(
                    f"Duplicate eval fixture id '{case.id}' in {first_path} and {path}"
                )
            seen_ids[case.id] = path
            cases.append(case)

    if not cases:
        raise ValueError(f"No eval fixtures found in {fixtures_dir}")

    return cases


def validate_eval_candidate_file(path: Path) -> list[EvalCase]:
    if not path.exists():
        raise EvalCandidateValidationError(path, ["File does not exist."])
    if not path.is_file():
        raise EvalCandidateValidationError(path, ["Path must be a JSON file."])

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except PermissionError as exc:
        raise EvalCandidateValidationError(path, ["File is not readable."]) from exc
    except OSError as exc:
        raise EvalCandidateValidationError(path, [f"Could not read file: {exc.strerror}."]) from exc
    except UnicodeDecodeError as exc:
        raise EvalCandidateValidationError(
            path,
            [
                "File must be UTF-8 encoded JSON; "
                f"could not decode byte {exc.object[exc.start]:#x} at offset {exc.start}."
            ],
        ) from exc
    except json.JSONDecodeError as exc:
        raise EvalCandidateValidationError(
            path,
            [f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}."],
        ) from exc

    if not isinstance(payload, list):
        raise EvalCandidateValidationError(path, ["Root value must be a JSON array."])
    if not payload:
        raise EvalCandidateValidationError(path, ["Candidate file must contain at least one case."])

    cases: list[EvalCase] = []
    seen_ids: dict[str, int] = {}
    messages: list[str] = []

    for index, raw_case in enumerate(payload):
        try:
            case = EvalCase.model_validate(raw_case)
        except ValidationError as exc:
            messages.extend(_format_candidate_case_errors(index, exc))
            continue

        if case.id in seen_ids:
            messages.append(
                f"Duplicate case id '{case.id}' at indexes {seen_ids[case.id]} and {index}."
            )
        else:
            seen_ids[case.id] = index
        cases.append(case)

    if messages:
        raise EvalCandidateValidationError(path, messages)

    return cases


def _format_candidate_case_errors(index: int, exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"])
        raw_message = str(error["msg"])
        if raw_message.startswith("Value error, "):
            raw_message = raw_message.removeprefix("Value error, ")
        message = _ensure_sentence(raw_message)
        if loc:
            messages.append(f"Case at index {index}: {loc}: {message}")
        else:
            messages.append(f"Case at index {index}: {message}")
    return messages


def _ensure_sentence(message: str) -> str:
    if message.endswith((".", "!", "?")):
        return message
    return f"{message}."


def evaluate_case(case: EvalCase, validator: Validator) -> EvalResult:
    mismatches: list[EvalMismatch] = []

    with _temporary_platform(case.platform_id):
        return _evaluate_case_on_platform(case, validator, mismatches)


def _evaluate_case_on_platform(
    case: EvalCase, validator: Validator, mismatches: list[EvalMismatch]
) -> EvalResult:
    proposal = detect_direct_command(case.user_input, platform_id=case.platform_id)
    proposal_origin = (
        ProposalOrigin.DIRECT_COMMAND if proposal is not None else ProposalOrigin.UNKNOWN
    )
    if proposal is None:
        ambiguity = detect_ambiguity(case.user_input)
        if case.expected_ambiguity_detected is not None and (
            ambiguity.is_ambiguous != case.expected_ambiguity_detected
        ):
            mismatches.append(
                EvalMismatch(
                    field="ambiguity_detected",
                    expected=case.expected_ambiguity_detected,
                    actual=ambiguity.is_ambiguous,
                )
            )
        if ambiguity.is_ambiguous:
            if case.expected_ambiguity_reason_contains is not None and (
                case.expected_ambiguity_reason_contains not in ambiguity.reason
            ):
                mismatches.append(
                    EvalMismatch(
                        field="ambiguity_reason",
                        expected=f"contains {case.expected_ambiguity_reason_contains!r}",
                        actual=ambiguity.reason,
                    )
                )
            if case.expected_ambiguity_safe_options is not None and (
                list(ambiguity.suggested_safe_options) != case.expected_ambiguity_safe_options
            ):
                mismatches.append(
                    EvalMismatch(
                        field="ambiguity_safe_options",
                        expected=case.expected_ambiguity_safe_options,
                        actual=list(ambiguity.suggested_safe_options),
                    )
                )
            if case.planner_proposal is not None:
                mismatches.append(
                    EvalMismatch(
                        field="planner_proposal",
                        expected="omitted when ambiguity stops before planner",
                        actual="present",
                    )
                )
            return EvalResult(case_id=case.id, passed=len(mismatches) == 0, mismatches=mismatches)
        if case.expected_ambiguity_detected is True:
            return EvalResult(case_id=case.id, passed=False, mismatches=mismatches)

        route = route_request(case.user_input, platform_id=case.platform_id)
        local_match = plan_locally(case.user_input, route, platform_id=case.platform_id)
        if local_match is not None:
            proposal = local_match.proposal
            proposal_origin = ProposalOrigin.LOCAL_PLANNER
        else:
            if case.planner_proposal is None:
                return EvalResult(
                    case_id=case.id,
                    passed=False,
                    mismatches=[
                        *mismatches,
                        EvalMismatch(
                            field="planner_proposal",
                            expected="fixture with planner_proposal or local-planner match for non-direct input",
                            actual=None,
                        ),
                    ],
                )

            try:
                proposal = Planner.parse_proposal(json.dumps(case.planner_proposal))
                proposal_origin = ProposalOrigin.OLLAMA_PLANNER
            except PlannerError as exc:
                if (
                    case.expected_planner_error_contains
                    and case.expected_planner_error_contains in str(exc)
                ):
                    return EvalResult(case_id=case.id, passed=True, mismatches=[])
                return EvalResult(
                    case_id=case.id,
                    passed=False,
                    mismatches=[
                        EvalMismatch(
                            field="planner_parse",
                            expected="valid planner payload",
                            actual=str(exc),
                        )
                    ],
                )

    validation = validator.validate(proposal, origin=proposal_origin)

    if case.expected_mode is not None and proposal.mode != case.expected_mode:
        mismatches.append(
            EvalMismatch(
                field="mode", expected=case.expected_mode.value, actual=proposal.mode.value
            )
        )

    if proposal.command_family != case.expected_command_family:
        mismatches.append(
            EvalMismatch(
                field="command_family",
                expected=case.expected_command_family,
                actual=proposal.command_family,
            )
        )

    if case.expected_risk_level is not None and validation.risk_level != case.expected_risk_level:
        mismatches.append(
            EvalMismatch(
                field="risk_level",
                expected=case.expected_risk_level.value,
                actual=validation.risk_level.value,
            )
        )

    if case.expected_acceptance is not None and validation.accepted != case.expected_acceptance:
        mismatches.append(
            EvalMismatch(
                field="accepted",
                expected=case.expected_acceptance,
                actual=validation.accepted,
            )
        )

    if (
        case.expected_rendered_command is not None
        and validation.rendered_command != case.expected_rendered_command
    ):
        mismatches.append(
            EvalMismatch(
                field="rendered_command",
                expected=case.expected_rendered_command,
                actual=validation.rendered_command,
            )
        )

    if case.expected_argv is not None and validation.argv != case.expected_argv:
        mismatches.append(
            EvalMismatch(field="argv", expected=case.expected_argv, actual=validation.argv)
        )

    return EvalResult(case_id=case.id, passed=len(mismatches) == 0, mismatches=mismatches)


@contextmanager
def _temporary_platform(platform_id: str | None):
    if platform_id is None:
        yield
        return
    original = command_registry.sys.platform
    command_registry.sys.platform = platform_id
    try:
        yield
    finally:
        command_registry.sys.platform = original


def run_eval_cases(
    cases: list[EvalCase], validator: Validator
) -> tuple[list[EvalResult], EvalSummary]:
    results = [evaluate_case(case, validator) for case in cases]
    passed = sum(1 for result in results if result.passed)
    summary = EvalSummary(total=len(results), passed=passed, failed=len(results) - passed)
    return results, summary


def format_eval_report(results: list[EvalResult], summary: EvalSummary) -> str:
    lines: list[str] = [
        "oterminus eval report",
        "====================",
        f"Total: {summary.total}  Passed: {summary.passed}  Failed: {summary.failed}",
        "",
    ]

    for result in results:
        prefix = "PASS" if result.passed else "FAIL"
        lines.append(f"[{prefix}] {result.case_id}")
        for mismatch in result.mismatches:
            lines.append(
                f"  - {mismatch.field}: expected={mismatch.expected!r} actual={mismatch.actual!r}"
            )

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic eval fixtures for oterminus.")
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--fixtures-dir",
        default=str(default_fixtures_dir()),
        help="Directory containing eval fixture JSON files (default: packaged fixtures)",
    )
    source_group.add_argument(
        "--validate-file",
        help="Validate one contributor-created eval candidate JSON file",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run deterministic evaluation after --validate-file succeeds",
    )
    args = parser.parse_args(argv)
    if args.run and args.validate_file is None:
        parser.error("--run requires --validate-file")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate_file is not None:
        try:
            cases = validate_eval_candidate_file(Path(args.validate_file))
        except EvalCandidateValidationError as exc:
            print(exc)
            return 2
        if not args.run:
            print(f"Valid eval candidate: {args.validate_file} ({len(cases)} case(s))")
            return 0
    else:
        cases = load_eval_cases(Path(args.fixtures_dir))

    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    results, summary = run_eval_cases(cases, validator)
    print(format_eval_report(results, summary))
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

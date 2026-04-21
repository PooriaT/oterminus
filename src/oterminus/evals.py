from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from oterminus.direct_commands import detect_direct_command
from oterminus.models import ProposalMode, RiskLevel
from oterminus.planner import Planner, PlannerError
from oterminus.policies import PolicyConfig
from oterminus.validator import Validator


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
    optional_notes: str | None = None

    @model_validator(mode="after")
    def validate_expectations(self) -> EvalCase:
        if self.expected_planner_error_contains:
            return self
        if self.expected_mode is None or self.expected_risk_level is None or self.expected_acceptance is None:
            raise ValueError(
                "expected_mode, expected_risk_level, and expected_acceptance are required unless expected_planner_error_contains is set."
            )
        return self


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


def load_eval_cases(fixtures_dir: Path) -> list[EvalCase]:
    if not fixtures_dir.exists():
        raise FileNotFoundError(f"Eval fixtures directory does not exist: {fixtures_dir}")

    cases: list[EvalCase] = []
    seen_ids: set[str] = set()

    for path in sorted(fixtures_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        if not isinstance(payload, list):
            raise ValueError(f"Fixture file must contain a JSON array: {path}")

        for index, raw_case in enumerate(payload):
            try:
                case = EvalCase.model_validate(raw_case)
            except ValidationError as exc:
                raise ValueError(f"Invalid eval fixture in {path} at index {index}: {exc}") from exc

            if case.id in seen_ids:
                raise ValueError(f"Duplicate eval fixture id: {case.id}")
            seen_ids.add(case.id)
            cases.append(case)

    if not cases:
        raise ValueError(f"No eval fixtures found in {fixtures_dir}")

    return cases


def evaluate_case(case: EvalCase, validator: Validator) -> EvalResult:
    mismatches: list[EvalMismatch] = []

    proposal = detect_direct_command(case.user_input)
    if proposal is None:
        if case.planner_proposal is None:
            return EvalResult(
                case_id=case.id,
                passed=False,
                mismatches=[
                    EvalMismatch(
                        field="planner_proposal",
                        expected="fixture with planner_proposal for non-direct input",
                        actual=None,
                    )
                ],
            )

        try:
            proposal = Planner.parse_proposal(json.dumps(case.planner_proposal))
        except PlannerError as exc:
            if case.expected_planner_error_contains and case.expected_planner_error_contains in str(exc):
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

    validation = validator.validate(proposal)

    if case.expected_mode is not None and proposal.mode != case.expected_mode:
        mismatches.append(
            EvalMismatch(field="mode", expected=case.expected_mode.value, actual=proposal.mode.value)
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

    if case.expected_rendered_command is not None and validation.rendered_command != case.expected_rendered_command:
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


def run_eval_cases(cases: list[EvalCase], validator: Validator) -> tuple[list[EvalResult], EvalSummary]:
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
    parser.add_argument(
        "--fixtures-dir",
        default="evals/cases",
        help="Directory containing eval fixture JSON files (default: evals/cases)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = load_eval_cases(Path(args.fixtures_dir))
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    results, summary = run_eval_cases(cases, validator)
    print(format_eval_report(results, summary))
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

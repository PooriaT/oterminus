import json
from pathlib import Path

import pytest

from oterminus.evals import (
    EvalCase,
    format_eval_report,
    load_eval_cases,
    run_eval_cases,
)
from oterminus.models import RiskLevel
from oterminus.policies import PolicyConfig
from oterminus.validator import Validator


def _minimal_case(case_id: str) -> dict[str, object]:
    return {
        "id": case_id,
        "user_input": "pwd",
        "expected_mode": "structured",
        "expected_command_family": "pwd",
        "expected_risk_level": "safe",
        "expected_acceptance": True,
    }


def test_load_eval_cases_loads_multiple_files_in_sorted_order(tmp_path: Path) -> None:
    fixtures = tmp_path / "cases"
    fixtures.mkdir()
    (fixtures / "b.json").write_text(json.dumps([_minimal_case("case-b")]))
    (fixtures / "a.json").write_text(json.dumps([_minimal_case("case-a")]))

    cases = load_eval_cases(fixtures)

    assert [case.id for case in cases] == ["case-a", "case-b"]


def test_load_eval_cases_requires_unique_ids_across_files(tmp_path: Path) -> None:
    fixtures = tmp_path / "cases"
    fixtures.mkdir()
    (fixtures / "a.json").write_text(json.dumps([_minimal_case("dup")]))
    (fixtures / "b.json").write_text(json.dumps([_minimal_case("dup")]))

    with pytest.raises(ValueError, match=r"Duplicate eval fixture id 'dup'.*a.json.*b.json"):
        load_eval_cases(fixtures)


def test_load_eval_cases_rejects_empty_fixtures_dir(tmp_path: Path) -> None:
    fixtures = tmp_path / "cases"
    fixtures.mkdir()

    with pytest.raises(ValueError, match="No eval fixtures found"):
        load_eval_cases(fixtures)


def test_load_eval_cases_rejects_non_array_json(tmp_path: Path) -> None:
    fixtures = tmp_path / "cases"
    fixtures.mkdir()
    (fixtures / "bad.json").write_text(json.dumps({"id": "nope"}))

    with pytest.raises(ValueError, match=r"Fixture file must contain a JSON array: .*bad.json"):
        load_eval_cases(fixtures)


def test_run_eval_cases_reports_pass_and_fail() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    cases = [
        EvalCase.model_validate(
            {
                "id": "pass-case",
                "user_input": "pwd",
                "expected_mode": "structured",
                "expected_command_family": "pwd",
                "expected_risk_level": "safe",
                "expected_acceptance": True,
                "expected_rendered_command": "pwd",
                "expected_argv": ["pwd"],
            }
        ),
        EvalCase.model_validate(
            {
                "id": "fail-case",
                "user_input": "pwd",
                "expected_mode": "experimental",
                "expected_command_family": "pwd",
                "expected_risk_level": "safe",
                "expected_acceptance": True,
            }
        ),
    ]

    results, summary = run_eval_cases(cases, validator)

    assert summary.total == 2
    assert summary.passed == 1
    assert summary.failed == 1
    report = format_eval_report(results, summary)
    assert "[PASS] pass-case" in report
    assert "[FAIL] fail-case" in report


def test_default_fixture_suite_is_capability_split() -> None:
    fixtures = load_eval_cases(Path("evals/cases"))
    fixture_files = sorted(path.name for path in Path("evals/cases").glob("*.json"))

    assert len(fixtures) >= 30
    assert "golden_core.json" not in fixture_files
    assert {
        "direct_commands.json",
        "filesystem_inspection.json",
        "filesystem_mutation.json",
        "text_inspection.json",
        "process_inspection.json",
        "git_inspection.json",
        "system_inspection.json",
        "macos_desktop.json",
        "unsafe_and_blocked.json",
        "ambiguity.json",
        "planner_normalization.json",
    }.issubset(set(fixture_files))

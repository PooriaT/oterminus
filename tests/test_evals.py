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


def test_load_eval_cases_requires_unique_ids(tmp_path: Path) -> None:
    fixtures = tmp_path / "cases"
    fixtures.mkdir()
    payload = [
        {
            "id": "dup",
            "user_input": "pwd",
            "expected_mode": "structured",
            "expected_command_family": "pwd",
            "expected_risk_level": "safe",
            "expected_acceptance": True,
        },
        {
            "id": "dup",
            "user_input": "pwd",
            "expected_mode": "structured",
            "expected_command_family": "pwd",
            "expected_risk_level": "safe",
            "expected_acceptance": True,
        },
    ]
    (fixtures / "dups.json").write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="Duplicate eval fixture id"):
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


def test_golden_eval_fixture_set_has_minimum_coverage() -> None:
    fixtures = load_eval_cases(Path("evals/cases"))
    assert len(fixtures) >= 30

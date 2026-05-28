import json
from pathlib import Path

import pytest

from oterminus.evals import (
    EvalCase,
    default_fixtures_dir,
    format_eval_report,
    load_eval_cases,
    parse_args,
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


def test_load_eval_cases_rejects_invalid_json_with_file_path(tmp_path: Path) -> None:
    fixtures = tmp_path / "cases"
    fixtures.mkdir()
    (fixtures / "bad.json").write_text("[")

    with pytest.raises(ValueError, match=r"Invalid JSON in eval fixture file .*bad.json"):
        load_eval_cases(fixtures)


def test_load_eval_cases_rejects_invalid_case_shape_with_file_path_and_index(
    tmp_path: Path,
) -> None:
    fixtures = tmp_path / "cases"
    fixtures.mkdir()
    (fixtures / "bad.json").write_text(json.dumps([_minimal_case("ok"), {"id": "bad"}]))

    with pytest.raises(ValueError, match=r"Invalid eval fixture in .*bad.json at index 1"):
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

    expected_fixture_files = {
        "ambiguity.json",
        "archive_inspection.json",
        "direct_commands.json",
        "fast_path_local_planner.json",
        "filesystem_inspection.json",
        "filesystem_mutation.json",
        "git_inspection.json",
        "macos_desktop.json",
        "network_diagnostics.json",
        "planner_normalization.json",
        "process_inspection.json",
        "project_health.json",
        "system_inspection.json",
        "text_inspection.json",
        "unsafe_and_blocked.json",
    }
    case_ids = [case.id for case in fixtures]

    assert len(fixtures) >= 30
    assert len(case_ids) == len(set(case_ids))
    assert "golden_core.json" not in fixture_files
    assert expected_fixture_files.issubset(set(fixture_files))


def test_default_eval_command_uses_packaged_capability_fixtures() -> None:
    repo_fixture_files = sorted(path.name for path in Path("evals/cases").glob("*.json"))
    package_fixture_files = sorted(path.name for path in default_fixtures_dir().glob("*.json"))

    assert parse_args([]).fixtures_dir == str(default_fixtures_dir())
    assert package_fixture_files == repo_fixture_files
    assert len(load_eval_cases(default_fixtures_dir())) == len(load_eval_cases(Path("evals/cases")))


def test_expanded_newer_capability_cases_pass_without_ollama() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    fixtures = load_eval_cases(Path("evals/cases"))
    required_ids = {
        "archive-reject-arbitrary-tar-flags-direct",
        "network-reject-file-url-structured",
        "network-reject-wget-unsupported",
        "git-reject-push-structured",
        "project-health-reject-ruff-format-write-direct",
        "direct-git-status-short",
    }
    selected = [case for case in fixtures if case.id in required_ids]

    assert {case.id for case in selected} == required_ids
    results, summary = run_eval_cases(selected, validator)

    assert summary.total == len(required_ids)
    assert summary.failed == 0
    assert all(result.passed for result in results)


def test_expanded_unsafe_and_ambiguity_cases_cover_expected_boundaries() -> None:
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    fixtures = load_eval_cases(Path("evals/cases"))
    case_by_id = {case.id: case for case in fixtures}

    assert case_by_id["ambiguous-repair-this-repo"].expected_ambiguity_detected is True
    assert case_by_id["ambiguous-backup-everything"].planner_proposal is None
    assert case_by_id["unsafe-command-substitution-blocked"].expected_acceptance is False
    assert case_by_id["unsafe-unsupported-nmap-scan"].expected_acceptance is False

    selected = [
        case_by_id["ambiguous-repair-this-repo"],
        case_by_id["ambiguous-backup-everything"],
        case_by_id["unsafe-command-substitution-blocked"],
        case_by_id["unsafe-unsupported-nmap-scan"],
    ]
    results, summary = run_eval_cases(selected, validator)

    assert summary.failed == 0
    assert all(result.passed for result in results)

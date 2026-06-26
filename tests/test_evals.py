import json
from pathlib import Path

import pytest

from oterminus.evals import (
    EvalCandidateValidationError,
    EvalCase,
    default_fixtures_dir,
    format_eval_report,
    load_eval_cases,
    main,
    parse_args,
    run_eval_cases,
    validate_eval_candidate_file,
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


def _write_candidate(path: Path, cases: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(cases), encoding="utf-8")


def _planner_case(case_id: str) -> dict[str, object]:
    return {
        "id": case_id,
        "user_input": "find python files in this folder",
        "planner_proposal": {
            "action_type": "shell_command",
            "mode": "structured",
            "command_family": "find",
            "arguments": {"path": ".", "name": "*.py"},
            "summary": "find python files",
            "explanation": "use find",
            "risk_level": "safe",
            "needs_confirmation": True,
            "notes": [],
        },
        "expected_mode": "structured",
        "expected_command_family": "find",
        "expected_risk_level": "safe",
        "expected_acceptance": True,
        "expected_rendered_command": "find . -name '*.py'",
        "expected_argv": ["find", ".", "-name", "*.py"],
    }


def _ambiguity_case(case_id: str) -> dict[str, object]:
    return {
        "id": case_id,
        "user_input": "clean this folder",
        "expected_ambiguity_detected": True,
        "expected_ambiguity_reason_contains": "Matched ambiguous phrase",
    }


def _local_planner_case(case_id: str) -> dict[str, object]:
    return {
        "id": case_id,
        "user_input": "show first 20 lines of README.md",
        "expected_mode": "structured",
        "expected_command_family": "head",
        "expected_risk_level": "safe",
        "expected_acceptance": True,
        "expected_rendered_command": "head -n 20 README.md",
        "expected_argv": ["head", "-n", "20", "README.md"],
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
        "deterministic_shortcuts.json",
        "filesystem_inspection.json",
        "filesystem_mutation.json",
        "git_inspection.json",
        "macos_desktop.json",
        "network_diagnostics.json",
        "planner_normalization.json",
        "process_inspection.json",
        "project_health.json",
        "release_smoke.json",
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
        "local-grep-search-todo-src",
        "local-git-last-5-commits",
        "local-process-find-python",
        "local-file-identify-readme",
    }
    selected = [case for case in fixtures if case.id in required_ids]

    assert {case.id for case in selected} == required_ids
    results, summary = run_eval_cases(selected, validator)

    assert summary.total == len(required_ids)
    assert summary.failed == 0
    assert all(result.passed for result in results)


def test_validate_eval_candidate_file_accepts_valid_single_case(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    _write_candidate(candidate, [_minimal_case("candidate-pwd")])

    cases = validate_eval_candidate_file(candidate)

    assert [case.id for case in cases] == ["candidate-pwd"]


def test_validate_eval_candidate_file_accepts_valid_multi_case(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    _write_candidate(
        candidate,
        [
            _minimal_case("candidate-pwd"),
            _planner_case("candidate-planner-find"),
            _ambiguity_case("candidate-ambiguous-clean"),
            _local_planner_case("candidate-local-head"),
        ],
    )

    cases = validate_eval_candidate_file(candidate)

    assert [case.id for case in cases] == [
        "candidate-pwd",
        "candidate-planner-find",
        "candidate-ambiguous-clean",
        "candidate-local-head",
    ]


def test_validate_eval_candidate_file_accepts_path_outside_eval_cases(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "scratch"
    candidate_dir.mkdir()
    candidate = candidate_dir / "proposed.json"
    _write_candidate(candidate, [_minimal_case("candidate-outside-fixtures")])

    cases = validate_eval_candidate_file(candidate)

    assert cases[0].id == "candidate-outside-fixtures"


@pytest.mark.parametrize("payload", [{"id": "nope"}, "nope", 1])
def test_validate_eval_candidate_file_rejects_non_array_roots(
    tmp_path: Path, payload: object
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvalCandidateValidationError, match="Root value must be a JSON array"):
        validate_eval_candidate_file(candidate)


def test_validate_eval_candidate_file_rejects_missing_file(tmp_path: Path) -> None:
    candidate = tmp_path / "missing.json"

    with pytest.raises(EvalCandidateValidationError, match="File does not exist"):
        validate_eval_candidate_file(candidate)


def test_validate_eval_candidate_file_rejects_unreadable_path(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.mkdir()

    with pytest.raises(EvalCandidateValidationError, match="Path must be a JSON file"):
        validate_eval_candidate_file(candidate)


def test_validate_eval_candidate_file_rejects_malformed_json(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text("[", encoding="utf-8")

    with pytest.raises(EvalCandidateValidationError, match="Invalid JSON at line 1, column 2"):
        validate_eval_candidate_file(candidate)


def test_validate_eval_candidate_file_rejects_invalid_utf8(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(b'[\xff{"id": "not-utf8"}]')

    with pytest.raises(EvalCandidateValidationError) as exc_info:
        validate_eval_candidate_file(candidate)

    message = str(exc_info.value)
    assert f"Invalid eval candidate: {candidate}" in message
    assert "File must be UTF-8 encoded JSON" in message
    assert "offset 1" in message


def test_validate_eval_candidate_file_rejects_empty_array(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text("[]", encoding="utf-8")

    with pytest.raises(
        EvalCandidateValidationError, match="Candidate file must contain at least one case"
    ):
        validate_eval_candidate_file(candidate)


def test_validate_eval_candidate_file_rejects_invalid_case_with_index(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    _write_candidate(candidate, [_minimal_case("ok"), {"id": "missing-user-input"}])

    with pytest.raises(EvalCandidateValidationError) as exc_info:
        validate_eval_candidate_file(candidate)

    message = str(exc_info.value)
    assert f"Invalid eval candidate: {candidate}" in message
    assert "Case at index 1: user_input: Field required." in message


def test_validate_eval_candidate_file_rejects_missing_required_expectations(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.json"
    _write_candidate(candidate, [{"id": "missing-expectations", "user_input": "pwd"}])

    with pytest.raises(EvalCandidateValidationError) as exc_info:
        validate_eval_candidate_file(candidate)

    assert (
        "Case at index 0: expected_mode, expected_risk_level, and expected_acceptance are required"
    ) in str(exc_info.value)


def test_validate_eval_candidate_file_rejects_unknown_field(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    raw_case = _minimal_case("unknown-field")
    raw_case["surprise"] = True
    _write_candidate(candidate, [raw_case])

    with pytest.raises(EvalCandidateValidationError) as exc_info:
        validate_eval_candidate_file(candidate)

    assert "Case at index 0: surprise: Extra inputs are not permitted." in str(exc_info.value)


def test_validate_eval_candidate_file_rejects_duplicate_ids_with_indexes(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.json"
    _write_candidate(
        candidate,
        [
            _minimal_case("text-show-readme"),
            _minimal_case("other"),
            _minimal_case("text-show-readme"),
        ],
    )

    with pytest.raises(EvalCandidateValidationError) as exc_info:
        validate_eval_candidate_file(candidate)

    assert "Duplicate case id 'text-show-readme' at indexes 0 and 2." in str(exc_info.value)


def test_eval_cli_validate_file_exits_zero_for_valid_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate = tmp_path / "candidate.json"
    _write_candidate(candidate, [_minimal_case("candidate-pwd")])

    assert main(["--validate-file", str(candidate)]) == 0

    assert f"Valid eval candidate: {candidate} (1 case(s))" in capsys.readouterr().out


def test_eval_cli_validate_file_exits_nonzero_for_invalid_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"id": "nope"}), encoding="utf-8")

    assert main(["--validate-file", str(candidate)]) == 2

    output = capsys.readouterr().out
    assert f"Invalid eval candidate: {candidate}" in output
    assert "- Root value must be a JSON array." in output


def test_eval_cli_validate_file_exits_nonzero_for_invalid_utf8(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(b"\xff")

    assert main(["--validate-file", str(candidate)]) == 2

    output = capsys.readouterr().out
    assert f"Invalid eval candidate: {candidate}" in output
    assert "File must be UTF-8 encoded JSON" in output


def test_eval_cli_validate_file_run_evaluates_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate = tmp_path / "candidate.json"
    _write_candidate(candidate, [_minimal_case("candidate-pwd")])

    assert main(["--validate-file", str(candidate), "--run"]) == 0

    output = capsys.readouterr().out
    assert "oterminus eval report" in output
    assert "[PASS] candidate-pwd" in output


def test_eval_cli_validate_file_run_exits_nonzero_when_eval_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate = tmp_path / "candidate.json"
    failing_case = _minimal_case("candidate-fails")
    failing_case["expected_command_family"] = "not-pwd"
    _write_candidate(candidate, [failing_case])

    assert main(["--validate-file", str(candidate), "--run"]) == 1

    output = capsys.readouterr().out
    assert "[FAIL] candidate-fails" in output


def test_eval_cli_fixtures_dir_behavior_still_runs_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixtures = tmp_path / "cases"
    fixtures.mkdir()
    _write_candidate(fixtures / "candidate.json", [_minimal_case("fixture-pwd")])

    assert main(["--fixtures-dir", str(fixtures)]) == 0

    output = capsys.readouterr().out
    assert "[PASS] fixture-pwd" in output


def test_eval_cli_no_arg_behavior_still_uses_default_fixtures() -> None:
    assert parse_args([]).fixtures_dir == str(default_fixtures_dir())
    assert parse_args([]).validate_file is None
    assert parse_args([]).run is False


def test_eval_cli_run_without_validate_file_fails_clearly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--run"])

    assert exc_info.value.code == 2
    assert "--run requires --validate-file" in capsys.readouterr().err


def test_eval_cli_validate_file_and_fixtures_dir_combination_fails_clearly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate = tmp_path / "candidate.json"
    _write_candidate(candidate, [_minimal_case("candidate-pwd")])

    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--validate-file", str(candidate), "--fixtures-dir", "evals/cases"])

    assert exc_info.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


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

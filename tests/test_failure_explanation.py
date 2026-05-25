from unittest.mock import Mock

from oterminus.cli import RunMode, handle_request
from oterminus.models import (
    ActionType,
    FailureExplanation,
    Proposal,
    ProposalMode,
    RiskLevel,
    SuggestedNextActionMode,
    ValidationResult,
)


def _proposal() -> Proposal:
    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command="grep TODO missing.txt",
        summary="search",
        explanation="desc",
    )


def test_nonzero_with_explainer_prints_and_preserves_exit(monkeypatch, capsys) -> None:
    planner = Mock()
    planner.plan.return_value = _proposal()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="grep TODO missing.txt",
        argv=["grep", "TODO", "missing.txt"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 2
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = "No such file"
    explainer = Mock()
    explainer.explain.return_value = FailureExplanation(
        command="grep TODO missing.txt",
        exit_code=2,
        stderr_summary="No such file",
        likely_cause="File missing",
        suggested_next_action='oterminus --dry-run "list files in this directory"',
        suggested_next_action_mode=SuggestedNextActionMode.DRY_RUN,
    )
    monkeypatch.setattr("builtins.input", lambda _p: "EXECUTE EXPERIMENTAL")

    code = handle_request("find", planner, validator, executor, failure_explainer=explainer)

    assert code == 2
    executor.run.assert_called_once()
    explainer.explain.assert_called_once()
    out = capsys.readouterr().out
    assert "--- failure explanation ---" in out
    assert "No next action was executed." in out


def test_nonzero_without_explainer_does_not_generate(monkeypatch) -> None:
    planner = Mock()
    planner.plan.return_value = _proposal()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="grep TODO missing.txt",
        argv=["grep", "TODO", "missing.txt"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 1
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = "err"
    monkeypatch.setattr("builtins.input", lambda _p: "EXECUTE EXPERIMENTAL")
    assert handle_request("find", planner, validator, executor, failure_explainer=None) == 1


def test_dry_run_does_not_trigger_explainer() -> None:
    planner = Mock()
    planner.plan.return_value = _proposal()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="grep TODO missing.txt",
        argv=["grep", "TODO", "missing.txt"],
    )
    executor = Mock()
    explainer = Mock()
    assert (
        handle_request(
            "find",
            planner,
            validator,
            executor,
            run_mode=RunMode.DRY_RUN,
            failure_explainer=explainer,
        )
        == 0
    )
    explainer.explain.assert_not_called()
    executor.run.assert_not_called()

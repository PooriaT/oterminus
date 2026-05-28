import json
from unittest.mock import Mock

from oterminus.config import load_config
from oterminus.failure_explainer import FailureExplainer, FailureExplainerConfig

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


def test_failure_explanation_config_defaults_to_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_EXPLAIN_FAILURES", raising=False)

    config = load_config()

    assert config.explain_failures is False
    assert FailureExplainerConfig().enabled is False


def test_failure_explainer_redacts_and_truncates_context_before_model_call() -> None:
    client = Mock()
    client.chat_json.return_value = json.dumps(
        {
            "likely_cause": "bad token TOKEN=server-secret",
            "stderr_summary": "PASSWORD=model-secret",
            "suggested_next_action": "curl --token model-secret",
            "suggested_next_action_mode": "dry-run",
            "notes": ["api_key: model-secret"],
        }
    )
    explainer = FailureExplainer(client, max_chars=24)

    explanation = explainer.explain(
        command="curl --password command-secret https://example.com",
        exit_code=1,
        stdout="API_KEY=stdout-secret " + "x" * 100,
        stderr="Bearer stderr-secret " + "y" * 100,
    )

    _, prompt = client.chat_json.call_args.args
    payload = json.loads(prompt)
    serialized_prompt = json.dumps(payload)
    assert "command-secret" not in serialized_prompt
    assert "stdout-secret" not in serialized_prompt
    assert "stderr-secret" not in serialized_prompt
    assert len(payload["stdout"]) <= 24
    assert len(payload["stderr"]) <= 24
    assert explanation.stderr_summary == "PASSWORD=[REDACTED]"
    assert explanation.suggested_next_action == "curl --token [REDACTED]"
    assert explanation.likely_cause == "bad token TOKEN=[REDACTED]"
    assert explanation.notes == ["api_key: [REDACTED]"]


def test_failure_explainer_does_not_pass_raw_common_secrets_to_ollama_client() -> None:
    client = Mock()
    client.chat_json.return_value = json.dumps({"suggested_next_action_mode": "none"})
    explainer = FailureExplainer(client, max_chars=4000)

    explainer.explain(
        command="deploy --token command-token",
        exit_code=1,
        stdout="https://user:pass@example.com/path ghp_abcdefghijklmnopqrstuvwxyz123456",
        stderr="Authorization: Bearer stderr-token PASSWORD=stderr-password",
    )

    prompt = client.chat_json.call_args.args[1]
    for secret in (
        "command-token",
        "user:pass@",
        "ghp_abcdefghijklmnopqrstuvwxyz123456",
        "stderr-token",
        "stderr-password",
    ):
        assert secret not in prompt


def test_failure_explainer_invalid_suggested_next_action_mode_falls_back_safely() -> None:
    client = Mock()
    client.chat_json.return_value = json.dumps(
        {
            "suggested_next_action": "ls",
            "suggested_next_action_mode": "execute-now",
        }
    )
    explainer = FailureExplainer(client)

    explanation = explainer.explain(command="false", exit_code=1, stdout="", stderr="")

    assert explanation.suggested_next_action_mode == SuggestedNextActionMode.NONE


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


def test_failure_explainer_errors_do_not_execute_suggested_actions(monkeypatch) -> None:
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
    executor.run.return_value.stderr = "err"
    explainer = Mock()
    explainer.explain.side_effect = RuntimeError("model failed")
    monkeypatch.setattr("builtins.input", lambda _p: "EXECUTE EXPERIMENTAL")

    code = handle_request("find", planner, validator, executor, failure_explainer=explainer)

    assert code == 2
    executor.run.assert_called_once()
    explainer.explain.assert_called_once()

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from oterminus.model_diagnostics import (
    DEFAULT_MODEL_PROBES,
    ModelDiagnosticError,
    ModelProbe,
    run_model_diagnostics,
)
from oterminus.models import ProposalMode
from oterminus.ollama_client import OllamaClientError
from oterminus.planner import Planner


class _FakeClient:
    def __init__(self, *responses: str, error: OllamaClientError | None = None) -> None:
        self.responses = list(responses)
        self.error = error
        self.calls: list[dict[str, object]] = []

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "output_schema": output_schema,
            }
        )
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


def _payload(
    family: str | None,
    arguments: dict[str, object] | None,
    **overrides: object,
) -> str:
    proposal: dict[str, object] = {
        "action_type": "shell_command",
        "mode": "structured",
        "command_family": family,
        "arguments": arguments,
        "command": None,
        "summary": f"use {family}",
        "explanation": f"Use structured {family} arguments.",
        "risk_level": "safe",
        "needs_confirmation": True,
        "notes": [],
    }
    proposal.update(overrides)
    return json.dumps(proposal)


def _probe(family: str) -> ModelProbe:
    return ModelProbe(
        probe_id=f"{family}-probe",
        request=f"test {family}",
        expected_mode=ProposalMode.STRUCTURED,
        expected_command_family=family,
    )


@pytest.mark.parametrize(
    ("family", "arguments"),
    (
        (
            "ls",
            {
                "path": ".",
                "long": False,
                "human_readable": False,
                "all": False,
                "recursive": False,
            },
        ),
        (
            "du",
            {"path": ".", "human_readable": True, "summarize": True, "max_depth": None},
        ),
        ("man", {"topic": "grep", "section": None}),
    ),
)
def test_initial_success_uses_planner_schema_path(
    family: str, arguments: dict[str, object]
) -> None:
    client = _FakeClient(_payload(family, arguments))

    report = run_model_diagnostics(
        "gemma4:latest",
        probes=(_probe(family),),
        planner_factory=lambda model: Planner(client),
    )

    assert report.model == "gemma4:latest"
    assert report.results[0].passed is True
    assert report.results[0].repaired is False
    assert report.results[0].mode == "structured"
    assert report.results[0].command_family == family
    assert client.calls[0]["output_schema"] is not None


def test_default_probes_are_fixed_read_only_families_and_use_fresh_planners() -> None:
    client = _FakeClient(
        _payload(
            "ls",
            {
                "path": ".",
                "long": False,
                "human_readable": False,
                "all": False,
                "recursive": False,
            },
        ),
        _payload(
            "du",
            {"path": ".", "human_readable": True, "summarize": True, "max_depth": None},
        ),
        _payload("man", {"topic": "grep", "section": None}),
    )
    planner_factory = Mock(side_effect=lambda model: Planner(client))

    report = run_model_diagnostics("gemma4:latest", planner_factory=planner_factory)

    assert [probe.expected_command_family for probe in DEFAULT_MODEL_PROBES] == ["ls", "du", "man"]
    assert all(result.passed for result in report.results)
    assert planner_factory.call_count == 3
    assert all(call.args == ("gemma4:latest",) for call in planner_factory.call_args_list)


def test_malformed_json_then_repair_success_is_marked_repaired() -> None:
    client = _FakeClient("{broken", _payload("man", {"topic": "grep", "section": None}))

    report = run_model_diagnostics(
        "gemma4:latest",
        probes=(_probe("man"),),
        planner_factory=lambda model: Planner(client),
    )

    result = report.results[0]
    assert result.passed is True
    assert result.repaired is True
    assert len(client.calls) == 2
    assert "previous response did not match" in str(client.calls[1]["user_prompt"])


def test_schema_mismatch_then_repair_success_is_marked_repaired() -> None:
    invalid = _payload("man", {"topic": "grep", "section": None}, mode="file")
    valid = _payload("man", {"topic": "grep", "section": None})
    client = _FakeClient(invalid, valid)

    report = run_model_diagnostics(
        "gemma4:latest",
        probes=(_probe("man"),),
        planner_factory=lambda model: Planner(client),
    )

    assert report.results[0].passed is True
    assert report.results[0].repaired is True


def test_experimental_raw_command_fails_before_structured_normalization() -> None:
    client = _FakeClient(
        _payload(
            None,
            None,
            mode="experimental",
            command="ls .",
            notes=["Experimental proposal; review before running."],
        )
    )

    report = run_model_diagnostics(
        "gemma4:latest",
        probes=(_probe("ls"),),
        planner_factory=lambda model: Planner(client),
    )

    result = report.results[0]
    assert result.passed is False
    assert result.mode == "experimental"
    assert result.command_family is None
    assert result.failure_reason == "expected mode structured, got experimental"


def test_repair_failure_is_concise_and_does_not_include_raw_output() -> None:
    raw = "sensitive unexpected raw output"
    client = _FakeClient("{broken", raw)

    report = run_model_diagnostics(
        "gemma4:latest",
        probes=(_probe("man"),),
        planner_factory=lambda model: Planner(client),
    )

    result = report.results[0]
    assert result.passed is False
    assert result.repaired is False
    assert result.failure_reason is not None
    assert result.failure_reason.startswith("schema mismatch after repair: Invalid JSON")
    assert raw not in result.failure_reason


def test_client_failure_prevents_diagnostic_from_completing() -> None:
    client = _FakeClient(error=OllamaClientError("Ollama returned an empty planning response."))

    with pytest.raises(ModelDiagnosticError, match="empty planning response"):
        run_model_diagnostics(
            "gemma4:latest",
            probes=(_probe("man"),),
            planner_factory=lambda model: Planner(client),
        )


def test_semantic_family_mismatch_fails_without_execution(monkeypatch) -> None:
    executor_run = Mock(side_effect=AssertionError("must not execute"))
    handle_request = Mock(side_effect=AssertionError("must not handle request"))
    confirmation = Mock(side_effect=AssertionError("must not confirm"))
    monkeypatch.setattr("oterminus.executor.Executor.run", executor_run)
    monkeypatch.setattr("oterminus.cli.handle_request", handle_request)
    monkeypatch.setattr("oterminus.cli.ask_confirmation", confirmation)
    client = _FakeClient(
        _payload(
            "du",
            {"path": ".", "human_readable": True, "summarize": True, "max_depth": None},
        )
    )

    report = run_model_diagnostics(
        "gemma4:latest",
        probes=(_probe("ls"),),
        planner_factory=lambda model: Planner(client),
    )

    result = report.results[0]
    assert result.passed is False
    assert result.failure_reason == "expected family ls, got du"
    executor_run.assert_not_called()
    handle_request.assert_not_called()
    confirmation.assert_not_called()

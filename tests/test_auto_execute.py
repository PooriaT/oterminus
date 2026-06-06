from __future__ import annotations

import pytest

from oterminus.auto_execute import evaluate_safe_auto_execute
from oterminus.commands import get_command_spec
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel, ValidationResult


def _proposal(
    family: str = "pwd",
    *,
    mode: ProposalMode = ProposalMode.STRUCTURED,
    arguments: dict[str, object] | None = None,
    command: str | None = None,
    risk: RiskLevel = RiskLevel.SAFE,
) -> Proposal:
    payload = {
        "action_type": ActionType.SHELL_COMMAND,
        "mode": mode,
        "command_family": family,
        "summary": "test",
        "explanation": "test",
        "risk_level": risk,
        "needs_confirmation": True,
        "notes": [],
    }
    if mode == ProposalMode.STRUCTURED:
        payload["arguments"] = arguments if arguments is not None else {}
    else:
        payload["command"] = command or family
    return Proposal(**payload)


def _validation(
    *,
    accepted: bool = True,
    risk: RiskLevel = RiskLevel.SAFE,
    warnings: list[str] | None = None,
    reasons: list[str] | None = None,
    rendered_command: str | None = "pwd",
    argv: list[str] | None = None,
) -> ValidationResult:
    return ValidationResult(
        accepted=accepted,
        risk_level=risk,
        warnings=warnings or [],
        reasons=reasons or [],
        rendered_command=rendered_command,
        argv=argv if argv is not None else ["pwd"],
    )


def _decision(
    *,
    proposal: Proposal | None = None,
    validation: ValidationResult | None = None,
    origin: str = "direct_command",
    command_name: str | None = "pwd",
    enabled: bool = True,
    run_mode: str = "execute",
    rerun_source_history_id: int | None = None,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
):
    return evaluate_safe_auto_execute(
        enabled=enabled,
        run_mode=run_mode,
        proposal=proposal or _proposal(),
        validation=validation or _validation(),
        proposal_origin=origin,
        command_spec=get_command_spec(command_name) if command_name is not None else None,
        rerun_source_history_id=rerun_source_history_id,
        disabled_pack_ids=disabled_pack_ids,
        platform_id=platform_id,
    )


def test_direct_structured_safe_command_is_eligible() -> None:
    assert _decision().eligible is True


def test_local_planner_structured_safe_command_is_eligible() -> None:
    assert _decision(origin="local_planner").eligible is True


@pytest.mark.parametrize("origin", ["ollama_planner", "unknown", "experimental_fallback"])
def test_only_direct_and_local_origins_are_eligible(origin: str) -> None:
    decision = _decision(origin=origin)
    assert decision.eligible is False
    assert decision.reason == "proposal_origin"


def test_experimental_safe_command_is_ineligible() -> None:
    decision = _decision(proposal=_proposal(mode=ProposalMode.EXPERIMENTAL, command="pwd"))
    assert decision.eligible is False
    assert decision.reason == "proposal_mode"


def test_direct_ls_passthrough_only_shape_is_not_auto_execute_eligible() -> None:
    proposal = _proposal("ls", mode=ProposalMode.EXPERIMENTAL, command="ls -ltrh")
    validation = _validation(rendered_command="ls -ltrh", argv=["ls", "-ltrh"])

    decision = _decision(proposal=proposal, validation=validation, command_name="ls")

    assert decision.eligible is False
    assert decision.reason == "proposal_mode"


@pytest.mark.parametrize("risk", [RiskLevel.WRITE, RiskLevel.DANGEROUS])
def test_write_and_dangerous_commands_are_ineligible(risk: RiskLevel) -> None:
    decision = _decision(validation=_validation(risk=risk))
    assert decision.eligible is False
    assert decision.reason == "risk_not_safe"


def test_warning_bearing_command_is_ineligible() -> None:
    decision = _decision(validation=_validation(warnings=["warning"]))
    assert decision.eligible is False
    assert decision.reason == "validation_warnings"


def test_rejection_reasons_are_ineligible() -> None:
    decision = _decision(validation=_validation(reasons=["reason"]))
    assert decision.eligible is False
    assert decision.reason == "validation_reasons"


def test_network_touching_command_is_ineligible() -> None:
    proposal = _proposal("ping", arguments={"host": "example.com", "count": 4})
    validation = _validation(
        rendered_command="ping -c 4 example.com",
        argv=["ping", "-c", "4", "example.com"],
    )
    decision = _decision(proposal=proposal, validation=validation, command_name="ping")
    assert decision.eligible is False
    assert decision.reason == "network_touching"


def test_project_health_command_is_ineligible() -> None:
    proposal = _proposal("project_health", arguments={"operation": "run_tests"})
    validation = _validation(
        rendered_command="poetry run pytest",
        argv=["poetry", "run", "pytest"],
    )
    decision = _decision(proposal=proposal, validation=validation, command_name="project_health")
    assert decision.eligible is False
    assert decision.reason == "project_health"


def test_archive_inspection_can_be_eligible() -> None:
    proposal = _proposal("tar", arguments={"operation": "list", "archive_path": "archive.tar"})
    validation = _validation(
        rendered_command="tar -tf archive.tar", argv=["tar", "-tf", "archive.tar"]
    )
    decision = _decision(proposal=proposal, validation=validation, command_name="tar")
    assert decision.eligible is True


@pytest.mark.parametrize(
    ("family", "arguments", "command_name"),
    [
        (
            "tar",
            {"operation": "extract_tar", "archive_path": "archive.tar", "destination_path": "out"},
            "tar",
        ),
        (
            "unzip",
            {
                "operation": "extract_zip",
                "archive_path": "archive.zip",
                "destination_path": "out",
            },
            "unzip",
        ),
        (
            "tar",
            {
                "operation": "create_tar_gz",
                "archive_path": "backup.tar.gz",
                "source_paths": ["src"],
            },
            "tar",
        ),
        (
            "zip",
            {"operation": "create_zip", "archive_path": "backup.zip", "source_paths": ["docs"]},
            "zip",
        ),
    ],
)
def test_archive_mutation_is_ineligible(
    family: str, arguments: dict[str, object], command_name: str
) -> None:
    proposal = _proposal(family, arguments=arguments)
    validation = _validation(
        rendered_command=f"{command_name} archive",
        argv=[command_name, "archive"],
    )
    decision = _decision(proposal=proposal, validation=validation, command_name=command_name)
    assert decision.eligible is False
    assert decision.reason == "archive_mutation"


def test_history_rerun_is_ineligible() -> None:
    decision = _decision(rerun_source_history_id=7)
    assert decision.eligible is False
    assert decision.reason == "history_rerun"


def test_missing_command_spec_is_ineligible() -> None:
    decision = _decision(command_name=None)
    assert decision.eligible is False
    assert decision.reason == "missing_command_spec"


@pytest.mark.parametrize(
    "validation",
    [
        _validation(rendered_command=None),
        _validation(argv=[]),
    ],
)
def test_missing_rendered_command_or_argv_is_ineligible(validation: ValidationResult) -> None:
    decision = _decision(validation=validation)
    assert decision.eligible is False


def test_disabled_command_pack_is_ineligible() -> None:
    decision = _decision(disabled_pack_ids=frozenset({"filesystem"}))
    assert decision.eligible is False
    assert decision.reason == "command_pack_disabled"


def test_unsupported_platform_command_is_ineligible() -> None:
    proposal = _proposal("pwd")
    validation = _validation(rendered_command="open .", argv=["open", "."])
    decision = _decision(
        proposal=proposal,
        validation=validation,
        command_name="open",
        platform_id="linux",
    )
    assert decision.eligible is False
    assert decision.reason == "unsupported_platform"


def test_disabled_setting_and_non_execute_modes_are_ineligible() -> None:
    assert _decision(enabled=False).reason == "disabled"
    assert _decision(run_mode="dry-run").reason == "run_mode_not_execute"

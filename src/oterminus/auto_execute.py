from __future__ import annotations

from dataclasses import dataclass

from oterminus.commands import (
    CommandSpec,
    get_pack_for_command,
    is_command_supported_on_platform,
    is_normal_executable_spec,
)
from oterminus.models import Proposal, ProposalMode, RiskLevel, ValidationResult

ELIGIBLE_PROPOSAL_ORIGINS = frozenset({"direct_command", "deterministic_shortcut", "local_planner"})
ARCHIVE_MUTATION_OPERATIONS = frozenset(
    {"extract_tar", "extract_zip", "create_tar_gz", "create_zip"}
)


@dataclass(frozen=True)
class AutoExecuteDecision:
    eligible: bool
    reason: str


def evaluate_safe_auto_execute(
    *,
    enabled: bool,
    run_mode: object,
    proposal: Proposal,
    validation: ValidationResult,
    proposal_origin: str,
    command_spec: CommandSpec | None,
    rerun_source_history_id: int | None,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
) -> AutoExecuteDecision:
    if not enabled:
        return AutoExecuteDecision(False, "disabled")
    if _run_mode_value(run_mode) != "execute":
        return AutoExecuteDecision(False, "run_mode_not_execute")
    if proposal_origin not in ELIGIBLE_PROPOSAL_ORIGINS:
        return AutoExecuteDecision(False, "proposal_origin")
    if rerun_source_history_id is not None:
        return AutoExecuteDecision(False, "history_rerun")
    if proposal.mode != ProposalMode.STRUCTURED:
        return AutoExecuteDecision(False, "proposal_mode")
    if not validation.accepted:
        return AutoExecuteDecision(False, "validation_rejected")
    if validation.risk_level != RiskLevel.SAFE:
        return AutoExecuteDecision(False, "risk_not_safe")
    if validation.warnings:
        return AutoExecuteDecision(False, "validation_warnings")
    if validation.reasons:
        return AutoExecuteDecision(False, "validation_reasons")
    if not validation.rendered_command:
        return AutoExecuteDecision(False, "missing_rendered_command")
    if not validation.argv:
        return AutoExecuteDecision(False, "missing_argv")
    if command_spec is None:
        return AutoExecuteDecision(False, "missing_command_spec")
    if not is_normal_executable_spec(command_spec):
        return AutoExecuteDecision(False, "not_normal_executable")

    pack_id = get_pack_for_command(command_spec.name)
    if pack_id is None:
        return AutoExecuteDecision(False, "command_pack_unknown")
    if pack_id in (disabled_pack_ids or frozenset()):
        return AutoExecuteDecision(False, "command_pack_disabled")
    if not is_command_supported_on_platform(command_spec, platform_id):
        return AutoExecuteDecision(False, "unsupported_platform")
    if command_spec.network_touching:
        return AutoExecuteDecision(False, "network_touching")
    if proposal.command_family == "project_health" or command_spec.name == "project_health":
        return AutoExecuteDecision(False, "project_health")
    if _is_archive_mutation(proposal):
        return AutoExecuteDecision(False, "archive_mutation")

    return AutoExecuteDecision(True, "eligible")


def _run_mode_value(run_mode: object) -> str:
    value = getattr(run_mode, "value", run_mode)
    return str(value)


def _is_archive_mutation(proposal: Proposal) -> bool:
    if proposal.command_family not in {"tar", "unzip", "zip"}:
        return False
    arguments = proposal.arguments
    if not isinstance(arguments, dict):
        return True
    operation = arguments.get("operation")
    if not isinstance(operation, str):
        return True
    return operation in ARCHIVE_MUTATION_OPERATIONS

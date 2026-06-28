from __future__ import annotations

import json

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from oterminus.models import Proposal, ProposalMode
from oterminus.ollama_client import OllamaPlannerClient, proposal_output_schema
from oterminus.policies import PolicyConfig
from oterminus.prompts import build_system_prompt, build_user_prompt
from oterminus.router import route_request
from oterminus.structured_commands import (
    StructuredCommandError,
    parse_raw_command_as_structured,
    supports_structured_family,
)


class PlannerError(RuntimeError):
    pass


class _ProposalSchemaError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlannerSchemaFailure:
    stage: Literal["initial", "repair"]
    detail: str
    raw_output_preview: str | None = None


_REPAIR_CONTEXT_MAX_CHARS = 2000
_VALIDATION_DETAIL_MAX_CHARS = 1200
_RAW_OUTPUT_PREVIEW_MAX_CHARS = 500


class Planner:
    def __init__(self, client: OllamaPlannerClient, policy: PolicyConfig | None = None):
        self.client = client
        self.policy = policy or PolicyConfig()

    def plan(
        self,
        request: str,
        *,
        trace_callback: Callable[[str], None] | None = None,
    ) -> Proposal:
        route = route_request(request, disabled_pack_ids=self.policy.disabled_command_packs)
        system_prompt = build_system_prompt(disabled_pack_ids=self.policy.disabled_command_packs)
        user_prompt = build_user_prompt(request, route=route)
        raw = self.client.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=proposal_output_schema(),
        )
        try:
            return self._parse_proposal_strict(raw)
        except (_ProposalSchemaError, PlannerError) as first_error:
            first_failure = PlannerSchemaFailure(
                stage="initial",
                detail=str(first_error),
                raw_output_preview=_preview_raw_output(raw),
            )
            _emit_trace(
                trace_callback,
                "planner=schema_validation_failed "
                f"stage={first_failure.stage} detail={_truncate(first_failure.detail, 180)}",
            )
            _emit_trace(trace_callback, "planner=repair_attempt started")
            repair_raw = self.client.chat_json(
                system_prompt=system_prompt,
                user_prompt=build_repair_user_prompt(
                    original_request=request,
                    original_user_prompt=user_prompt,
                    invalid_json=raw,
                    validation_error=first_failure.detail,
                ),
                output_schema=proposal_output_schema(),
            )
            try:
                proposal = self._parse_proposal_strict(repair_raw)
                _emit_trace(trace_callback, "planner=repair_attempt succeeded")
                return proposal
            except _ProposalSchemaError as second_error:
                second_failure = PlannerSchemaFailure(
                    stage="repair",
                    detail=str(second_error),
                    raw_output_preview=_preview_raw_output(repair_raw),
                )
                _emit_trace(
                    trace_callback,
                    "planner=schema_validation_failed "
                    f"stage={second_failure.stage} detail={_truncate(second_failure.detail, 180)}",
                )
                _emit_trace(trace_callback, "planner=repair_attempt failed")
                raise PlannerError(
                    _format_repaired_schema_failure(second_failure.detail)
                ) from second_error
            except PlannerError as second_error:
                second_failure = PlannerSchemaFailure(
                    stage="repair",
                    detail=str(second_error),
                    raw_output_preview=_preview_raw_output(repair_raw),
                )
                _emit_trace(
                    trace_callback,
                    "planner=schema_validation_failed "
                    f"stage={second_failure.stage} detail={_truncate(second_failure.detail, 180)}",
                )
                _emit_trace(trace_callback, "planner=repair_attempt failed")
                raise PlannerError(
                    _format_repaired_schema_failure(second_failure.detail)
                ) from second_error

    @staticmethod
    def parse_proposal(raw_json: str) -> Proposal:
        try:
            return Planner._parse_proposal_strict(raw_json)
        except _ProposalSchemaError as exc:
            raise PlannerError(f"Model output did not match proposal schema: {exc}") from exc

    @staticmethod
    def _parse_proposal_strict(raw_json: str) -> Proposal:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise PlannerError(f"Invalid JSON from model: {exc}") from exc

        _validate_planner_output_contract(payload)

        try:
            proposal = Proposal.model_validate(payload)
        except ValidationError as exc:
            raise _ProposalSchemaError(_validation_error_summary(exc)) from exc

        if not proposal.needs_confirmation:
            raise _ProposalSchemaError(
                "field `needs_confirmation`: Input should be true; got False"
            )

        try:
            return Planner._prefer_structured_rendering(proposal)
        except (StructuredCommandError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                detail = _validation_error_summary(exc)
            else:
                detail = str(exc)
            raise _ProposalSchemaError(_truncate(detail, _VALIDATION_DETAIL_MAX_CHARS)) from exc

    @staticmethod
    def _prefer_structured_rendering(proposal: Proposal) -> Proposal:
        if (
            proposal.command_family
            and proposal.arguments is not None
            and supports_structured_family(proposal.command_family)
        ):
            return Proposal.model_validate(
                {
                    **proposal.model_dump(),
                    "mode": ProposalMode.STRUCTURED.value,
                }
            )

        if proposal.mode == ProposalMode.STRUCTURED or not proposal.command:
            return proposal

        parsed = parse_raw_command_as_structured(proposal.command)
        if parsed is None:
            return proposal

        command_family, arguments = parsed
        if proposal.command_family and proposal.command_family != command_family:
            return proposal

        return Proposal.model_validate(
            {
                **proposal.model_dump(),
                "mode": ProposalMode.STRUCTURED.value,
                "command_family": command_family,
                "arguments": arguments,
                "command": None,
            }
        )


def build_repair_user_prompt(
    *,
    original_request: str,
    original_user_prompt: str,
    invalid_json: str,
    validation_error: str,
) -> str:
    return (
        "The previous response did not match the required Proposal schema.\n\n"
        "Return JSON only. Do not return markdown. Do not return prose before or after the JSON.\n"
        "Preserve the original user intent while correcting only the schema and shape.\n\n"
        "Original user request:\n"
        f"{_truncate(original_request, _REPAIR_CONTEXT_MAX_CHARS)}\n\n"
        "Original planner context:\n"
        f"{_truncate(original_user_prompt, _REPAIR_CONTEXT_MAX_CHARS)}\n\n"
        "Invalid JSON returned:\n"
        f"{_truncate(invalid_json, _REPAIR_CONTEXT_MAX_CHARS)}\n\n"
        "Validation error:\n"
        f"{_truncate(validation_error, _VALIDATION_DETAIL_MAX_CHARS)}\n\n"
        "Return one corrected JSON object only. Every corrected object must include action_type, "
        "mode, command_family, arguments, command, summary, explanation, risk_level, "
        "needs_confirmation, and notes.\n"
        '- action_type must be exactly "shell_command".\n'
        '- mode must be exactly "structured" or "experimental".\n'
        "- Command names such as `cat`, `ls`, `file`, or `grep` must not be used as action_type "
        "or mode.\n"
        "- needs_confirmation must be true.\n"
        "- Structured proposals require command_family and arguments.\n"
        "- Structured proposals must set command to null.\n"
        "- Experimental proposals require command.\n"
        "- Experimental proposals must set command_family and arguments to null.\n\n"
        "Valid structured shape:\n"
        '{"action_type":"shell_command","mode":"structured","command_family":"...",'
        '"arguments":{},"command":null,"summary":"...","explanation":"...","risk_level":"safe",'
        '"needs_confirmation":true,"notes":[]}\n\n'
        "Valid experimental shape:\n"
        '{"action_type":"shell_command","mode":"experimental","command_family":null,'
        '"arguments":null,"command":"...","summary":"...","explanation":"...","risk_level":"safe",'
        '"needs_confirmation":true,"notes":["experimental"]}'
    )


def _validation_error_summary(exc: ValidationError) -> str:
    details: list[str] = []
    for error in exc.errors()[:3]:
        loc = error.get("loc", ())
        field = ".".join(str(part) for part in loc) if loc else "proposal"
        message = str(error.get("msg", "invalid value"))
        input_value = error.get("input")
        if input_value is None:
            details.append(f"field `{field}`: {message}")
        else:
            details.append(f"field `{field}`: {message}; got {input_value!r}")

    if not details:
        details.append(str(exc))

    remaining = len(exc.errors()) - len(details)
    if remaining > 0:
        details.append(f"{remaining} additional validation error(s)")

    return _truncate("; ".join(details), _VALIDATION_DETAIL_MAX_CHARS)


def _validate_planner_output_contract(payload: object) -> None:
    schema = proposal_output_schema()
    required = tuple(schema["required"])  # type: ignore[index]
    properties = schema["properties"]  # type: ignore[index]

    if not isinstance(payload, dict):
        raise _ProposalSchemaError("proposal: Input should be a JSON object.")

    missing = [field for field in required if field not in payload]
    if missing:
        raise _ProposalSchemaError(f"field `{missing[0]}`: Field required")

    extra = sorted(set(payload) - set(properties))
    if extra:
        raise _ProposalSchemaError(f"field `{extra[0]}`: Extra inputs are not permitted")

    if payload["action_type"] != "shell_command":
        raise _ProposalSchemaError(
            f"field `action_type`: Input should be 'shell_command'; got {payload['action_type']!r}"
        )

    if payload["mode"] not in {"structured", "experimental"}:
        raise _ProposalSchemaError(
            f"field `mode`: Input should be 'structured' or 'experimental'; got {payload['mode']!r}"
        )

    _validate_nullable_string(payload, "command_family")
    _validate_nullable_string(payload, "command")
    _validate_required_string(payload, "summary")
    _validate_required_string(payload, "explanation")

    if payload["arguments"] is not None and not isinstance(payload["arguments"], dict):
        raise _ProposalSchemaError("field `arguments`: Input should be an object or null")

    if payload["risk_level"] not in {"safe", "write", "dangerous", None}:
        raise _ProposalSchemaError(
            "field `risk_level`: Input should be 'safe', 'write', 'dangerous', or null; "
            f"got {payload['risk_level']!r}"
        )

    if payload["needs_confirmation"] is not True:
        raise _ProposalSchemaError(
            f"field `needs_confirmation`: Input should be true; got {payload['needs_confirmation']!r}"
        )

    notes = payload["notes"]
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise _ProposalSchemaError("field `notes`: Input should be an array of strings")


def _validate_required_string(payload: dict[str, object], field: str) -> None:
    if not isinstance(payload[field], str):
        raise _ProposalSchemaError(f"field `{field}`: Input should be a string")


def _validate_nullable_string(payload: dict[str, object], field: str) -> None:
    if payload[field] is not None and not isinstance(payload[field], str):
        raise _ProposalSchemaError(f"field `{field}`: Input should be a string or null")


def _format_repaired_schema_failure(detail: str) -> str:
    return (
        "the selected model returned JSON, but it did not match OTerminus's required proposal "
        "schema after one repair attempt.\n\n"
        "Try:\n"
        "- `oterminus config set model <another-model>`\n"
        "- `oterminus doctor`\n"
        "- or run the direct command if you already know it.\n\n"
        f"Details: {_truncate(detail, _VALIDATION_DETAIL_MAX_CHARS)}"
    )


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3] + "..."


def _preview_raw_output(raw_output: str) -> str:
    return _truncate(raw_output.replace("\x00", ""), _RAW_OUTPUT_PREVIEW_MAX_CHARS)


def _emit_trace(callback: Callable[[str], None] | None, message: str) -> None:
    if callback is not None:
        callback(message)

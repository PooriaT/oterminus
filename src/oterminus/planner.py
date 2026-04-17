from __future__ import annotations

import json

from pydantic import ValidationError

from oterminus.models import Proposal, ProposalMode
from oterminus.ollama_client import OllamaPlannerClient
from oterminus.prompts import SYSTEM_PROMPT, build_user_prompt
from oterminus.structured_commands import parse_raw_command_as_structured, supports_structured_family


class PlannerError(RuntimeError):
    pass


class Planner:
    def __init__(self, client: OllamaPlannerClient):
        self.client = client

    def plan(self, request: str) -> Proposal:
        raw = self.client.chat_json(system_prompt=SYSTEM_PROMPT, user_prompt=build_user_prompt(request))
        return self.parse_proposal(raw)

    @staticmethod
    def parse_proposal(raw_json: str) -> Proposal:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise PlannerError(f"Invalid JSON from model: {exc}") from exc

        try:
            proposal = Proposal.model_validate(payload)
        except ValidationError as exc:
            raise PlannerError(f"Model output did not match proposal schema: {exc}") from exc

        try:
            return Planner._prefer_structured_rendering(proposal)
        except ValidationError as exc:
            raise PlannerError(f"Model output did not match proposal schema: {exc}") from exc

    @staticmethod
    def _prefer_structured_rendering(proposal: Proposal) -> Proposal:
        if proposal.command_family and proposal.arguments is not None and supports_structured_family(proposal.command_family):
            return Proposal.model_validate(
                {
                    **proposal.model_dump(),
                    "mode": ProposalMode.STRUCTURED.value,
                    "command": None,
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

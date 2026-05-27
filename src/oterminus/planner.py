from __future__ import annotations

import json

from pydantic import ValidationError

from oterminus.models import Proposal, ProposalMode
from oterminus.ollama_client import OllamaPlannerClient
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


class Planner:
    def __init__(self, client: OllamaPlannerClient, policy: PolicyConfig | None = None):
        self.client = client
        self.policy = policy or PolicyConfig()

    def plan(self, request: str) -> Proposal:
        route = route_request(request, disabled_pack_ids=self.policy.disabled_command_packs)
        raw = self.client.chat_json(
            system_prompt=build_system_prompt(disabled_pack_ids=self.policy.disabled_command_packs),
            user_prompt=build_user_prompt(request, route=route),
        )
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
        except (StructuredCommandError, ValidationError) as exc:
            raise PlannerError(f"Model output did not match proposal schema: {exc}") from exc

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

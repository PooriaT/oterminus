from __future__ import annotations

import json

from pydantic import ValidationError

from oterminus.models import Proposal
from oterminus.ollama_client import OllamaPlannerClient
from oterminus.prompts import SYSTEM_PROMPT, build_user_prompt


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
            return Proposal.model_validate(payload)
        except ValidationError as exc:
            raise PlannerError(f"Model output did not match proposal schema: {exc}") from exc

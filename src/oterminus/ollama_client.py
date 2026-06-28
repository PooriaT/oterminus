from __future__ import annotations

import shutil
import subprocess

from ollama import Client, ResponseError

from oterminus.models import ActionType, ProposalMode, RiskLevel


class OllamaClientError(RuntimeError):
    pass


PLANNER_PROPOSAL_REQUIRED_FIELDS = (
    "action_type",
    "mode",
    "command_family",
    "arguments",
    "command",
    "summary",
    "explanation",
    "risk_level",
    "needs_confirmation",
    "notes",
)


def proposal_output_schema() -> dict[str, object]:
    """Return the simple JSON Schema sent to Ollama for planner proposals.

    `Proposal.model_json_schema()` is intentionally not used directly here: it contains
    Pydantic defaults/refs and cannot express the planner-output-only contract that every
    top-level key must be present and `needs_confirmation` must be true. Conditional
    structured-vs-experimental shape constraints are left to `Proposal` post-validation
    instead of `oneOf` so the schema remains small and Ollama-compatible. Keep this schema
    synchronized with `Proposal` via tests.
    """

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action_type": {"type": "string", "enum": [ActionType.SHELL_COMMAND.value]},
            "mode": {"type": "string", "enum": [mode.value for mode in ProposalMode]},
            "command_family": {"type": ["string", "null"]},
            "arguments": {"type": ["object", "null"]},
            "command": {"type": ["string", "null"]},
            "summary": {"type": "string"},
            "explanation": {"type": "string"},
            "risk_level": {
                "type": ["string", "null"],
                "enum": [risk.value for risk in RiskLevel] + [None],
            },
            "needs_confirmation": {"type": "boolean", "enum": [True]},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": list(PLANNER_PROPOSAL_REQUIRED_FIELDS),
    }


def is_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


class OllamaPlannerClient:
    def __init__(self, model: str, host: str | None = None):
        self.model = model
        self.client = Client(host=host) if host else Client()

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        output_schema: dict[str, object] | None = None,
        temperature: float = 0,
    ) -> str:
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format=output_schema or "json",
                options={"temperature": temperature},
            )
        except ResponseError as exc:
            raise OllamaClientError(f"Ollama response error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise OllamaClientError(
                "Unable to reach Ollama. Ensure Ollama is running and the model is pulled."
            ) from exc

        message = response.get("message", {})
        content = message.get("content", "")
        if not content:
            raise OllamaClientError("Ollama returned an empty planning response.")
        return content


def list_installed_models() -> list[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise OllamaClientError(
            "Unable to run `ollama list`. Ensure Ollama is installed and available on PATH."
        ) from exc

    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or "`ollama list` failed."
        raise OllamaClientError(message)

    return parse_ollama_list_output(result.stdout)


def parse_ollama_list_output(output: str) -> list[str]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return []

    if lines[0].lower().startswith("name"):
        lines = lines[1:]

    models: list[str] = []
    for line in lines:
        parts = line.split()
        if parts:
            models.append(parts[0])

    return list(dict.fromkeys(models))

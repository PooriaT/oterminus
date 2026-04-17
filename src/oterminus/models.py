from __future__ import annotations

from enum import Enum
import shlex
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from oterminus.structured_commands import StructuredCommandError, validate_structured_arguments


class RiskLevel(str, Enum):
    SAFE = "safe"
    WRITE = "write"
    DANGEROUS = "dangerous"


class ActionType(str, Enum):
    SHELL_COMMAND = "shell_command"


class ProposalMode(str, Enum):
    RAW = "raw"
    STRUCTURED = "structured"


class Proposal(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action_type: ActionType = ActionType.SHELL_COMMAND
    summary: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    risk_level: Optional[RiskLevel] = None
    needs_confirmation: bool = True
    notes: list[str] = Field(default_factory=list)
    mode: ProposalMode = ProposalMode.RAW
    command_family: Optional[str] = Field(default=None, min_length=1)
    arguments: Optional[dict[str, Any]] = None
    command: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="before")
    @classmethod
    def infer_mode(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        command = payload.get("command")
        command_family = payload.get("command_family")
        arguments = payload.get("arguments")

        if isinstance(command, str):
            payload["command"] = command.strip() or None
        if isinstance(command_family, str):
            payload["command_family"] = command_family.strip() or None
        if payload.get("notes") is None:
            payload["notes"] = []

        if payload.get("mode") is None:
            has_command = payload.get("command") is not None
            has_structured_fields = payload.get("command_family") is not None or arguments is not None
            payload["mode"] = ProposalMode.STRUCTURED if has_structured_fields and not has_command else ProposalMode.RAW

        return payload

    @model_validator(mode="after")
    def validate_shape(self) -> Proposal:
        if self.mode == ProposalMode.RAW and not self.command:
            raise ValueError("Raw proposals require a command.")

        if self.mode == ProposalMode.STRUCTURED and not self.command_family:
            raise ValueError("Structured proposals require command_family.")

        if self.arguments is not None and not self.command_family:
            raise ValueError("Structured arguments require command_family.")

        if self.arguments is not None and any(not key.strip() for key in self.arguments):
            raise ValueError("Structured argument keys must be non-empty strings.")

        if self.mode == ProposalMode.STRUCTURED or self.arguments is not None:
            try:
                validated = validate_structured_arguments(self.command_family, self.arguments)
            except StructuredCommandError as exc:
                raise ValueError(str(exc)) from exc
            self.arguments = validated.model_dump()

        if self.command and self.command_family:
            try:
                parsed = shlex.split(self.command)
            except ValueError:
                parsed = []
            if parsed and parsed[0] != self.command_family:
                raise ValueError("command_family must match the raw command base when both are present.")

        return self

    def executable_command(self) -> str | None:
        return self.command


class ValidationResult(BaseModel):
    accepted: bool
    risk_level: RiskLevel
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rendered_command: Optional[str] = None
    argv: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    command: str
    returncode: int
    stdout: str
    stderr: str

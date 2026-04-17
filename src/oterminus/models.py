from __future__ import annotations

from enum import Enum
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
    STRUCTURED = "structured"
    EXPERIMENTAL = "experimental"


class Proposal(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action_type: ActionType = ActionType.SHELL_COMMAND
    summary: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    risk_level: Optional[RiskLevel] = None
    needs_confirmation: bool = True
    notes: list[str] = Field(default_factory=list)
    mode: ProposalMode = ProposalMode.EXPERIMENTAL
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

        mode = payload.get("mode")
        if mode == "raw":
            notes = payload.get("notes")
            if not isinstance(notes, list):
                notes = []
            migration_note = "Legacy raw mode was normalized to experimental mode."
            if migration_note not in notes:
                notes.append(migration_note)
            payload["notes"] = notes
            has_command = payload.get("command") is not None
            has_arguments = arguments is not None
            has_command_family = payload.get("command_family") is not None
            payload["mode"] = (
                ProposalMode.STRUCTURED
                if has_arguments or (has_command_family and not has_command)
                else ProposalMode.EXPERIMENTAL
            )

        if payload.get("mode") is None:
            has_command = payload.get("command") is not None
            has_arguments = arguments is not None
            has_command_family = payload.get("command_family") is not None
            payload["mode"] = (
                ProposalMode.STRUCTURED
                if has_arguments or (has_command_family and not has_command)
                else ProposalMode.EXPERIMENTAL
            )

        return payload

    @model_validator(mode="after")
    def validate_shape(self) -> Proposal:
        if self.mode == ProposalMode.EXPERIMENTAL and not self.command:
            raise ValueError("Experimental proposals require a command.")

        if self.mode == ProposalMode.STRUCTURED and not self.command_family:
            raise ValueError("Structured proposals require command_family.")

        if self.mode == ProposalMode.STRUCTURED and self.arguments is None:
            raise ValueError("Structured proposals require arguments.")

        if self.mode == ProposalMode.EXPERIMENTAL and self.arguments is not None:
            raise ValueError("Experimental proposals cannot include structured arguments.")

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

        return self

    def executable_command(self) -> str | None:
        return self.command

    @property
    def is_experimental(self) -> bool:
        return self.mode == ProposalMode.EXPERIMENTAL


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

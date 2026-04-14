from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    SAFE = "safe"
    WRITE = "write"
    DANGEROUS = "dangerous"


class ActionType(str, Enum):
    SHELL_COMMAND = "shell_command"


class Proposal(BaseModel):
    action_type: ActionType = ActionType.SHELL_COMMAND
    command: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    risk_level: Optional[RiskLevel] = None
    needs_confirmation: bool = True
    notes: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    accepted: bool
    risk_level: RiskLevel
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    command: str
    returncode: int
    stdout: str
    stderr: str

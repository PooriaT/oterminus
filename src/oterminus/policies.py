from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from oterminus.models import ProposalMode, RiskLevel


@dataclass(frozen=True)
class PolicyConfig:
    mode: RiskLevel = RiskLevel.WRITE
    allow_dangerous: bool = False
    allowed_roots: list[str] = field(default_factory=list)


class ConfirmationLevel(str, Enum):
    STANDARD = "standard"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


def is_risk_allowed(risk: RiskLevel, policy: PolicyConfig) -> bool:
    if risk == RiskLevel.DANGEROUS:
        return policy.allow_dangerous and policy.mode == RiskLevel.DANGEROUS
    if risk == RiskLevel.WRITE:
        return policy.mode in {RiskLevel.WRITE, RiskLevel.DANGEROUS}
    return True


def confirmation_level(mode: ProposalMode, risk: RiskLevel) -> ConfirmationLevel:
    if mode == ProposalMode.EXPERIMENTAL:
        return ConfirmationLevel.VERY_STRONG
    if risk == RiskLevel.DANGEROUS:
        return ConfirmationLevel.STRONG
    return ConfirmationLevel.STANDARD

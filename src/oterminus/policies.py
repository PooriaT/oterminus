from __future__ import annotations

from dataclasses import dataclass, field

from oterminus.models import RiskLevel


@dataclass(frozen=True)
class PolicyConfig:
    mode: RiskLevel = RiskLevel.WRITE
    allow_dangerous: bool = False
    allowed_roots: list[str] = field(default_factory=list)


def is_risk_allowed(risk: RiskLevel, policy: PolicyConfig) -> bool:
    if risk == RiskLevel.DANGEROUS:
        return policy.allow_dangerous and policy.mode == RiskLevel.DANGEROUS
    if risk == RiskLevel.WRITE:
        return policy.mode in {RiskLevel.WRITE, RiskLevel.DANGEROUS}
    return True


def requires_strong_confirmation(risk: RiskLevel) -> bool:
    return risk == RiskLevel.DANGEROUS

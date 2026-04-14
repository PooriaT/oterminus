from __future__ import annotations

import os
from dataclasses import dataclass, field

from oterminus.models import RiskLevel
from oterminus.policies import PolicyConfig


@dataclass(frozen=True)
class AppConfig:
    model_name: str = "gemma4"
    timeout_seconds: int = 60
    policy: PolicyConfig = field(default_factory=PolicyConfig)



def load_config() -> AppConfig:
    model_name = os.getenv("OTERMINUS_MODEL", "gemma4")
    timeout_seconds = int(os.getenv("OTERMINUS_TIMEOUT_SECONDS", "60"))
    mode = RiskLevel(os.getenv("OTERMINUS_POLICY_MODE", RiskLevel.WRITE.value))
    allow_dangerous = os.getenv("OTERMINUS_ALLOW_DANGEROUS", "false").lower() == "true"
    roots = os.getenv("OTERMINUS_ALLOWED_ROOTS", "")
    allowed_roots = [root for root in roots.split(":") if root]

    return AppConfig(
        model_name=model_name,
        timeout_seconds=timeout_seconds,
        policy=PolicyConfig(mode=mode, allow_dangerous=allow_dangerous, allowed_roots=allowed_roots),
    )

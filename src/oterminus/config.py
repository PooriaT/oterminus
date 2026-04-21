from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oterminus.models import RiskLevel
from oterminus.policies import PolicyConfig


@dataclass(frozen=True)
class AppConfig:
    timeout_seconds: int = 60
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    model: str | None = None
    audit_log_path: Path = field(default_factory=lambda: Path.home() / ".oterminus" / "audit.jsonl")


def get_user_config_path() -> Path:
    override = os.getenv("OTERMINUS_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".oterminus" / "config.json"


def load_user_config() -> dict[str, Any]:
    path = get_user_config_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}
    return payload


def save_user_config(payload: dict[str, Any]) -> None:
    path = get_user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_config() -> AppConfig:
    timeout_seconds = int(os.getenv("OTERMINUS_TIMEOUT_SECONDS", "60"))
    mode = RiskLevel(os.getenv("OTERMINUS_POLICY_MODE", RiskLevel.WRITE.value))
    allow_dangerous = os.getenv("OTERMINUS_ALLOW_DANGEROUS", "false").lower() == "true"
    roots = os.getenv("OTERMINUS_ALLOWED_ROOTS", "")
    allowed_roots = [root for root in roots.split(":") if root]

    user_config = load_user_config()
    model = user_config.get("model")
    if not isinstance(model, str) or not model.strip():
        model = None
    configured_audit_path = os.getenv("OTERMINUS_AUDIT_LOG_PATH")
    if not configured_audit_path:
        configured_audit_path = user_config.get("audit_log_path")
    if isinstance(configured_audit_path, str) and configured_audit_path.strip():
        audit_log_path = Path(configured_audit_path).expanduser()
    else:
        audit_log_path = Path.home() / ".oterminus" / "audit.jsonl"

    return AppConfig(
        timeout_seconds=timeout_seconds,
        policy=PolicyConfig(mode=mode, allow_dangerous=allow_dangerous, allowed_roots=allowed_roots),
        model=model,
        audit_log_path=audit_log_path,
    )

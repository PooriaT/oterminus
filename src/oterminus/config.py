from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oterminus.models import RiskLevel
from oterminus.commands import available_pack_ids
from oterminus.policies import PolicyConfig

_COMMAND_PROFILE_DISABLED_PACKS: dict[str, frozenset[str]] = {
    "beginner": frozenset(
        {"archive", "dangerous", "git", "macos", "network", "process", "project"}
    ),
    "safe": frozenset({"dangerous", "network", "project"}),
    "developer": frozenset({"dangerous", "network"}),
    "power": frozenset({"dangerous"}),
}


@dataclass(frozen=True)
class AppConfig:
    timeout_seconds: int = 60
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    model: str | None = None
    audit_log_path: Path = field(default_factory=lambda: Path.home() / ".oterminus" / "audit.jsonl")
    audit_enabled: bool = True
    audit_redact: bool = True
    history_enabled: bool = False
    history_path: Path = field(default_factory=lambda: Path.home() / ".oterminus" / "history.jsonl")
    history_limit: int = 100
    history_redact: bool = True
    max_output_chars: int = 20000
    explain_failures: bool = False
    failure_explanation_max_chars: int = 4000


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
    audit_enabled = _env_flag("OTERMINUS_AUDIT_ENABLED", default=True)
    audit_redact = _env_flag("OTERMINUS_AUDIT_REDACT", default=True)
    history_enabled = _env_flag("OTERMINUS_HISTORY_ENABLED", default=False)
    history_limit = int(os.getenv("OTERMINUS_HISTORY_LIMIT", "100"))
    history_path_raw = os.getenv("OTERMINUS_HISTORY_PATH")
    history_path = (
        Path(history_path_raw).expanduser()
        if history_path_raw
        else Path.home() / ".oterminus" / "history.jsonl"
    )
    history_redact = _env_flag("OTERMINUS_HISTORY_REDACT", default=audit_redact)
    max_output_chars = _positive_int_env("OTERMINUS_MAX_OUTPUT_CHARS", default=20000)
    explain_failures = _env_flag("OTERMINUS_EXPLAIN_FAILURES", default=False)
    failure_explanation_max_chars = _positive_int_env(
        "OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS", default=4000
    )
    command_profile = _parse_command_profile(os.getenv("OTERMINUS_COMMAND_PROFILE"))
    profile_disabled_command_packs = _disabled_packs_for_profile(command_profile)
    disabled_command_packs = _parse_disabled_command_packs(
        os.getenv("OTERMINUS_DISABLED_COMMAND_PACKS", "")
    )
    disabled_command_packs = profile_disabled_command_packs | disabled_command_packs

    return AppConfig(
        timeout_seconds=timeout_seconds,
        policy=PolicyConfig(
            mode=mode,
            allow_dangerous=allow_dangerous,
            allowed_roots=allowed_roots,
            disabled_command_packs=disabled_command_packs,
        ),
        model=model,
        audit_log_path=audit_log_path,
        audit_enabled=audit_enabled,
        audit_redact=audit_redact,
        history_enabled=history_enabled,
        history_path=history_path,
        history_limit=history_limit,
        history_redact=history_redact,
        max_output_chars=max_output_chars,
        explain_failures=explain_failures,
        failure_explanation_max_chars=failure_explanation_max_chars,
    )


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_disabled_command_packs(raw: str) -> frozenset[str]:
    values = frozenset(part.strip().lower() for part in raw.split(",") if part.strip())
    unknown = sorted(values - set(available_pack_ids()))
    if unknown:
        msg = (
            "Unknown value(s) in OTERMINUS_DISABLED_COMMAND_PACKS: "
            + ", ".join(unknown)
            + ". Available pack IDs: "
            + ", ".join(available_pack_ids())
        )
        raise ValueError(msg)
    return values


def _parse_command_profile(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if not normalized:
        return None
    if normalized not in _COMMAND_PROFILE_DISABLED_PACKS:
        msg = (
            "Unknown value for OTERMINUS_COMMAND_PROFILE: "
            + normalized
            + ". Supported profiles: "
            + ", ".join(sorted(_COMMAND_PROFILE_DISABLED_PACKS))
        )
        raise ValueError(msg)
    return normalized


def _disabled_packs_for_profile(profile: str | None) -> frozenset[str]:
    if profile is None:
        return frozenset()
    return _COMMAND_PROFILE_DISABLED_PACKS[profile]


def _positive_int_env(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 1 else default

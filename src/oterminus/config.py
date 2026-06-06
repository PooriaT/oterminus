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
_DOTENV_FILENAME = ".env"


@dataclass(frozen=True)
class AppConfig:
    timeout_seconds: int = 60
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    auto_execute_safe: bool = False
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
    override = _env_value("OTERMINUS_CONFIG_PATH", _load_dotenv_values())
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
    dotenv_values = _load_dotenv_values()
    timeout_seconds = int(_env_value("OTERMINUS_TIMEOUT_SECONDS", dotenv_values, "60"))
    mode = RiskLevel(_env_value("OTERMINUS_POLICY_MODE", dotenv_values, RiskLevel.WRITE.value))
    allow_dangerous = (
        _env_value("OTERMINUS_ALLOW_DANGEROUS", dotenv_values, "false").lower() == "true"
    )
    roots = _env_value("OTERMINUS_ALLOWED_ROOTS", dotenv_values, "")
    allowed_roots = [root for root in roots.split(":") if root]

    user_config = load_user_config()
    model = user_config.get("model")
    if not isinstance(model, str) or not model.strip():
        model = None
    configured_audit_path = _env_value("OTERMINUS_AUDIT_LOG_PATH", dotenv_values)
    if not configured_audit_path:
        configured_audit_path = user_config.get("audit_log_path")
    if isinstance(configured_audit_path, str) and configured_audit_path.strip():
        audit_log_path = Path(configured_audit_path).expanduser()
    else:
        audit_log_path = Path.home() / ".oterminus" / "audit.jsonl"
    audit_enabled = _env_flag("OTERMINUS_AUDIT_ENABLED", default=True, dotenv_values=dotenv_values)
    audit_redact = _env_flag("OTERMINUS_AUDIT_REDACT", default=True, dotenv_values=dotenv_values)
    history_enabled = _env_flag(
        "OTERMINUS_HISTORY_ENABLED", default=False, dotenv_values=dotenv_values
    )
    history_limit = int(_env_value("OTERMINUS_HISTORY_LIMIT", dotenv_values, "100"))
    history_path_raw = _env_value("OTERMINUS_HISTORY_PATH", dotenv_values)
    history_path = (
        Path(history_path_raw).expanduser()
        if history_path_raw
        else Path.home() / ".oterminus" / "history.jsonl"
    )
    history_redact = _env_flag(
        "OTERMINUS_HISTORY_REDACT", default=audit_redact, dotenv_values=dotenv_values
    )
    max_output_chars = _positive_int_env(
        "OTERMINUS_MAX_OUTPUT_CHARS", default=20000, dotenv_values=dotenv_values
    )
    explain_failures = _env_flag(
        "OTERMINUS_EXPLAIN_FAILURES", default=False, dotenv_values=dotenv_values
    )
    failure_explanation_max_chars = _positive_int_env(
        "OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS", default=4000, dotenv_values=dotenv_values
    )
    auto_execute_safe = _env_flag(
        "OTERMINUS_AUTO_EXECUTE_SAFE", default=False, dotenv_values=dotenv_values
    )
    command_profile = _parse_command_profile(_env_value("OTERMINUS_COMMAND_PROFILE", dotenv_values))
    profile_disabled_command_packs = _disabled_packs_for_profile(command_profile)
    disabled_command_packs = _parse_disabled_command_packs(
        _env_value("OTERMINUS_DISABLED_COMMAND_PACKS", dotenv_values, "")
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
        auto_execute_safe=auto_execute_safe,
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


def _env_value(
    name: str, dotenv_values: dict[str, str] | None = None, default: str | None = None
) -> str | None:
    raw = os.getenv(name)
    if raw is not None:
        return raw
    if dotenv_values is not None and name in dotenv_values:
        return dotenv_values[name]
    return default


def _env_flag(name: str, *, default: bool, dotenv_values: dict[str, str] | None = None) -> bool:
    raw = _env_value(name, dotenv_values)
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


def _positive_int_env(
    name: str, *, default: int, dotenv_values: dict[str, str] | None = None
) -> int:
    raw = _env_value(name, dotenv_values)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 1 else default


def _load_dotenv_values(path: Path | None = None) -> dict[str, str]:
    dotenv_path = path or Path.cwd() / _DOTENV_FILENAME
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    except OSError:
        return {}

    values: dict[str, str] = {}
    for line in lines:
        parsed = _parse_dotenv_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if key.startswith("OTERMINUS_"):
            values[key] = value
    return values


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", maxsplit=1)
    key = key.strip()
    if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    elif "#" in value:
        value = value.split("#", maxsplit=1)[0].rstrip()
    return key, value

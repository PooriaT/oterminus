from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
    field_validator,
)

from oterminus.commands import available_pack_ids
from oterminus.models import RiskLevel
from oterminus.policies import PolicyConfig
from oterminus.terminal_style import ColorMode

CURRENT_USER_CONFIG_SCHEMA_VERSION = 1
PositiveConfigInt = Annotated[int, Field(strict=True, gt=0)]

_COMMAND_PROFILE_DISABLED_PACKS: dict[str, frozenset[str]] = {
    "beginner": frozenset(
        {"archive", "dangerous", "git", "macos", "network", "process", "project"}
    ),
    "safe": frozenset({"dangerous", "network", "project"}),
    "developer": frozenset({"dangerous", "network"}),
    "power": frozenset({"dangerous"}),
}
_COMMAND_PROFILE_DESCRIPTIONS: dict[str, str] = {
    "beginner": "Most restrictive; disables advanced and higher-risk command packs.",
    "safe": "Balanced default; keeps local inspection tools and disables riskier packs.",
    "developer": "Enables most local developer workflows while keeping dangerous and network packs off.",
    "power": "Broadest normal profile; only the dangerous pack stays disabled.",
}
_DOTENV_FILENAME = ".env"


class ConfigError(RuntimeError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


class ConfigValueSource(str, Enum):
    ENVIRONMENT = "environment"
    DOTENV = "dotenv"
    USER_CONFIG = "user_config"
    DEFAULT = "default"
    DERIVED = "derived"


class UserConfigReadStatus(str, Enum):
    MISSING = "missing"
    VALID = "valid"
    INVALID_JSON = "invalid_json"
    NON_OBJECT_JSON = "non_object_json"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    VALIDATION_ERROR = "validation_error"
    UNREADABLE = "unreadable"


class UserConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=CURRENT_USER_CONFIG_SCHEMA_VERSION, strict=True)
    onboarding_completed: StrictBool = False

    model: StrictStr | None = None
    command_profile: StrictStr | None = None
    disabled_command_packs: list[StrictStr] = Field(default_factory=list)
    policy_mode: RiskLevel = RiskLevel.WRITE
    allowed_roots: list[StrictStr] = Field(default_factory=list)

    auto_execute_safe: StrictBool = False
    timeout_seconds: PositiveConfigInt = 60
    max_output_chars: PositiveConfigInt = 20000
    color_mode: ColorMode = ColorMode.AUTO

    audit_enabled: StrictBool = True
    audit_redact: StrictBool = True
    audit_log_path: StrictStr | None = None

    history_enabled: StrictBool = False
    history_path: StrictStr | None = None
    history_limit: PositiveConfigInt = 100
    history_redact: StrictBool = True

    explain_failures: StrictBool = False
    failure_explanation_max_chars: PositiveConfigInt = 4000

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        if value != CURRENT_USER_CONFIG_SCHEMA_VERSION:
            msg = (
                f"Unsupported user config schema_version {value}; "
                f"expected {CURRENT_USER_CONFIG_SCHEMA_VERSION}."
            )
            raise ValueError(msg)
        return value

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("model must be a nonblank string when provided.")
        return stripped

    @field_validator("command_profile")
    @classmethod
    def validate_command_profile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in _COMMAND_PROFILE_DISABLED_PACKS:
            msg = (
                "Unsupported command_profile "
                f"{value!r}; supported profiles: {', '.join(sorted(_COMMAND_PROFILE_DISABLED_PACKS))}."
            )
            raise ValueError(msg)
        return normalized

    @field_validator("disabled_command_packs")
    @classmethod
    def validate_disabled_command_packs(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        if any(not value for value in normalized):
            raise ValueError("disabled_command_packs entries must be nonblank strings.")
        unknown = sorted(set(normalized) - set(available_pack_ids()))
        if unknown:
            msg = (
                "Unknown disabled_command_packs value(s): "
                + ", ".join(unknown)
                + ". Available pack IDs: "
                + ", ".join(available_pack_ids())
                + "."
            )
            raise ValueError(msg)
        return sorted(set(normalized))

    @field_validator("allowed_roots")
    @classmethod
    def validate_allowed_roots(cls, values: list[str]) -> list[str]:
        stripped = [value.strip() for value in values]
        if any(not value for value in stripped):
            raise ValueError("allowed_roots entries must be nonblank strings.")
        return stripped

    @field_validator("audit_log_path", "history_path")
    @classmethod
    def validate_path_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("path fields must be nonblank strings when provided.")
        return stripped


def safe_default_user_config() -> UserConfig:
    return UserConfig(
        schema_version=CURRENT_USER_CONFIG_SCHEMA_VERSION,
        onboarding_completed=True,
        command_profile="safe",
        policy_mode=RiskLevel.WRITE,
        disabled_command_packs=[],
        allowed_roots=[],
        auto_execute_safe=False,
        audit_enabled=True,
        audit_redact=True,
        history_enabled=False,
        history_redact=True,
        explain_failures=False,
        model=None,
        timeout_seconds=60,
        max_output_chars=20000,
        color_mode=ColorMode.AUTO,
        audit_log_path=None,
        history_path=None,
        history_limit=100,
        failure_explanation_max_chars=4000,
    )


def supported_command_profiles() -> tuple[str, ...]:
    return tuple(_COMMAND_PROFILE_DISABLED_PACKS)


def command_profile_description(profile: str) -> str:
    return _COMMAND_PROFILE_DESCRIPTIONS[profile]


def disabled_packs_for_command_profile(profile: str | None) -> frozenset[str]:
    return _disabled_packs_for_profile(profile)


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
    color_mode: ColorMode = ColorMode.AUTO
    explain_failures: bool = False
    failure_explanation_max_chars: int = 4000


@dataclass(frozen=True)
class UserConfigReadResult:
    status: UserConfigReadStatus
    path: Path
    config: UserConfig | None = None
    error: ConfigError | None = None

    @property
    def exists(self) -> bool:
        return self.status is not UserConfigReadStatus.MISSING


@dataclass(frozen=True)
class ResolvedConfig:
    app_config: AppConfig
    sources: dict[str, ConfigValueSource]
    user_config: UserConfig | None
    config_path: Path
    config_exists: bool


@dataclass(frozen=True)
class _RawConfigValue:
    value: str
    source: ConfigValueSource


def get_user_config_path() -> Path:
    override = _env_value("OTERMINUS_CONFIG_PATH", _load_dotenv_values())
    if override:
        return Path(override).expanduser()
    return Path.home() / ".oterminus" / "config.json"


def read_user_config(path: Path | None = None) -> UserConfigReadResult:
    config_path = path or get_user_config_path()
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return UserConfigReadResult(UserConfigReadStatus.MISSING, config_path)
    except OSError as exc:
        error = ConfigError(config_path, f"Unable to read user config: {exc}")
        return UserConfigReadResult(UserConfigReadStatus.UNREADABLE, config_path, error=error)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        error = ConfigError(config_path, f"Invalid JSON at line {exc.lineno}, column {exc.colno}.")
        return UserConfigReadResult(UserConfigReadStatus.INVALID_JSON, config_path, error=error)

    if not isinstance(payload, dict):
        error = ConfigError(config_path, "User config must be a JSON object.")
        return UserConfigReadResult(UserConfigReadStatus.NON_OBJECT_JSON, config_path, error=error)

    try:
        config = _validate_user_config_payload(payload, config_path)
    except ConfigError as exc:
        status = (
            UserConfigReadStatus.UNSUPPORTED_SCHEMA
            if "Unsupported user config schema_version" in exc.reason
            else UserConfigReadStatus.VALIDATION_ERROR
        )
        return UserConfigReadResult(status, config_path, error=exc)
    return UserConfigReadResult(UserConfigReadStatus.VALID, config_path, config=config)


def load_user_config() -> UserConfig | None:
    result = read_user_config()
    if result.status is UserConfigReadStatus.MISSING:
        return None
    if result.config is None:
        raise result.error or ConfigError(result.path, "Invalid user config.")
    return result.config


def merge_user_config(config: UserConfig | None = None, **updates: object) -> UserConfig:
    unknown = sorted(set(updates) - set(UserConfig.model_fields))
    if unknown:
        raise ConfigError(
            get_user_config_path(), "Unknown user config field(s): " + ", ".join(unknown)
        )
    payload = (
        config.model_dump(mode="python", include=config.model_fields_set)
        if config is not None
        else {}
    )
    payload.update(updates)
    try:
        return UserConfig.model_validate(payload)
    except ValidationError as exc:
        raise ConfigError(get_user_config_path(), _format_validation_error(exc)) from exc


def update_user_config(**updates: object) -> UserConfig:
    current = load_user_config()
    updated = merge_user_config(current, **updates)
    save_user_config(updated)
    return updated


def save_user_config(config: UserConfig, *, include_none: bool = False) -> None:
    explicit_fields = set(config.model_fields_set)
    explicit_fields.add("schema_version")
    payload = config.model_dump(mode="json", include=explicit_fields, exclude_none=not include_none)
    payload["schema_version"] = CURRENT_USER_CONFIG_SCHEMA_VERSION
    UserConfig.model_validate(payload)
    path = get_user_config_path()
    _atomic_write_json(path, payload)


def _validate_user_config_payload(payload: dict[str, Any], path: Path) -> UserConfig:
    normalized = dict(payload)
    raw_schema_version = normalized.get("schema_version")
    if raw_schema_version is None:
        normalized["schema_version"] = CURRENT_USER_CONFIG_SCHEMA_VERSION
        normalized.setdefault("onboarding_completed", True)
    elif (
        isinstance(raw_schema_version, int)
        and raw_schema_version != CURRENT_USER_CONFIG_SCHEMA_VERSION
    ):
        raise ConfigError(
            path,
            f"Unsupported user config schema_version {raw_schema_version}; "
            f"expected {CURRENT_USER_CONFIG_SCHEMA_VERSION}.",
        )
    try:
        return UserConfig.model_validate(normalized)
    except ValidationError as exc:
        raise ConfigError(path, _format_validation_error(exc)) from exc


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except FileNotFoundError:
                pass


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors()[:5]:
        location = ".".join(str(part) for part in error["loc"]) or "config"
        parts.append(f"{location}: {error['msg']}")
    if len(exc.errors()) > 5:
        parts.append(f"{len(exc.errors()) - 5} more validation error(s)")
    return "; ".join(parts)


def load_config() -> AppConfig:
    return resolve_config().app_config


def resolve_config() -> ResolvedConfig:
    dotenv_values = _load_dotenv_values()
    user_result = read_user_config()
    if user_result.status is UserConfigReadStatus.MISSING:
        user_config = None
    elif user_result.config is None:
        raise user_result.error or ConfigError(user_result.path, "Invalid user config.")
    else:
        user_config = user_result.config

    sources: dict[str, ConfigValueSource] = {}

    timeout_seconds, sources["timeout_seconds"] = _resolve_int(
        "timeout_seconds",
        "OTERMINUS_TIMEOUT_SECONDS",
        dotenv_values,
        user_config,
        default=60,
        fallback_on_invalid=False,
    )
    policy_mode, sources["policy.mode"] = _resolve_policy_mode(dotenv_values, user_config)
    allow_dangerous = _resolve_env_only_flag(
        "OTERMINUS_ALLOW_DANGEROUS", dotenv_values, default=False
    )
    sources["policy.allow_dangerous"] = (
        _env_source("OTERMINUS_ALLOW_DANGEROUS", dotenv_values) or ConfigValueSource.DEFAULT
    )
    allowed_roots, sources["policy.allowed_roots"] = _resolve_allowed_roots(
        dotenv_values, user_config
    )

    model = user_config.model if user_config is not None else None
    sources["model"] = (
        ConfigValueSource.USER_CONFIG
        if _user_has_field(user_config, "model")
        else ConfigValueSource.DEFAULT
    )

    audit_log_path, sources["audit_log_path"] = _resolve_path(
        "audit_log_path",
        "OTERMINUS_AUDIT_LOG_PATH",
        dotenv_values,
        user_config,
        default=Path.home() / ".oterminus" / "audit.jsonl",
    )
    audit_enabled, sources["audit_enabled"] = _resolve_flag(
        "audit_enabled", "OTERMINUS_AUDIT_ENABLED", dotenv_values, user_config, default=True
    )
    audit_redact, sources["audit_redact"] = _resolve_flag(
        "audit_redact", "OTERMINUS_AUDIT_REDACT", dotenv_values, user_config, default=True
    )
    history_enabled, sources["history_enabled"] = _resolve_flag(
        "history_enabled", "OTERMINUS_HISTORY_ENABLED", dotenv_values, user_config, default=False
    )
    history_limit, sources["history_limit"] = _resolve_int(
        "history_limit",
        "OTERMINUS_HISTORY_LIMIT",
        dotenv_values,
        user_config,
        default=100,
        fallback_on_invalid=False,
    )
    history_path, sources["history_path"] = _resolve_path(
        "history_path",
        "OTERMINUS_HISTORY_PATH",
        dotenv_values,
        user_config,
        default=Path.home() / ".oterminus" / "history.jsonl",
    )
    history_redact, sources["history_redact"] = _resolve_history_redact(
        dotenv_values, user_config, audit_redact
    )
    max_output_chars, sources["max_output_chars"] = _resolve_int(
        "max_output_chars",
        "OTERMINUS_MAX_OUTPUT_CHARS",
        dotenv_values,
        user_config,
        default=20000,
        fallback_on_invalid=True,
    )
    color_mode, sources["color_mode"] = _resolve_color_mode(dotenv_values, user_config)
    explain_failures, sources["explain_failures"] = _resolve_flag(
        "explain_failures",
        "OTERMINUS_EXPLAIN_FAILURES",
        dotenv_values,
        user_config,
        default=False,
    )
    failure_explanation_max_chars, sources["failure_explanation_max_chars"] = _resolve_int(
        "failure_explanation_max_chars",
        "OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS",
        dotenv_values,
        user_config,
        default=4000,
        fallback_on_invalid=True,
    )
    auto_execute_safe, sources["auto_execute_safe"] = _resolve_flag(
        "auto_execute_safe",
        "OTERMINUS_AUTO_EXECUTE_SAFE",
        dotenv_values,
        user_config,
        default=False,
    )
    command_profile, sources["command_profile"] = _resolve_command_profile(
        dotenv_values, user_config
    )
    profile_disabled_command_packs = _disabled_packs_for_profile(command_profile)
    explicit_disabled_command_packs, sources["disabled_command_packs"] = _resolve_disabled_packs(
        dotenv_values, user_config
    )
    disabled_command_packs = profile_disabled_command_packs | explicit_disabled_command_packs
    sources["policy.disabled_command_packs"] = ConfigValueSource.DERIVED

    return ResolvedConfig(
        app_config=AppConfig(
            timeout_seconds=timeout_seconds,
            policy=PolicyConfig(
                mode=policy_mode,
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
            color_mode=color_mode,
            explain_failures=explain_failures,
            failure_explanation_max_chars=failure_explanation_max_chars,
        ),
        sources=sources,
        user_config=user_config,
        config_path=user_result.path,
        config_exists=user_result.exists,
    )


def _raw_value(name: str, dotenv_values: dict[str, str]) -> _RawConfigValue | None:
    raw = os.getenv(name)
    if raw is not None:
        return _RawConfigValue(raw, ConfigValueSource.ENVIRONMENT)
    if name in dotenv_values:
        return _RawConfigValue(dotenv_values[name], ConfigValueSource.DOTENV)
    return None


def _env_source(name: str, dotenv_values: dict[str, str]) -> ConfigValueSource | None:
    raw = _raw_value(name, dotenv_values)
    return raw.source if raw else None


def _user_has_field(user_config: UserConfig | None, field_name: str) -> bool:
    return user_config is not None and field_name in user_config.model_fields_set


def _resolve_flag(
    field_name: str,
    env_name: str,
    dotenv_values: dict[str, str],
    user_config: UserConfig | None,
    *,
    default: bool,
) -> tuple[bool, ConfigValueSource]:
    raw = _raw_value(env_name, dotenv_values)
    if raw is not None:
        parsed = _parse_bool(raw.value)
        if parsed is None:
            return default, ConfigValueSource.DEFAULT
        return parsed, raw.source
    if _user_has_field(user_config, field_name):
        return bool(getattr(user_config, field_name)), ConfigValueSource.USER_CONFIG
    return default, ConfigValueSource.DEFAULT


def _resolve_env_only_flag(env_name: str, dotenv_values: dict[str, str], *, default: bool) -> bool:
    raw = _raw_value(env_name, dotenv_values)
    if raw is None:
        return default
    parsed = _parse_bool(raw.value)
    return default if parsed is None else parsed


def _resolve_int(
    field_name: str,
    env_name: str,
    dotenv_values: dict[str, str],
    user_config: UserConfig | None,
    *,
    default: int,
    fallback_on_invalid: bool,
) -> tuple[int, ConfigValueSource]:
    raw = _raw_value(env_name, dotenv_values)
    if raw is not None:
        try:
            value = int(raw.value)
        except ValueError:
            if fallback_on_invalid:
                return default, ConfigValueSource.DEFAULT
            raise
        if value < 1 and fallback_on_invalid:
            return default, ConfigValueSource.DEFAULT
        return value, raw.source
    if _user_has_field(user_config, field_name):
        return int(getattr(user_config, field_name)), ConfigValueSource.USER_CONFIG
    return default, ConfigValueSource.DEFAULT


def _resolve_path(
    field_name: str,
    env_name: str,
    dotenv_values: dict[str, str],
    user_config: UserConfig | None,
    *,
    default: Path,
) -> tuple[Path, ConfigValueSource]:
    raw = _raw_value(env_name, dotenv_values)
    if raw is not None and raw.value.strip():
        return Path(raw.value).expanduser(), raw.source
    if _user_has_field(user_config, field_name):
        configured = getattr(user_config, field_name)
        if configured:
            return Path(configured).expanduser(), ConfigValueSource.USER_CONFIG
    return default, ConfigValueSource.DEFAULT


def _resolve_policy_mode(
    dotenv_values: dict[str, str], user_config: UserConfig | None
) -> tuple[RiskLevel, ConfigValueSource]:
    raw = _raw_value("OTERMINUS_POLICY_MODE", dotenv_values)
    if raw is not None:
        return RiskLevel(raw.value), raw.source
    if _user_has_field(user_config, "policy_mode"):
        return user_config.policy_mode, ConfigValueSource.USER_CONFIG
    return RiskLevel.WRITE, ConfigValueSource.DEFAULT


def _resolve_allowed_roots(
    dotenv_values: dict[str, str], user_config: UserConfig | None
) -> tuple[list[str], ConfigValueSource]:
    raw = _raw_value("OTERMINUS_ALLOWED_ROOTS", dotenv_values)
    if raw is not None:
        return [root for root in raw.value.split(":") if root], raw.source
    if _user_has_field(user_config, "allowed_roots"):
        return list(user_config.allowed_roots), ConfigValueSource.USER_CONFIG
    return [], ConfigValueSource.DEFAULT


def _resolve_command_profile(
    dotenv_values: dict[str, str], user_config: UserConfig | None
) -> tuple[str | None, ConfigValueSource]:
    raw = _raw_value("OTERMINUS_COMMAND_PROFILE", dotenv_values)
    if raw is not None:
        return _parse_command_profile(raw.value), raw.source
    if _user_has_field(user_config, "command_profile"):
        return user_config.command_profile, ConfigValueSource.USER_CONFIG
    return None, ConfigValueSource.DEFAULT


def _resolve_disabled_packs(
    dotenv_values: dict[str, str], user_config: UserConfig | None
) -> tuple[frozenset[str], ConfigValueSource]:
    raw = _raw_value("OTERMINUS_DISABLED_COMMAND_PACKS", dotenv_values)
    if raw is not None:
        return _parse_disabled_command_packs(raw.value), raw.source
    if _user_has_field(user_config, "disabled_command_packs"):
        return frozenset(user_config.disabled_command_packs), ConfigValueSource.USER_CONFIG
    return frozenset(), ConfigValueSource.DEFAULT


def _resolve_history_redact(
    dotenv_values: dict[str, str], user_config: UserConfig | None, audit_redact: bool
) -> tuple[bool, ConfigValueSource]:
    raw = _raw_value("OTERMINUS_HISTORY_REDACT", dotenv_values)
    if raw is not None:
        parsed = _parse_bool(raw.value)
        if parsed is None:
            return audit_redact, ConfigValueSource.DERIVED
        return parsed, raw.source
    if _user_has_field(user_config, "history_redact"):
        return user_config.history_redact, ConfigValueSource.USER_CONFIG
    return audit_redact, ConfigValueSource.DERIVED


def _resolve_color_mode(
    dotenv_values: dict[str, str], user_config: UserConfig | None
) -> tuple[ColorMode, ConfigValueSource]:
    raw = _raw_value("OTERMINUS_COLOR", dotenv_values)
    if raw is not None:
        parsed = _parse_color_mode(raw.value)
        if parsed is None:
            return ColorMode.AUTO, ConfigValueSource.DEFAULT
        return parsed, raw.source
    if _user_has_field(user_config, "color_mode"):
        return user_config.color_mode, ConfigValueSource.USER_CONFIG
    return ColorMode.AUTO, ConfigValueSource.DEFAULT


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
    parsed = _parse_bool(raw)
    return default if parsed is None else parsed


def _parse_bool(raw: str) -> bool | None:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


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


def _parse_color_mode(raw: str | None) -> ColorMode | None:
    if raw is None:
        return None
    normalized = raw.strip().lower()
    try:
        return ColorMode(normalized)
    except ValueError:
        return None


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

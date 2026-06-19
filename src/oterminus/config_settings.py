from __future__ import annotations

from dataclasses import dataclass

from oterminus.config import supported_command_profiles
from oterminus.terminal_style import ColorMode


@dataclass(frozen=True)
class ConfigSettingSpec:
    key: str
    env_var: str | None
    value_kind: str


SUPPORTED_MUTABLE_CONFIG_SETTINGS: tuple[ConfigSettingSpec, ...] = (
    ConfigSettingSpec("model", None, "model"),
    ConfigSettingSpec("command_profile", "OTERMINUS_COMMAND_PROFILE", "command_profile"),
    ConfigSettingSpec("auto_execute_safe", "OTERMINUS_AUTO_EXECUTE_SAFE", "bool"),
    ConfigSettingSpec("audit_enabled", "OTERMINUS_AUDIT_ENABLED", "bool"),
    ConfigSettingSpec("audit_redact", "OTERMINUS_AUDIT_REDACT", "bool"),
    ConfigSettingSpec("history_enabled", "OTERMINUS_HISTORY_ENABLED", "bool"),
    ConfigSettingSpec("history_redact", "OTERMINUS_HISTORY_REDACT", "bool"),
    ConfigSettingSpec("explain_failures", "OTERMINUS_EXPLAIN_FAILURES", "bool"),
    ConfigSettingSpec("color_mode", "OTERMINUS_COLOR", "color_mode"),
    ConfigSettingSpec("timeout_seconds", "OTERMINUS_TIMEOUT_SECONDS", "positive_int"),
    ConfigSettingSpec("max_output_chars", "OTERMINUS_MAX_OUTPUT_CHARS", "positive_int"),
)
SUPPORTED_MUTABLE_CONFIG_KEYS: tuple[str, ...] = tuple(
    spec.key for spec in SUPPORTED_MUTABLE_CONFIG_SETTINGS
)
SUPPORTED_MUTABLE_CONFIG_SETTING_BY_KEY: dict[str, ConfigSettingSpec] = {
    spec.key: spec for spec in SUPPORTED_MUTABLE_CONFIG_SETTINGS
}
SUPPORTED_RESET_CONFIG_SETTINGS: tuple[ConfigSettingSpec, ...] = SUPPORTED_MUTABLE_CONFIG_SETTINGS
SUPPORTED_RESET_CONFIG_KEYS: tuple[str, ...] = tuple(
    spec.key for spec in SUPPORTED_RESET_CONFIG_SETTINGS
)

DANGEROUS_CONFIG_KEYS: frozenset[str] = frozenset({"allow_dangerous", "policy.allow_dangerous"})


def parse_config_set_value(key: str, raw_value: str) -> object:
    spec = SUPPORTED_MUTABLE_CONFIG_SETTING_BY_KEY[key]
    value = raw_value.strip()

    if spec.value_kind == "model":
        if value.lower() in {"none", "null"}:
            return None
        if not value:
            raise ValueError("model must be a nonblank string, or none/null to clear it.")
        return value

    if spec.value_kind == "command_profile":
        normalized = value.lower()
        supported = supported_command_profiles()
        if normalized not in supported:
            raise ValueError(
                "command_profile must be one of: " + ", ".join(sorted(supported)) + "."
            )
        return normalized

    if spec.value_kind == "bool":
        parsed = _parse_config_bool(value)
        if parsed is None:
            raise ValueError(f"{key} must be a boolean: true/false, 1/0, yes/no, or on/off.")
        return parsed

    if spec.value_kind == "color_mode":
        normalized = value.lower()
        try:
            return ColorMode(normalized)
        except ValueError as exc:
            raise ValueError("color_mode must be one of: auto, always, never.") from exc

    if spec.value_kind == "positive_int":
        if not value.isdecimal():
            raise ValueError(f"{key} must be a positive base-10 integer.")
        parsed_int = int(value, 10)
        if parsed_int < 1:
            raise ValueError(f"{key} must be greater than zero.")
        return parsed_int

    raise ValueError(f"Unsupported config value parser for {key}.")


def _parse_config_bool(raw: str) -> bool | None:
    normalized = raw.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None

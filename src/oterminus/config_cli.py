from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from oterminus.config import (
    CURRENT_USER_CONFIG_SCHEMA_VERSION,
    ConfigError,
    ConfigValueSource,
    ResolvedConfig,
    UserConfig,
    UserConfigReadResult,
    UserConfigReadStatus,
    get_user_config_path,
    read_user_config,
    resolve_config,
    safe_default_user_config,
    save_user_config,
    update_user_config,
    _load_dotenv_values,
)
from oterminus.config_settings import (
    DANGEROUS_CONFIG_KEYS,
    SUPPORTED_MUTABLE_CONFIG_KEYS,
    SUPPORTED_MUTABLE_CONFIG_SETTING_BY_KEY,
    SUPPORTED_RESET_CONFIG_KEYS,
    parse_config_set_value,
)
from oterminus.onboarding import run_onboarding


CONFIG_COMMANDS: tuple[str, ...] = (
    "path",
    "show",
    "init",
    "validate",
    "edit",
    "get",
    "set",
    "reset",
)
CONFIG_INIT_OPTIONS: tuple[str, ...] = ("--defaults", "--force")
SUPPORTED_MUTABLE_CONFIG_KEYS_TEXT = ", ".join(SUPPORTED_MUTABLE_CONFIG_KEYS)
SUPPORTED_RESET_CONFIG_KEYS_TEXT = ", ".join(SUPPORTED_RESET_CONFIG_KEYS)


@dataclass(frozen=True)
class ConfigInitResult:
    path: Path
    created: bool
    replaced: bool
    read_result: UserConfigReadResult


class ConfigInitService:
    def create_safe_defaults(self, *, force: bool = False) -> ConfigInitResult:
        path = get_user_config_path()
        existing = read_user_config(path)
        if existing.status is UserConfigReadStatus.VALID and not force:
            return ConfigInitResult(path, created=False, replaced=False, read_result=existing)
        if existing.status not in {UserConfigReadStatus.MISSING, UserConfigReadStatus.VALID}:
            raise ConfigError(
                path,
                "Existing config is invalid. Repair or move it before initializing safe defaults.",
            )

        config = safe_default_user_config()
        try:
            save_user_config(config, include_none=True)
        except OSError as exc:
            raise ConfigError(path, f"Unable to write safe default config: {exc}") from exc
        return ConfigInitResult(
            path,
            created=existing.status is UserConfigReadStatus.MISSING,
            replaced=existing.status is UserConfigReadStatus.VALID,
            read_result=existing,
        )


def parse_config_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="oterminus config",
        description="Manage OTerminus configuration without starting the request lifecycle.",
    )
    subparsers = parser.add_subparsers(dest="config_command")

    subparsers.add_parser("path", help="Print the active config path.")
    subparsers.add_parser("show", help="Show the effective runtime configuration.")
    get_parser = subparsers.add_parser(
        "get",
        help="Print one effective safe setting.",
        epilog=f"Supported keys: {SUPPORTED_MUTABLE_CONFIG_KEYS_TEXT}",
    )
    get_parser.add_argument("key", help="Supported config key.")
    set_parser = subparsers.add_parser(
        "set",
        help="Persist one safe setting in the user config.",
        epilog=f"Supported keys: {SUPPORTED_MUTABLE_CONFIG_KEYS_TEXT}",
    )
    set_parser.add_argument("key", help="Supported config key.")
    set_parser.add_argument("value", help="Value to persist.")
    reset_parser = subparsers.add_parser(
        "reset",
        help="Remove one safe persisted setting or all safe persisted settings.",
        epilog=f"Supported keys: {SUPPORTED_RESET_CONFIG_KEYS_TEXT}",
    )
    reset_parser.add_argument("key", nargs="?", help="Supported config key to reset.")
    reset_parser.add_argument(
        "--all-safe",
        action="store_true",
        help="Reset all supported safe user-facing settings.",
    )
    init_parser = subparsers.add_parser("init", help="Create a safe default config.")
    init_parser.add_argument(
        "--defaults",
        action="store_true",
        help="Explicitly create safe non-interactive defaults.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="With --defaults, replace an existing valid config with safe defaults.",
    )
    subparsers.add_parser("validate", help="Validate the active config file.")
    subparsers.add_parser("edit", help="Open the active config in $VISUAL or $EDITOR.")

    args = parser.parse_args(argv)
    if args.config_command == "reset" and (args.key is None) == (not args.all_safe):
        reset_parser.error("reset requires exactly one of <key> or --all-safe")
    if args.config_command is None:
        parser.print_help()
    return args


def run_config_cli(
    argv: list[str],
    *,
    init_service: ConfigInitService | None = None,
    run_editor: Callable[..., subprocess.CompletedProcess[object]] = subprocess.run,
    input_fn: Callable[[str], str] = input,
    stdin_isatty: Callable[[], bool] | None = None,
) -> int:
    args = parse_config_args(argv)
    command = args.config_command
    service = init_service or ConfigInitService()

    if command is None:
        return 0
    if command == "path":
        print(get_user_config_path())
        return 0
    if command == "show":
        return _show_config()
    if command == "get":
        return _get_config(args.key)
    if command == "set":
        return _set_config(args.key, args.value)
    if command == "reset":
        return _reset_config(args.key, all_safe=args.all_safe)
    if command == "init":
        return _init_config(
            defaults=args.defaults,
            force=args.force,
            service=service,
            input_fn=input_fn,
            stdin_isatty=stdin_isatty or sys.stdin.isatty,
        )
    if command == "validate":
        return _validate_config()
    if command == "edit":
        return _edit_config(service=service, run_editor=run_editor)

    print_config_help()
    return 2


def print_config_help() -> None:
    parse_config_args([])


def _init_config(
    *,
    defaults: bool,
    force: bool,
    service: ConfigInitService,
    input_fn: Callable[[str], str],
    stdin_isatty: Callable[[], bool],
) -> int:
    if not defaults:
        if force:
            print("Use `oterminus config init --defaults --force` to replace with defaults.")
            print("Bare `oterminus config init` runs the interactive onboarding wizard.")
            return 2
        if not stdin_isatty():
            print("Interactive config init requires a TTY.")
            print("Use `oterminus config init --defaults` for non-interactive safe defaults.")
            return 1
        result = read_user_config()
        if result.status is UserConfigReadStatus.MISSING:
            existing = None
        elif result.status is UserConfigReadStatus.VALID:
            existing = result.config
        else:
            print(f"Config init failed: existing config is invalid ({result.status.value}).")
            if result.error is not None:
                print(f"Error: {result.error.reason}")
            print(f"Path: {result.path}")
            return 2
        onboarding = run_onboarding(existing=existing, input_fn=input_fn)
        return 0 if onboarding.saved else 1

    try:
        result = service.create_safe_defaults(force=force)
    except ConfigError as exc:
        print(f"Config init failed: {exc.reason}")
        print(f"Path: {exc.path}")
        return 2

    if result.replaced:
        print(f"Replaced config with safe defaults: {result.path}")
        return 0
    if result.created:
        print(f"Created config: {result.path}")
        return 0
    print(f"Config already exists; not overwritten: {result.path}")
    print(
        "Use `oterminus config init --defaults --force` to replace a valid config with safe defaults."
    )
    return 1


def _validate_config() -> int:
    result = read_user_config()
    if result.status is UserConfigReadStatus.VALID and result.config is not None:
        print(f"Path: {result.path}")
        print(f"Schema version: {result.config.schema_version}")
        print("Status: valid")
        return 0
    if result.status is UserConfigReadStatus.MISSING:
        print(f"No config file exists at {result.path}.")
        print("Run `oterminus config init` to create safe defaults.")
        return 1
    print(f"Path: {result.path}")
    print(f"Status: invalid ({result.status.value})")
    if result.error is not None:
        print(f"Error: {result.error.reason}")
    return 2


def _show_config() -> int:
    try:
        resolved = resolve_config()
    except (ConfigError, ValueError) as exc:
        print(f"Configuration error: {exc}")
        return 2

    app = resolved.app_config
    schema_version = (
        str(resolved.user_config.schema_version)
        if resolved.user_config is not None
        else "(no valid file)"
    )
    lines = [
        "OTerminus configuration",
        f"Active config path: {resolved.config_path}",
        f"Config file exists: {_format_bool(resolved.config_exists)}",
        f"Schema version: {schema_version}",
        "",
        "Settings:",
    ]
    rows = [
        ("model", app.model, resolved.sources.get("model")),
        (
            "command_profile",
            _effective_command_profile(
                resolved.user_config, resolved.sources.get("command_profile")
            ),
            resolved.sources.get("command_profile"),
        ),
        (
            "disabled_command_packs",
            _effective_disabled_packs(
                resolved.user_config, resolved.sources.get("disabled_command_packs")
            ),
            resolved.sources.get("disabled_command_packs"),
        ),
        ("policy.mode", app.policy.mode.value, resolved.sources.get("policy.mode")),
        (
            "policy.allow_dangerous",
            app.policy.allow_dangerous,
            resolved.sources.get("policy.allow_dangerous"),
            "environment-only",
        ),
        (
            "policy.allowed_roots",
            app.policy.allowed_roots,
            resolved.sources.get("policy.allowed_roots"),
        ),
        (
            "policy.disabled_command_packs",
            app.policy.disabled_command_packs,
            resolved.sources.get("policy.disabled_command_packs"),
            "derived union",
        ),
        ("auto_execute_safe", app.auto_execute_safe, resolved.sources.get("auto_execute_safe")),
        ("timeout_seconds", app.timeout_seconds, resolved.sources.get("timeout_seconds")),
        ("max_output_chars", app.max_output_chars, resolved.sources.get("max_output_chars")),
        ("color_mode", app.color_mode.value, resolved.sources.get("color_mode")),
        ("audit_enabled", app.audit_enabled, resolved.sources.get("audit_enabled")),
        ("audit_redact", app.audit_redact, resolved.sources.get("audit_redact")),
        ("audit_log_path", app.audit_log_path, resolved.sources.get("audit_log_path")),
        ("history_enabled", app.history_enabled, resolved.sources.get("history_enabled")),
        ("history_path", app.history_path, resolved.sources.get("history_path")),
        ("history_limit", app.history_limit, resolved.sources.get("history_limit")),
        ("history_redact", app.history_redact, resolved.sources.get("history_redact")),
        ("explain_failures", app.explain_failures, resolved.sources.get("explain_failures")),
        (
            "failure_explanation_max_chars",
            app.failure_explanation_max_chars,
            resolved.sources.get("failure_explanation_max_chars"),
        ),
        (
            "OTERMINUS_CONFIG_PATH",
            resolved.config_path,
            _path_selector_source(),
            "external path selector",
        ),
    ]
    for row in rows:
        name, value, source, *note = row
        suffix = f" ({note[0]})" if note else ""
        lines.append(f"- {name}: {_format_value(value)} [source: {_format_source(source)}]{suffix}")
    print("\n".join(lines))
    return 0


def _get_config(key: str) -> int:
    if not _is_supported_config_key(key):
        return 2
    try:
        resolved = resolve_config()
    except (ConfigError, ValueError) as exc:
        print(f"Configuration error: {exc}")
        return 2
    print(f"{key}={_format_config_get_value(key, resolved)}")
    return 0


def _set_config(key: str, raw_value: str) -> int:
    if not _is_supported_config_key(key):
        return 2
    path = get_user_config_path()
    try:
        value = parse_config_set_value(key, raw_value)
    except ValueError as exc:
        print(f"Invalid value for {key}: {exc}")
        return 2

    try:
        update_user_config(**{key: value})
    except ConfigError as exc:
        print(f"Config set failed: {exc.reason}")
        print(f"Path: {exc.path}")
        if read_user_config(path).status is not UserConfigReadStatus.VALID:
            print("Repair the file or run `oterminus config validate` for details.")
        return 2
    except OSError as exc:
        print(f"Config set failed: Unable to write user config: {exc}")
        print(f"Path: {path}")
        return 2

    print(f"Updated {key}={_format_persisted_value(value)} in {path}")
    try:
        resolved = resolve_config()
    except (ConfigError, ValueError) as exc:
        print(f"Note: effective configuration could not be resolved: {exc}")
        return 0
    note = _format_override_note(key, resolved.sources.get(key))
    if note is not None:
        print(note)
    return 0


def _reset_config(key: str | None, *, all_safe: bool) -> int:
    if all_safe:
        keys = SUPPORTED_RESET_CONFIG_KEYS
    else:
        assert key is not None
        if not _is_supported_config_key(key):
            return 2
        keys = (key,)

    path = get_user_config_path()
    result = read_user_config(path)
    if result.status is UserConfigReadStatus.MISSING:
        if all_safe:
            print(
                f"No config file exists at {path}; safe settings are already using "
                "effective defaults or overrides."
            )
        else:
            print(
                f"No config file exists at {path}; {key} is already using the effective "
                "default or overrides."
            )
        _print_reset_override_notes(keys)
        return 0
    if result.status is not UserConfigReadStatus.VALID or result.config is None:
        print(f"Config reset failed: existing config is invalid ({result.status.value}).")
        if result.error is not None:
            print(f"Error: {result.error.reason}")
        print(f"Path: {result.path}")
        print("Repair the file or run `oterminus config validate` for details.")
        return 2

    current = result.config
    explicit_fields = set(current.model_fields_set)
    keys_to_remove = tuple(key for key in keys if key in explicit_fields)
    if not keys_to_remove:
        if all_safe:
            print(f"No persisted safe config values in {path}; nothing to reset.")
            _print_reset_override_notes(keys)
        else:
            print(f"No persisted value for {key} in {path}; nothing to reset.")
            _print_reset_override_notes(keys)
        return 0

    kept_fields = explicit_fields - set(keys_to_remove)
    kept_fields.add("schema_version")
    payload = current.model_dump(mode="python", include=kept_fields)
    payload["schema_version"] = CURRENT_USER_CONFIG_SCHEMA_VERSION
    try:
        updated = UserConfig.model_validate(payload)
        save_user_config(updated, include_none=True)
    except ConfigError as exc:
        print(f"Config reset failed: {exc.reason}")
        print(f"Path: {exc.path}")
        return 2
    except OSError as exc:
        print(f"Config reset failed: Unable to write user config: {exc}")
        print(f"Path: {path}")
        return 2

    if all_safe:
        print(f"Reset safe config keys in {path}: {', '.join(keys_to_remove)}")
    else:
        print(f"Reset {keys_to_remove[0]} in {path}")
    _print_reset_override_notes(keys)
    return 0


def _is_supported_config_key(key: str) -> bool:
    if key in SUPPORTED_MUTABLE_CONFIG_SETTING_BY_KEY:
        return True
    if key in DANGEROUS_CONFIG_KEYS:
        print(
            f"Unsupported config key {key!r}. Dangerous execution is environment-only; "
            "use OTERMINUS_ALLOW_DANGEROUS outside the user config."
        )
        return False
    print(f"Unsupported config key {key!r}. Supported keys: {SUPPORTED_MUTABLE_CONFIG_KEYS_TEXT}.")
    return False


def _print_reset_override_notes(keys: tuple[str, ...]) -> None:
    try:
        resolved = resolve_config()
    except (ConfigError, ValueError) as exc:
        print(f"Note: effective configuration could not be resolved: {exc}")
        return
    for key in keys:
        note = _format_override_note(key, resolved.sources.get(key))
        if note is not None:
            print(note)


def _format_config_get_value(key: str, resolved: ResolvedConfig) -> str:
    app = resolved.app_config
    if key == "model":
        return app.model or ""
    if key == "command_profile":
        profile = _effective_command_profile(
            resolved.user_config, resolved.sources.get("command_profile")
        )
        return profile or ""
    return _format_value(getattr(app, key))


def _format_persisted_value(value: object) -> str:
    return _format_value(value)


def _format_override_note(key: str, source: ConfigValueSource | None) -> str | None:
    if source not in {ConfigValueSource.ENVIRONMENT, ConfigValueSource.DOTENV}:
        return None
    spec = SUPPORTED_MUTABLE_CONFIG_SETTING_BY_KEY[key]
    if spec.env_var is None:
        return None
    location = "environment" if source is ConfigValueSource.ENVIRONMENT else ".env"
    return f"Note: effective value is currently overridden by {spec.env_var} from {location}."


def _edit_config(
    *,
    service: ConfigInitService,
    run_editor: Callable[..., subprocess.CompletedProcess[object]],
) -> int:
    path = get_user_config_path()
    created = False
    if not path.exists():
        try:
            service.create_safe_defaults()
        except ConfigError as exc:
            print(f"Config edit failed during initialization: {exc.reason}")
            print(f"Path: {exc.path}")
            return 2
        created = True
        print(f"Created config: {path}")

    editor_raw = os.getenv("VISUAL") or os.getenv("EDITOR")
    if editor_raw is None:
        print(f"Config path: {path}")
        print("No editor configured. Set VISUAL or EDITOR, or edit this file manually.")
        return 1
    editor_argv = shlex.split(editor_raw)
    if not editor_argv:
        print(f"Config path: {path}")
        print("Editor command is empty after parsing VISUAL/EDITOR.")
        return 1

    proc = run_editor([*editor_argv, str(path)], shell=False, check=False)
    if proc.returncode != 0:
        print(f"Editor exited with status {proc.returncode}; config was not modified further.")
        return proc.returncode

    result = read_user_config(path)
    if result.status is UserConfigReadStatus.VALID and result.config is not None:
        if created:
            print("Config file was created before editing.")
        print(f"Config is valid: {path}")
        print(f"Schema version: {result.config.schema_version}")
        return 0
    print(f"Config is invalid after edit: {path}")
    if result.error is not None:
        print(f"Error: {result.error.reason}")
    print("Invalid edits were preserved. Repair the file and run `oterminus config validate`.")
    return 2


def _effective_command_profile(
    user_config: UserConfig | None, source: ConfigValueSource | None
) -> str | None:
    raw = _raw_setting_for_source("OTERMINUS_COMMAND_PROFILE", source)
    if raw and raw.strip():
        return raw.strip().lower()
    if source is ConfigValueSource.USER_CONFIG and user_config is not None:
        return user_config.command_profile
    return None


def _effective_disabled_packs(
    user_config: UserConfig | None, source: ConfigValueSource | None
) -> list[str]:
    raw = _raw_setting_for_source("OTERMINUS_DISABLED_COMMAND_PACKS", source)
    if raw:
        return sorted(part.strip().lower() for part in raw.split(",") if part.strip())
    if source is ConfigValueSource.USER_CONFIG and user_config is not None:
        return list(user_config.disabled_command_packs)
    return []


def _raw_setting_for_source(name: str, source: ConfigValueSource | None) -> str | None:
    if source is ConfigValueSource.ENVIRONMENT:
        return os.getenv(name)
    if source is ConfigValueSource.DOTENV:
        return _load_dotenv_values().get(name)
    return None


def _path_selector_source() -> ConfigValueSource:
    if os.getenv("OTERMINUS_CONFIG_PATH") is not None:
        return ConfigValueSource.ENVIRONMENT
    if "OTERMINUS_CONFIG_PATH" in _load_dotenv_values():
        return ConfigValueSource.DOTENV
    return ConfigValueSource.DEFAULT


def _format_source(source: ConfigValueSource | None) -> str:
    if source is None:
        return "default"
    if source is ConfigValueSource.DOTENV:
        return ".env"
    if source is ConfigValueSource.USER_CONFIG:
        return "user config"
    return source.value


def _format_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return _format_bool(value)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, frozenset):
        return "[" + ", ".join(sorted(value)) + "]"
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def _format_bool(value: bool) -> str:
    return "true" if value else "false"

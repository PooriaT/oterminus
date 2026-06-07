import json
import os
from pathlib import Path

import pytest

from oterminus.config import (
    CURRENT_USER_CONFIG_SCHEMA_VERSION,
    ConfigError,
    ConfigValueSource,
    UserConfig,
    UserConfigReadStatus,
    get_user_config_path,
    load_config,
    read_user_config,
    resolve_config,
    save_user_config,
    update_user_config,
)
from oterminus.models import RiskLevel
from oterminus.terminal_style import ColorMode


@pytest.fixture(autouse=True)
def _isolate_dotenv_cwd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


def test_load_config_auto_execute_safe_defaults_to_false(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_AUTO_EXECUTE_SAFE", raising=False)

    config = load_config()

    assert config.auto_execute_safe is False


@pytest.mark.parametrize("raw", ["true", "1", "yes", "on", "TRUE"])
def test_load_config_auto_execute_safe_true_values(monkeypatch, tmp_path: Path, raw: str) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_AUTO_EXECUTE_SAFE", raw)

    config = load_config()

    assert config.auto_execute_safe is True


@pytest.mark.parametrize("raw", ["false", "0", "no", "off", "FALSE"])
def test_load_config_auto_execute_safe_false_values(monkeypatch, tmp_path: Path, raw: str) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_AUTO_EXECUTE_SAFE", raw)

    config = load_config()

    assert config.auto_execute_safe is False


def test_load_config_auto_execute_safe_invalid_value_falls_back_to_false(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_AUTO_EXECUTE_SAFE", "sometimes")

    config = load_config()

    assert config.auto_execute_safe is False


def test_load_config_reads_auto_execute_safe_from_local_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_AUTO_EXECUTE_SAFE", raising=False)
    (tmp_path / ".env").write_text("OTERMINUS_AUTO_EXECUTE_SAFE=true\n", encoding="utf-8")

    config = load_config()

    assert config.auto_execute_safe is True


def test_load_config_exported_env_overrides_local_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_AUTO_EXECUTE_SAFE", "false")
    (tmp_path / ".env").write_text("OTERMINUS_AUTO_EXECUTE_SAFE=true\n", encoding="utf-8")

    config = load_config()

    assert config.auto_execute_safe is False


def test_load_config_accepts_export_and_quoted_dotenv_values(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_AUTO_EXECUTE_SAFE", raising=False)
    (tmp_path / ".env").write_text(
        "\n# local overrides\nexport OTERMINUS_AUTO_EXECUTE_SAFE='true'\n",
        encoding="utf-8",
    )

    config = load_config()

    assert config.auto_execute_safe is True


def test_dotenv_can_set_user_config_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OTERMINUS_CONFIG_PATH", raising=False)
    config_path = tmp_path / "custom-config.json"
    (tmp_path / ".env").write_text(
        f"OTERMINUS_CONFIG_PATH={config_path}\n",
        encoding="utf-8",
    )

    assert get_user_config_path() == config_path


def test_load_config_audit_path_from_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_AUDIT_LOG_PATH", str(tmp_path / "audit-lines.jsonl"))
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))

    config = load_config()

    assert config.audit_log_path == tmp_path / "audit-lines.jsonl"


def test_load_config_invalid_user_audit_path_type_raises_config_error(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"audit_log_path": 123}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_AUDIT_LOG_PATH", raising=False)

    with pytest.raises(ConfigError, match="audit_log_path"):
        load_config()


def test_load_config_audit_controls_default_to_enabled_and_redacted(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_AUDIT_ENABLED", raising=False)
    monkeypatch.delenv("OTERMINUS_AUDIT_REDACT", raising=False)

    config = load_config()

    assert config.audit_enabled is True
    assert config.audit_redact is True


def test_load_config_audit_controls_can_be_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_AUDIT_ENABLED", "false")
    monkeypatch.setenv("OTERMINUS_AUDIT_REDACT", "false")

    config = load_config()

    assert config.audit_enabled is False
    assert config.audit_redact is False


def test_load_config_history_defaults_privacy_safe(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_HISTORY_ENABLED", raising=False)

    config = load_config()

    assert config.history_enabled is False
    assert config.history_limit == 100


def test_load_config_history_env_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_HISTORY_ENABLED", "true")
    monkeypatch.setenv("OTERMINUS_HISTORY_PATH", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("OTERMINUS_HISTORY_LIMIT", "7")
    monkeypatch.setenv("OTERMINUS_HISTORY_REDACT", "false")

    config = load_config()

    assert config.history_enabled is True
    assert config.history_path == tmp_path / "history.jsonl"
    assert config.history_limit == 7
    assert config.history_redact is False


def test_load_config_disabled_command_packs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_DISABLED_COMMAND_PACKS", " dangerous, PROCESS ")

    config = load_config()

    assert config.policy.disabled_command_packs == frozenset({"dangerous", "process"})


def test_load_config_command_profile_unset_preserves_existing_behavior(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_COMMAND_PROFILE", raising=False)
    monkeypatch.delenv("OTERMINUS_DISABLED_COMMAND_PACKS", raising=False)

    config = load_config()

    assert config.policy.disabled_command_packs == frozenset()


def test_load_config_command_profiles(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    expected = {
        "beginner": frozenset(
            {"archive", "dangerous", "git", "macos", "network", "process", "project"}
        ),
        "safe": frozenset({"dangerous", "network", "project"}),
        "developer": frozenset({"dangerous", "network"}),
        "power": frozenset({"dangerous"}),
    }

    for profile, expected_disabled in expected.items():
        monkeypatch.setenv("OTERMINUS_COMMAND_PROFILE", profile.upper())
        monkeypatch.delenv("OTERMINUS_DISABLED_COMMAND_PACKS", raising=False)
        config = load_config()
        assert config.policy.disabled_command_packs == expected_disabled


def test_load_config_rejects_unknown_command_profile(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_COMMAND_PROFILE", "devv")

    import pytest

    with pytest.raises(ValueError, match=r"OTERMINUS_COMMAND_PROFILE"):
        load_config()


def test_load_config_combines_profile_and_explicit_disabled_command_packs(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_COMMAND_PROFILE", "developer")
    monkeypatch.setenv("OTERMINUS_DISABLED_COMMAND_PACKS", "macos, process")

    config = load_config()

    assert config.policy.disabled_command_packs == frozenset(
        {"dangerous", "network", "macos", "process"}
    )


def test_load_config_rejects_unknown_disabled_command_pack(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_DISABLED_COMMAND_PACKS", "notapack")

    import pytest

    with pytest.raises(ValueError, match=r"Unknown value\(s\)"):
        load_config()


def test_load_config_max_output_chars_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_MAX_OUTPUT_CHARS", raising=False)
    config = load_config()
    assert config.max_output_chars == 20000


def test_load_config_max_output_chars_parses_valid_integer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_MAX_OUTPUT_CHARS", "1234")
    config = load_config()
    assert config.max_output_chars == 1234


def test_load_config_max_output_chars_invalid_values_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    for raw in ("abc", "0", "-5"):
        monkeypatch.setenv("OTERMINUS_MAX_OUTPUT_CHARS", raw)
        config = load_config()
        assert config.max_output_chars == 20000


def test_load_config_failure_explanation_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_EXPLAIN_FAILURES", raising=False)
    monkeypatch.delenv("OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS", raising=False)
    config = load_config()
    assert config.explain_failures is False
    assert config.failure_explanation_max_chars == 4000


def test_load_config_failure_explanation_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_EXPLAIN_FAILURES", "true")
    monkeypatch.setenv("OTERMINUS_FAILURE_EXPLANATION_MAX_CHARS", "123")
    config = load_config()
    assert config.explain_failures is True
    assert config.failure_explanation_max_chars == 123


def test_load_config_color_mode_defaults_to_auto(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)

    config = load_config()

    assert config.color_mode is ColorMode.AUTO


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("auto", ColorMode.AUTO),
        ("always", ColorMode.ALWAYS),
        ("never", ColorMode.NEVER),
        ("ALWAYS", ColorMode.ALWAYS),
    ],
)
def test_load_config_color_mode_env_values(
    monkeypatch, tmp_path: Path, raw: str, expected: ColorMode
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_COLOR", raw)

    resolved = resolve_config()

    assert resolved.app_config.color_mode is expected
    assert resolved.sources["color_mode"] is ConfigValueSource.ENVIRONMENT


def test_load_config_color_mode_invalid_env_falls_back_to_auto(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_COLOR", "sparkles")

    resolved = resolve_config()

    assert resolved.app_config.color_mode is ColorMode.AUTO
    assert resolved.sources["color_mode"] is ConfigValueSource.DEFAULT


def test_dotenv_color_mode_overrides_user_config(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"color_mode": "never"}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)
    (tmp_path / ".env").write_text("OTERMINUS_COLOR=always\n", encoding="utf-8")

    resolved = resolve_config()

    assert resolved.app_config.color_mode is ColorMode.ALWAYS
    assert resolved.sources["color_mode"] is ConfigValueSource.DOTENV


def test_user_config_color_mode(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"color_mode": "never"}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)

    resolved = resolve_config()

    assert resolved.app_config.color_mode is ColorMode.NEVER
    assert resolved.sources["color_mode"] is ConfigValueSource.USER_CONFIG


def test_read_user_config_missing(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "missing.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    result = read_user_config()

    assert result.status is UserConfigReadStatus.MISSING
    assert result.config is None
    assert result.exists is False


def test_read_user_config_valid_versioned_file(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": CURRENT_USER_CONFIG_SCHEMA_VERSION,
                "onboarding_completed": False,
                "model": "gemma4",
                "command_profile": "Developer",
                "disabled_command_packs": ["PROCESS", "macos"],
                "policy_mode": "safe",
                "allowed_roots": [str(tmp_path)],
                "timeout_seconds": 12,
                "max_output_chars": 123,
                "color_mode": "always",
                "audit_enabled": False,
                "audit_redact": False,
                "audit_log_path": str(tmp_path / "audit.jsonl"),
                "history_enabled": True,
                "history_path": str(tmp_path / "history.jsonl"),
                "history_limit": 7,
                "history_redact": False,
                "explain_failures": True,
                "failure_explanation_max_chars": 456,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    result = read_user_config()

    assert result.status is UserConfigReadStatus.VALID
    assert result.config is not None
    assert result.config.model == "gemma4"
    assert result.config.command_profile == "developer"
    assert result.config.disabled_command_packs == ["macos", "process"]
    assert result.config.policy_mode is RiskLevel.SAFE
    assert result.config.color_mode is ColorMode.ALWAYS
    assert result.config.onboarding_completed is False


def test_read_user_config_legacy_model_only_is_onboarding_complete(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"model": "gemma4"}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    result = read_user_config()

    assert result.status is UserConfigReadStatus.VALID
    assert result.config is not None
    assert result.config.schema_version == CURRENT_USER_CONFIG_SCHEMA_VERSION
    assert result.config.model == "gemma4"
    assert result.config.onboarding_completed is True


def test_read_user_config_legacy_model_and_audit_path(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    audit_path = tmp_path / "audit.jsonl"
    config_path.write_text(
        json.dumps({"model": "gemma4", "audit_log_path": str(audit_path)}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    config = load_config()

    assert config.model == "gemma4"
    assert config.audit_log_path == audit_path


@pytest.mark.parametrize(
    ("payload", "status", "match"),
    [
        ("{", UserConfigReadStatus.INVALID_JSON, "Invalid JSON"),
        ("[]", UserConfigReadStatus.NON_OBJECT_JSON, "JSON object"),
        ('{"unknown": true}', UserConfigReadStatus.VALIDATION_ERROR, "unknown"),
        ('{"schema_version": 999}', UserConfigReadStatus.UNSUPPORTED_SCHEMA, "schema_version 999"),
        ('{"command_profile": "devv"}', UserConfigReadStatus.VALIDATION_ERROR, "command_profile"),
        (
            '{"disabled_command_packs": ["notapack"]}',
            UserConfigReadStatus.VALIDATION_ERROR,
            "notapack",
        ),
        ('{"policy_mode": "admin"}', UserConfigReadStatus.VALIDATION_ERROR, "policy_mode"),
        ('{"timeout_seconds": 0}', UserConfigReadStatus.VALIDATION_ERROR, "timeout_seconds"),
        ('{"max_output_chars": 0}', UserConfigReadStatus.VALIDATION_ERROR, "max_output_chars"),
        ('{"color_mode": "sometimes"}', UserConfigReadStatus.VALIDATION_ERROR, "color_mode"),
        ('{"history_limit": 0}', UserConfigReadStatus.VALIDATION_ERROR, "history_limit"),
        (
            '{"failure_explanation_max_chars": 0}',
            UserConfigReadStatus.VALIDATION_ERROR,
            "failure_explanation_max_chars",
        ),
        ('{"audit_log_path": 123}', UserConfigReadStatus.VALIDATION_ERROR, "audit_log_path"),
        ('{"model": "   "}', UserConfigReadStatus.VALIDATION_ERROR, "model"),
        ('{"audit_enabled": "false"}', UserConfigReadStatus.VALIDATION_ERROR, "audit_enabled"),
        (
            '{"allow_dangerous": true}',
            UserConfigReadStatus.VALIDATION_ERROR,
            "allow_dangerous",
        ),
    ],
)
def test_read_user_config_invalid_values_are_reported(
    monkeypatch, tmp_path: Path, payload: str, status: UserConfigReadStatus, match: str
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(payload, encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    result = read_user_config()

    assert result.status is status
    assert result.error is not None
    assert match in str(result.error)


def test_user_config_overrides_defaults(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"timeout_seconds": 42, "policy_mode": "safe", "auto_execute_safe": True}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    resolved = resolve_config()

    assert resolved.app_config.timeout_seconds == 42
    assert resolved.app_config.policy.mode is RiskLevel.SAFE
    assert resolved.app_config.auto_execute_safe is True
    assert resolved.sources["timeout_seconds"] is ConfigValueSource.USER_CONFIG


def test_dotenv_overrides_user_config(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"timeout_seconds": 42}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    (tmp_path / ".env").write_text("OTERMINUS_TIMEOUT_SECONDS=12\n", encoding="utf-8")

    resolved = resolve_config()

    assert resolved.app_config.timeout_seconds == 12
    assert resolved.sources["timeout_seconds"] is ConfigValueSource.DOTENV


def test_exported_environment_overrides_dotenv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_TIMEOUT_SECONDS", "99")
    (tmp_path / ".env").write_text("OTERMINUS_TIMEOUT_SECONDS=12\n", encoding="utf-8")

    resolved = resolve_config()

    assert resolved.app_config.timeout_seconds == 99
    assert resolved.sources["timeout_seconds"] is ConfigValueSource.ENVIRONMENT


def test_environment_disabled_packs_replace_persisted_explicit_packs_before_profile_union(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "command_profile": "developer",
                "disabled_command_packs": ["process"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("OTERMINUS_DISABLED_COMMAND_PACKS", "macos")

    config = load_config()

    assert config.policy.disabled_command_packs == frozenset({"dangerous", "network", "macos"})


def test_history_redaction_derived_default_follows_effective_audit_redaction(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"audit_redact": false}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_HISTORY_REDACT", raising=False)

    resolved = resolve_config()

    assert resolved.app_config.audit_redact is False
    assert resolved.app_config.history_redact is False
    assert resolved.sources["history_redact"] is ConfigValueSource.DERIVED


def test_environment_allow_dangerous_continues_working(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OTERMINUS_ALLOW_DANGEROUS", "yes")

    config = load_config()

    assert config.policy.allow_dangerous is True


def test_save_user_config_writes_formatted_json_and_creates_parent(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "nested" / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    save_user_config(UserConfig(model="gemma4"))

    payload = config_path.read_text(encoding="utf-8")
    assert payload.endswith("\n")
    assert json.loads(payload)["schema_version"] == CURRENT_USER_CONFIG_SCHEMA_VERSION
    assert json.loads(payload)["model"] == "gemma4"
    assert oct(os.stat(config_path).st_mode & 0o777) == "0o600"


def test_save_user_config_does_not_persist_implicit_defaults(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    save_user_config(UserConfig(model="gemma4"))

    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "model": "gemma4",
        "schema_version": CURRENT_USER_CONFIG_SCHEMA_VERSION,
    }


def test_update_user_config_does_not_make_history_redact_explicit_default(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    update_user_config(model="gemma4")
    update_user_config(audit_redact=False)
    resolved = resolve_config()

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert "history_redact" not in saved
    assert resolved.app_config.audit_redact is False
    assert resolved.app_config.history_redact is False
    assert resolved.sources["history_redact"] is ConfigValueSource.DERIVED


def test_update_user_config_preserves_unrelated_fields(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"model": "old:model", "audit_log_path": str(tmp_path / "audit.jsonl")}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    updated = update_user_config(model="new:model")

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert updated.model == "new:model"
    assert saved["audit_log_path"] == str(tmp_path / "audit.jsonl")
    assert saved["model"] == "new:model"


def test_update_user_config_does_not_overwrite_invalid_existing_file(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    original = '{"audit_log_path": 123}'
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    with pytest.raises(ConfigError):
        update_user_config(model="gemma4")

    assert config_path.read_text(encoding="utf-8") == original


def test_save_failure_does_not_corrupt_original(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"schema_version": 1, "model": "old:model"}\n', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    def fail_replace(source: str, destination: Path) -> None:
        raise OSError(f"cannot replace {destination} from {source}")

    monkeypatch.setattr("oterminus.config.os.replace", fail_replace)

    with pytest.raises(OSError):
        save_user_config(UserConfig(model="new:model"))

    assert json.loads(config_path.read_text(encoding="utf-8"))["model"] == "old:model"
    assert not list(tmp_path.glob(".config.json.*.tmp"))


def test_cli_reports_invalid_user_config_without_traceback(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from oterminus.cli import main

    config_path = tmp_path / "config.json"
    config_path.write_text('{"audit_log_path": 123}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))

    exit_code = main(["list files"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Configuration error:" in captured.err
    assert "audit_log_path" in captured.err
    assert "Traceback" not in captured.err

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from oterminus.commands.registry import COMMAND_PACKS
from oterminus.config import (
    UserConfig,
    command_profile_description,
    disabled_packs_for_command_profile,
    get_user_config_path,
    merge_user_config,
    safe_default_user_config,
    save_user_config,
    supported_command_profiles,
)
from oterminus.setup import OllamaModelStatus, get_ollama_model_status


@dataclass(frozen=True)
class OnboardingResult:
    completed: bool
    saved: bool
    config: UserConfig | None


_PrintFn = Callable[[str], None]
_InputFn = Callable[[str], str]
_ModelStatusFn = Callable[[], OllamaModelStatus]
_PACK_LABELS = {pack.pack_id: pack.label for pack in COMMAND_PACKS}


def run_onboarding(
    *,
    existing: UserConfig | None,
    input_fn: _InputFn = input,
    output_fn: _PrintFn = print,
    model_status_fn: _ModelStatusFn | None = None,
) -> OnboardingResult:
    base = existing or safe_default_user_config()
    output_fn("OTerminus first-time configuration")
    output_fn("")
    output_fn("This wizard configures core safety and privacy preferences.")
    output_fn("Advanced settings remain editable in the JSON config file.")
    output_fn("")

    command_profile = _ask_command_profile(base.command_profile or "safe", input_fn, output_fn)
    auto_execute_safe = _ask_yes_no(
        "Enable safe auto-execute for narrowly eligible validated local read-only commands?",
        default=base.auto_execute_safe if existing is not None else False,
        input_fn=input_fn,
        output_fn=output_fn,
        before=(
            "Preview and validation still occur. Network, write, dangerous, experimental, "
            "warning-bearing, LLM-planned, project-health, archive-mutation, and rerun "
            "requests do not qualify."
        ),
    )
    audit_enabled = _ask_yes_no(
        "Enable local audit logging?",
        default=base.audit_enabled if existing is not None else True,
        input_fn=input_fn,
        output_fn=output_fn,
        before=(
            "Audit logs remain local and do not store full stdout/stderr, but may still "
            "contain paths and command context. Review logs before sharing them."
        ),
    )
    if audit_enabled:
        audit_redact = _ask_yes_no(
            "Enable audit redaction?",
            default=base.audit_redact if existing is not None else True,
            input_fn=input_fn,
            output_fn=output_fn,
        )
    else:
        audit_redact = True
        output_fn("Audit redaction will remain enabled for future use.")
    history_enabled = _ask_yes_no(
        "Enable persistent request history?",
        default=base.history_enabled if existing is not None else False,
        input_fn=input_fn,
        output_fn=output_fn,
        before=(
            "Persisted history may include commands, local paths, and execution context. "
            "Reruns still require normal validation and confirmation."
        ),
    )
    if history_enabled:
        history_redact = _ask_yes_no(
            "Enable persistent-history redaction?",
            default=base.history_redact if existing is not None else True,
            input_fn=input_fn,
            output_fn=output_fn,
        )
    else:
        history_redact = True
        output_fn("Persistent-history redaction will remain enabled for future use.")
    explain_failures = _ask_yes_no(
        "Enable local Ollama failure explanations after non-zero command exits?",
        default=base.explain_failures if existing is not None else False,
        input_fn=input_fn,
        output_fn=output_fn,
        before=(
            "When enabled, redacted and truncated command output may be sent to the "
            "configured local Ollama model. Suggested next actions are never executed "
            "automatically."
        ),
    )
    model = _ask_ollama_model(
        current_model=base.model,
        input_fn=input_fn,
        output_fn=output_fn,
        model_status_fn=model_status_fn or get_ollama_model_status,
    )

    updated = merge_user_config(
        base if existing is not None else None,
        onboarding_completed=True,
        command_profile=command_profile,
        auto_execute_safe=auto_execute_safe,
        audit_enabled=audit_enabled,
        audit_redact=audit_redact,
        history_enabled=history_enabled,
        history_redact=history_redact,
        explain_failures=explain_failures,
        color_mode=base.color_mode,
        model=model,
    )
    target_path = get_user_config_path()
    _print_summary(updated, target_path, output_fn)
    if not _ask_yes_no(
        "Save this configuration?",
        default=True,
        input_fn=input_fn,
        output_fn=output_fn,
    ):
        output_fn("Configuration was not saved.")
        return OnboardingResult(completed=False, saved=False, config=existing)

    try:
        save_user_config(updated, include_none=True)
    except OSError as exc:
        output_fn(f"Failed to save configuration: {exc}")
        output_fn(f"Path: {target_path}")
        return OnboardingResult(completed=False, saved=False, config=updated)
    output_fn(f"Saved configuration: {target_path}")
    return OnboardingResult(completed=True, saved=True, config=updated)


def save_declined_onboarding(*, output_fn: _PrintFn = print) -> OnboardingResult:
    config = safe_default_user_config()
    try:
        save_user_config(config, include_none=True)
    except OSError as exc:
        output_fn(f"Failed to save declined onboarding state: {exc}")
        output_fn(
            "Continuing with in-memory safe defaults. The onboarding prompt may appear again "
            "because completion could not be persisted."
        )
        return OnboardingResult(completed=False, saved=False, config=config)
    output_fn("Saved safe default configuration.")
    output_fn("You can rerun onboarding later with `oterminus config init`.")
    return OnboardingResult(completed=True, saved=True, config=config)


def _ask_command_profile(default: str, input_fn: _InputFn, output_fn: _PrintFn) -> str:
    profiles = supported_command_profiles()
    output_fn("Command profiles:")
    for index, profile in enumerate(profiles, start=1):
        disabled = disabled_packs_for_command_profile(profile)
        disabled_labels = ", ".join(
            _PACK_LABELS.get(pack_id, pack_id) for pack_id in sorted(disabled)
        )
        output_fn(
            f"{index}. {profile} - {command_profile_description(profile)} "
            f"Disabled packs: {disabled_labels or 'none'}."
        )
    while True:
        answer = input_fn(f"Command profile [{default}]: ").strip().lower()
        if not answer:
            return default
        if answer.isdigit():
            selected = int(answer)
            if 1 <= selected <= len(profiles):
                return profiles[selected - 1]
        if answer in profiles:
            return answer
        output_fn("Choose a listed number or exact profile name.")


def _ask_yes_no(
    prompt: str,
    *,
    default: bool,
    input_fn: _InputFn,
    output_fn: _PrintFn,
    before: str | None = None,
) -> bool:
    if before:
        output_fn(before)
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input_fn(f"{prompt} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        output_fn("Please answer yes or no.")


def _ask_ollama_model(
    *,
    current_model: str | None,
    input_fn: _InputFn,
    output_fn: _PrintFn,
    model_status_fn: _ModelStatusFn,
) -> str | None:
    output_fn("Checking installed Ollama models...")
    status = model_status_fn()
    if not status.cli_installed:
        output_fn("Ollama CLI was not found. Model selection is skipped.")
        output_fn("Direct commands and deterministic local paths remain usable.")
        output_fn("Install Ollama and configure a model later with `oterminus config init`.")
        return current_model
    if not status.service_available:
        output_fn("Ollama is installed but the service is unavailable. Model selection is skipped.")
        if status.error:
            output_fn(f"Ollama status: {status.error}")
        output_fn("Direct commands and deterministic local paths remain usable.")
        output_fn("Start Ollama and configure a model later with `oterminus config init`.")
        return current_model
    models = list(status.models)
    if not models:
        output_fn("No installed Ollama models were found. Model selection is skipped.")
        output_fn("Direct commands and deterministic local paths remain usable.")
        output_fn("Pull a model later and rerun `oterminus config init`.")
        return current_model

    valid_current = current_model if current_model in models else None
    if current_model and valid_current is None:
        output_fn(f"Configured model '{current_model}' is no longer installed.")

    output_fn("Available Ollama models:")
    for index, model in enumerate(models, start=1):
        marker = " (current)" if model == valid_current else ""
        output_fn(f"{index}. {model}{marker}")
    default_label = valid_current or "skip"
    while True:
        answer = input_fn(
            f"Select a model by number, exact name, or press Enter to skip [{default_label}]: "
        ).strip()
        if not answer:
            return valid_current
        if answer.isdigit():
            selected = int(answer)
            if 1 <= selected <= len(models):
                return models[selected - 1]
        if answer in models:
            return answer
        lowered = answer.lower()
        if lowered in {"skip", "none", "no"}:
            return None
        output_fn("Choose a listed model number, exact model name, or skip.")


def _print_summary(config: UserConfig, target_path: Path, output_fn: _PrintFn) -> None:
    output_fn("")
    output_fn("Configuration summary:")
    output_fn(f"- command profile: {config.command_profile or 'not configured'}")
    output_fn(f"- safe auto-execute: {_enabled(config.auto_execute_safe)}")
    output_fn(f"- audit: {_enabled(config.audit_enabled)}")
    output_fn(f"- audit redaction: {_enabled(config.audit_redact)}")
    output_fn(f"- persistent history: {_enabled(config.history_enabled)}")
    output_fn(f"- history redaction: {_enabled(config.history_redact)}")
    output_fn(f"- failure explanations: {_enabled(config.explain_failures)}")
    output_fn(f"- Ollama model: {config.model or 'not configured'}")
    output_fn(f"- target config path: {target_path}")
    output_fn("")


def _enabled(value: bool) -> str:
    return "enabled" if value else "disabled"

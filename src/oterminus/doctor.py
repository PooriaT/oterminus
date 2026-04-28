from __future__ import annotations

import importlib
import os
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from oterminus.commands import COMMAND_PACKS, COMMAND_REGISTRY
from oterminus.config import get_user_config_path, load_config
from oterminus.evals import load_eval_cases
from oterminus.setup import check_ollama_installed, check_ollama_running, get_available_models


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: Status
    message: str
    guidance: str | None = None
    critical: bool = False


@dataclass(frozen=True, slots=True)
class DoctorReport:
    results: tuple[CheckResult, ...]

    @property
    def exit_code(self) -> int:
        if any(item.critical and item.status is Status.FAIL for item in self.results):
            return 2
        return 0


def run_doctor() -> DoctorReport:
    results: list[CheckResult] = []

    results.append(_check_python_version())
    results.append(_check_package_importable())

    cli_installed = check_ollama_installed()
    results.append(_check_ollama_cli(cli_installed))

    ollama_running = False
    models: list[str] = []
    if cli_installed:
        ollama_running = check_ollama_running()
        results.append(_check_ollama_service(ollama_running))
        if ollama_running:
            models_result, models = _check_ollama_models()
            results.append(models_result)
        else:
            results.append(
                CheckResult(
                    name="local ollama models",
                    status=Status.WARN,
                    message="Skipped because Ollama service is unreachable.",
                    guidance="Start Ollama with `ollama serve`, then rerun `oterminus doctor`.",
                )
            )
    else:
        results.append(
            CheckResult(
                name="ollama service",
                status=Status.WARN,
                message="Skipped because Ollama CLI is missing.",
                guidance="Install Ollama, then rerun `oterminus doctor`.",
            )
        )
        results.append(
            CheckResult(
                name="local ollama models",
                status=Status.WARN,
                message="Skipped because Ollama CLI is missing.",
            )
        )

    results.append(_check_configured_model(models, ollama_ready=cli_installed and ollama_running))
    results.append(_check_config_file())
    results.append(_check_audit_path())
    results.append(_check_prompt_toolkit())
    results.append(_check_registry_loads())
    results.append(_check_registry_duplicates())
    results.append(_check_eval_fixtures())
    results.append(_check_dev_tools())

    return DoctorReport(results=tuple(results))


def print_report(report: DoctorReport) -> None:
    print("oterminus doctor")
    for item in report.results:
        print(f"{item.status.value:<5} {item.name}: {item.message}")
        if item.status is not Status.PASS and item.guidance:
            print(f"      ↳ {item.guidance}")

    total = len(report.results)
    failed = sum(1 for item in report.results if item.status is Status.FAIL)
    warned = sum(1 for item in report.results if item.status is Status.WARN)
    print(f"Summary: {total} checks, {failed} failed, {warned} warnings")


def _check_python_version() -> CheckResult:
    if sys.version_info >= (3, 13):
        return CheckResult(name="python version", status=Status.PASS, message=f"Detected {sys.version.split()[0]}.", critical=True)
    return CheckResult(
        name="python version",
        status=Status.FAIL,
        message=f"Detected {sys.version.split()[0]}; requires Python 3.13+.",
        guidance="Install Python 3.13 or newer, then reinstall dependencies.",
        critical=True,
    )


def _check_package_importable() -> CheckResult:
    try:
        importlib.import_module("oterminus")
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult(
            name="oterminus package",
            status=Status.FAIL,
            message="Could not import `oterminus`.",
            guidance=f"Reinstall the package (e.g. `poetry install`). Details: {exc}",
            critical=True,
        )
    return CheckResult(name="oterminus package", status=Status.PASS, message="Import succeeded.", critical=True)


def _check_ollama_cli(installed: bool) -> CheckResult:
    if installed:
        return CheckResult(name="ollama CLI", status=Status.PASS, message="Found on PATH.", critical=True)
    return CheckResult(
        name="ollama CLI",
        status=Status.FAIL,
        message="`ollama` was not found on PATH.",
        guidance="Install Ollama from https://ollama.com/download.",
        critical=True,
    )


def _check_ollama_service(running: bool) -> CheckResult:
    if running:
        return CheckResult(name="ollama service", status=Status.PASS, message="Reachable via `ollama list`.", critical=True)
    return CheckResult(
        name="ollama service",
        status=Status.FAIL,
        message="Ollama service is not reachable.",
        guidance="Start it with `ollama serve`, then rerun the doctor.",
        critical=True,
    )


def _check_ollama_models() -> tuple[CheckResult, list[str]]:
    try:
        models = get_available_models()
    except Exception as exc:
        return (
            CheckResult(
                name="local ollama models",
                status=Status.FAIL,
                message="Could not read local model list.",
                guidance=f"Run `ollama list` manually and fix the error. Details: {exc}",
                critical=True,
            ),
            [],
        )

    if models:
        return (
            CheckResult(
                name="local ollama models",
                status=Status.PASS,
                message=f"Found {len(models)} model(s).",
                critical=True,
            ),
            models,
        )

    return (
        CheckResult(
            name="local ollama models",
            status=Status.FAIL,
            message="No local Ollama models were found.",
            guidance="Pull one with `ollama pull <model>` (for example `ollama pull gemma4`).",
            critical=True,
        ),
        [],
    )


def _check_configured_model(models: list[str], *, ollama_ready: bool) -> CheckResult:
    configured_model = load_config().model
    if not configured_model:
        return CheckResult(
            name="configured model",
            status=Status.WARN,
            message="No model configured in user config yet.",
            guidance="Run OTerminus once to select a model, or set `model` in your config JSON.",
        )

    if not ollama_ready:
        return CheckResult(
            name="configured model",
            status=Status.WARN,
            message=f"Configured model is `{configured_model}` (availability not verified).",
            guidance="Fix Ollama CLI/service checks first, then rerun doctor.",
        )

    if configured_model in models:
        return CheckResult(name="configured model", status=Status.PASS, message=f"`{configured_model}` is installed.", critical=True)

    return CheckResult(
        name="configured model",
        status=Status.FAIL,
        message=f"Configured model `{configured_model}` is not installed locally.",
        guidance="Update config to an installed model or pull the configured model with Ollama.",
        critical=True,
    )


def _check_config_file() -> CheckResult:
    path = get_user_config_path()
    parent = path.parent

    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return CheckResult(
            name="config path",
            status=Status.FAIL,
            message=f"Cannot create config directory at {parent}.",
            guidance=f"Fix directory permissions. Details: {exc}",
            critical=True,
        )

    if path.exists():
        try:
            path.read_text(encoding="utf-8")
        except OSError as exc:
            return CheckResult(
                name="config path",
                status=Status.FAIL,
                message=f"Config file exists but is unreadable: {path}.",
                guidance=f"Check file permissions. Details: {exc}",
                critical=True,
            )

    writable_target = path if path.exists() else parent
    if os.access(writable_target, os.W_OK):
        return CheckResult(name="config path", status=Status.PASS, message=f"Readable/writable at {path}.", critical=True)

    return CheckResult(
        name="config path",
        status=Status.FAIL,
        message=f"Config path is not writable: {path}.",
        guidance="Grant write permission to the config file or its parent directory.",
        critical=True,
    )


def _check_audit_path() -> CheckResult:
    config = load_config()
    if not config.audit_enabled:
        return CheckResult(name="audit log path", status=Status.WARN, message="Audit logging is disabled.")

    audit_dir = config.audit_log_path.expanduser().parent
    try:
        audit_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return CheckResult(
            name="audit log path",
            status=Status.FAIL,
            message=f"Cannot create audit log directory: {audit_dir}.",
            guidance=f"Set OTERMINUS_AUDIT_LOG_PATH to a writable location. Details: {exc}",
            critical=True,
        )

    if os.access(audit_dir, os.W_OK):
        return CheckResult(name="audit log path", status=Status.PASS, message=f"Directory writable: {audit_dir}.", critical=True)

    return CheckResult(
        name="audit log path",
        status=Status.FAIL,
        message=f"Audit log directory is not writable: {audit_dir}.",
        guidance="Set OTERMINUS_AUDIT_LOG_PATH to a writable location.",
        critical=True,
    )


def _check_prompt_toolkit() -> CheckResult:
    try:
        importlib.import_module("prompt_toolkit")
    except Exception:
        return CheckResult(
            name="prompt_toolkit",
            status=Status.WARN,
            message="Not installed; REPL autocomplete will be disabled.",
            guidance="Install dependencies with `poetry install` to enable autocomplete.",
        )
    return CheckResult(name="prompt_toolkit", status=Status.PASS, message="Autocomplete dependency available.")


def _check_registry_loads() -> CheckResult:
    try:
        count = len(COMMAND_REGISTRY)
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult(
            name="command registry",
            status=Status.FAIL,
            message="Command registry could not be loaded.",
            guidance=f"Check command spec metadata and imports. Details: {exc}",
            critical=True,
        )
    return CheckResult(name="command registry", status=Status.PASS, message=f"Loaded {count} command specs.", critical=True)


def _check_registry_duplicates() -> CheckResult:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for pack in COMMAND_PACKS:
        for spec in pack:
            if spec.name in seen:
                duplicates.add(spec.name)
            seen.add(spec.name)

    if not duplicates:
        return CheckResult(name="duplicate command names", status=Status.PASS, message="No duplicate command names detected.", critical=True)
    duplicate_names = ", ".join(sorted(duplicates))
    return CheckResult(
        name="duplicate command names",
        status=Status.FAIL,
        message=f"Duplicate command names detected: {duplicate_names}.",
        guidance="Ensure each command name is unique across COMMAND_PACKS.",
        critical=True,
    )


def _check_eval_fixtures() -> CheckResult:
    fixtures_dir = Path("evals/cases")
    try:
        cases = load_eval_cases(fixtures_dir)
    except Exception as exc:
        return CheckResult(
            name="eval fixtures",
            status=Status.FAIL,
            message="Fixture directory missing or fixtures are invalid.",
            guidance=f"Fix eval fixtures under {fixtures_dir}. Details: {exc}",
            critical=True,
        )

    return CheckResult(name="eval fixtures", status=Status.PASS, message=f"Loaded {len(cases)} fixture case(s).", critical=True)


def _check_dev_tools() -> CheckResult:
    in_repo = Path("pyproject.toml").exists()
    if not in_repo:
        return CheckResult(name="dev tools", status=Status.WARN, message="pyproject.toml not found; dev tool checks skipped.")

    poetry_path = shutil.which("poetry")
    if poetry_path:
        return CheckResult(name="dev tools", status=Status.PASS, message=f"Poetry available at {poetry_path}.")
    return CheckResult(
        name="dev tools",
        status=Status.WARN,
        message="Poetry not found on PATH.",
        guidance="Install Poetry for local development workflows.",
    )

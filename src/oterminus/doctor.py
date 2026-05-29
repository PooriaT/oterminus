from __future__ import annotations

import importlib
import os
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from oterminus.commands import COMMAND_PACKS, COMMAND_REGISTRY, current_platform_id
from oterminus.config import AppConfig, get_user_config_path, load_config
from oterminus.evals import load_eval_cases
from oterminus.setup import check_ollama_installed, check_ollama_running, get_available_models
from oterminus.version import _LOCAL_VERSION, get_version


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


_REPORT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Package/runtime",
        (
            "oterminus version",
            "package import",
            "python runtime",
            "environment",
            "install context",
        ),
    ),
    ("Platform", ("platform",)),
    ("Ollama", ("ollama CLI", "ollama service", "local ollama models")),
    ("Model/config", ("app config", "configured model")),
    ("Local files", ("config path", "audit log path", "history path")),
    ("Optional features", ("prompt_toolkit",)),
    (
        "Developer checks",
        ("command registry", "duplicate command names", "eval fixtures", "dev tools"),
    ),
)


def run_doctor() -> DoctorReport:
    results: list[CheckResult] = []

    results.append(_check_oterminus_version())
    results.append(_check_package_importable())
    results.append(_check_python_runtime())
    results.append(_check_environment())
    results.append(_check_install_context())
    results.append(_check_platform_support())

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
                guidance="Install Ollama from https://ollama.com/download, then rerun `oterminus doctor`.",
            )
        )

    app_config, config_check = _load_app_config()
    results.append(config_check)
    results.append(
        _check_configured_model(app_config, models, ollama_ready=cli_installed and ollama_running)
    )
    results.append(_check_config_file())
    results.append(_check_audit_path(app_config))
    results.append(_check_history_path(app_config))
    results.append(_check_prompt_toolkit())
    results.append(_check_registry_loads())
    results.append(_check_registry_duplicates())
    results.append(_check_eval_fixtures())
    results.append(_check_dev_tools())

    return DoctorReport(results=tuple(results))


def print_report(report: DoctorReport) -> None:
    print("oterminus doctor")
    printed: set[int] = set()
    for group_name, check_names in _REPORT_GROUPS:
        group_results = [
            (index, item)
            for index, item in enumerate(report.results)
            if item.name in check_names and index not in printed
        ]
        if not group_results:
            continue
        print()
        print(f"{group_name}:")
        for index, item in group_results:
            printed.add(index)
            _print_check_result(item)

    remaining = [(index, item) for index, item in enumerate(report.results) if index not in printed]
    if remaining:
        print()
        print("Other:")
        for _index, item in remaining:
            _print_check_result(item)

    total = len(report.results)
    failed = sum(1 for item in report.results if item.status is Status.FAIL)
    warned = sum(1 for item in report.results if item.status is Status.WARN)
    print()
    print(f"Summary: {total} checks, {failed} failed, {warned} warnings")


def _print_check_result(item: CheckResult) -> None:
    print(f"  {item.status.value:<5} {item.name}: {item.message}")
    if item.status is not Status.PASS and item.guidance:
        print(f"        ↳ {item.guidance}")


def _check_oterminus_version() -> CheckResult:
    try:
        version = get_version()
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult(
            name="oterminus version",
            status=Status.WARN,
            message="Package metadata is unavailable and no local fallback could be read.",
            guidance=f"Reinstall OTerminus. Details: {exc}",
        )
    if version == _LOCAL_VERSION:
        return CheckResult(
            name="oterminus version",
            status=Status.WARN,
            message="Package metadata unavailable; running from source checkout fallback.",
            guidance="Install the package with `pipx install oterminus` or use `poetry install` for development.",
        )
    return CheckResult(
        name="oterminus version",
        status=Status.PASS,
        message=version,
        critical=True,
    )


def _check_python_runtime() -> CheckResult:
    if sys.version_info >= (3, 13):
        return CheckResult(
            name="python runtime",
            status=Status.PASS,
            message=f"Python {sys.version.split()[0]} at {sys.executable}.",
            critical=True,
        )
    return CheckResult(
        name="python runtime",
        status=Status.FAIL,
        message=f"Python {sys.version.split()[0]} at {sys.executable}; requires Python 3.13+.",
        guidance="Install Python 3.13 or newer, then reinstall OTerminus in that environment.",
        critical=True,
    )


def _check_environment() -> CheckResult:
    if _inside_virtualenv():
        return CheckResult(
            name="environment",
            status=Status.PASS,
            message="Running inside a virtual environment.",
        )
    return CheckResult(
        name="environment",
        status=Status.WARN,
        message="No active virtual environment detected.",
        guidance="For normal CLI use, prefer `pipx install oterminus` so dependencies stay isolated.",
    )


def _check_install_context() -> CheckResult:
    if _looks_like_pipx():
        return CheckResult(
            name="install context",
            status=Status.PASS,
            message="Looks like a pipx-managed install.",
        )
    if _source_checkout_detected():
        return CheckResult(
            name="install context",
            status=Status.WARN,
            message="Source checkout detected; developer-only checks are enabled.",
            guidance="PyPI/pipx installs skip source-only fixture and dev-tool checks.",
        )
    if _inside_virtualenv():
        return CheckResult(
            name="install context",
            status=Status.PASS,
            message="Virtual environment detected; pipx not detected.",
        )
    return CheckResult(
        name="install context",
        status=Status.WARN,
        message="Install manager unknown; pipx or source checkout not detected.",
        guidance="If this is a user install, `pipx install oterminus` is the recommended path.",
    )


def _inside_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _looks_like_pipx() -> bool:
    if any(os.getenv(name) for name in ("PIPX_HOME", "PIPX_BIN_DIR", "PIPX_DEFAULT_PYTHON")):
        return True
    paths = (Path(sys.prefix), Path(sys.executable))
    return any("pipx" in path.parts for path in paths)


def _source_checkout_detected() -> bool:
    return Path("pyproject.toml").exists()


def _check_package_importable() -> CheckResult:
    try:
        importlib.import_module("oterminus")
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult(
            name="package import",
            status=Status.FAIL,
            message="Could not import `oterminus`.",
            guidance=f"Reinstall the package (for example `pipx reinstall oterminus`). Details: {exc}",
            critical=True,
        )
    return CheckResult(
        name="package import", status=Status.PASS, message="Import succeeded.", critical=True
    )


def _check_platform_support() -> CheckResult:
    platform_id = current_platform_id()
    if platform_id == "darwin":
        return CheckResult(
            name="platform",
            status=Status.PASS,
            message="Detected darwin; macOS command pack support is available.",
        )
    if platform_id == "linux":
        return CheckResult(
            name="platform",
            status=Status.PASS,
            message="Detected linux; use a Unix-like shell with required commands available.",
        )
    if platform_id == "windows":
        return CheckResult(
            name="platform",
            status=Status.WARN,
            message="Detected native Windows; Command Prompt and PowerShell are not first-class supported.",
            guidance="Use WSL for a Unix-like environment, then rerun `oterminus doctor` inside WSL.",
        )
    return CheckResult(
        name="platform",
        status=Status.WARN,
        message=f"Detected {platform_id}; OTerminus targets macOS and Unix-like POSIX shells.",
        guidance="Verify required shell commands and Ollama manually before using natural-language planning.",
    )


def _check_ollama_cli(installed: bool) -> CheckResult:
    if installed:
        return CheckResult(
            name="ollama CLI", status=Status.PASS, message="Found on PATH.", critical=True
        )
    return CheckResult(
        name="ollama CLI",
        status=Status.FAIL,
        message="`ollama` was not found on PATH.",
        guidance="Install Ollama from https://ollama.com/download.",
        critical=True,
    )


def _check_ollama_service(running: bool) -> CheckResult:
    if running:
        return CheckResult(
            name="ollama service",
            status=Status.PASS,
            message="Reachable via `ollama list`.",
            critical=True,
        )
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


def _load_app_config() -> tuple[AppConfig | None, CheckResult]:
    try:
        config = load_config()
    except Exception as exc:
        return (
            None,
            CheckResult(
                name="app config",
                status=Status.FAIL,
                message="Configuration could not be parsed from environment/user settings.",
                guidance=f"Fix malformed OTERMINUS_* values and config JSON. Details: {exc}",
                critical=True,
            ),
        )
    return (
        config,
        CheckResult(
            name="app config",
            status=Status.PASS,
            message="Configuration parsed successfully.",
            critical=True,
        ),
    )


def _check_configured_model(
    config: AppConfig | None, models: list[str], *, ollama_ready: bool
) -> CheckResult:
    if config is None:
        return CheckResult(
            name="configured model",
            status=Status.WARN,
            message="Skipped because app config failed to parse.",
            guidance="Fix the app config check first, then rerun doctor.",
        )
    configured_model = config.model
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
        return CheckResult(
            name="configured model",
            status=Status.PASS,
            message=f"`{configured_model}` is installed.",
            critical=True,
        )

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
        return CheckResult(
            name="config path",
            status=Status.PASS,
            message=f"Readable/writable at {path}.",
            critical=True,
        )

    return CheckResult(
        name="config path",
        status=Status.FAIL,
        message=f"Config path is not writable: {path}.",
        guidance="Grant write permission to the config file or its parent directory.",
        critical=True,
    )


def _check_audit_path(config: AppConfig | None) -> CheckResult:
    if config is None:
        return CheckResult(
            name="audit log path",
            status=Status.WARN,
            message="Skipped because app config failed to parse.",
            guidance="Fix the app config check first, then rerun doctor.",
        )
    if not config.audit_enabled:
        return CheckResult(
            name="audit log path", status=Status.WARN, message="Audit logging is disabled."
        )

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
        return CheckResult(
            name="audit log path",
            status=Status.PASS,
            message=f"Directory writable: {audit_dir}.",
            critical=True,
        )

    return CheckResult(
        name="audit log path",
        status=Status.FAIL,
        message=f"Audit log directory is not writable: {audit_dir}.",
        guidance="Set OTERMINUS_AUDIT_LOG_PATH to a writable location.",
        critical=True,
    )


def _check_history_path(config: AppConfig | None) -> CheckResult:
    if config is None:
        return CheckResult(
            name="history path",
            status=Status.WARN,
            message="Skipped because app config failed to parse.",
            guidance="Fix the app config check first, then rerun doctor.",
        )
    if not config.history_enabled:
        return CheckResult(
            name="history path",
            status=Status.PASS,
            message="Persistent history is disabled.",
        )

    history_path = config.history_path.expanduser()
    history_dir = history_path.parent
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return CheckResult(
            name="history path",
            status=Status.FAIL,
            message=f"Cannot create history directory: {history_dir}.",
            guidance=f"Set OTERMINUS_HISTORY_PATH to a writable location. Details: {exc}",
            critical=True,
        )

    if history_path.exists():
        if history_path.is_dir():
            return CheckResult(
                name="history path",
                status=Status.FAIL,
                message=f"History path points to a directory, not a JSONL file: {history_path}.",
                guidance="Set OTERMINUS_HISTORY_PATH to a writable JSONL file path.",
                critical=True,
            )
        if os.access(history_path, os.W_OK):
            return CheckResult(
                name="history path",
                status=Status.PASS,
                message=f"History file writable: {history_path}.",
                critical=True,
            )
        return CheckResult(
            name="history path",
            status=Status.FAIL,
            message=f"History file is not writable: {history_path}.",
            guidance="Grant write permission to the history file or set OTERMINUS_HISTORY_PATH to a writable location.",
            critical=True,
        )

    if os.access(history_dir, os.W_OK):
        return CheckResult(
            name="history path",
            status=Status.PASS,
            message=f"Directory writable: {history_dir}.",
            critical=True,
        )

    return CheckResult(
        name="history path",
        status=Status.FAIL,
        message=f"History directory is not writable: {history_dir}.",
        guidance="Set OTERMINUS_HISTORY_PATH to a writable location.",
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
    return CheckResult(
        name="prompt_toolkit", status=Status.PASS, message="Autocomplete dependency available."
    )


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
    return CheckResult(
        name="command registry",
        status=Status.PASS,
        message=f"Loaded {count} command specs.",
        critical=True,
    )


def _check_registry_duplicates() -> CheckResult:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for pack in COMMAND_PACKS:
        for spec in pack:
            if spec.name in seen:
                duplicates.add(spec.name)
            seen.add(spec.name)

    if not duplicates:
        return CheckResult(
            name="duplicate command names",
            status=Status.PASS,
            message="No duplicate command names detected.",
            critical=True,
        )
    duplicate_names = ", ".join(sorted(duplicates))
    return CheckResult(
        name="duplicate command names",
        status=Status.FAIL,
        message=f"Duplicate command names detected: {duplicate_names}.",
        guidance="Ensure each command name is unique across COMMAND_PACKS.",
        critical=True,
    )


def _check_eval_fixtures() -> CheckResult:
    if not _source_checkout_detected():
        return CheckResult(
            name="eval fixtures",
            status=Status.WARN,
            message="Developer-only fixture check skipped outside a source checkout.",
        )

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

    return CheckResult(
        name="eval fixtures",
        status=Status.PASS,
        message=f"Loaded {len(cases)} fixture case(s).",
        critical=True,
    )


def _check_dev_tools() -> CheckResult:
    if not _source_checkout_detected():
        return CheckResult(
            name="dev tools",
            status=Status.WARN,
            message="Developer tool check skipped outside a source checkout.",
        )

    poetry_path = shutil.which("poetry")
    if poetry_path:
        return CheckResult(
            name="dev tools", status=Status.PASS, message=f"Poetry available at {poetry_path}."
        )
    return CheckResult(
        name="dev tools",
        status=Status.WARN,
        message="Poetry not found on PATH.",
        guidance="Install Poetry for local development workflows.",
    )

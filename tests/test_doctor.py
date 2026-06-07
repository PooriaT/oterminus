from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import Mock

import pytest

from oterminus.config import AppConfig, load_config as real_load_config
from oterminus.doctor import CheckResult, DoctorReport, Status, print_report, run_doctor
from oterminus.terminal_style import TerminalStyle
from oterminus.version import get_version as real_get_version


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _base_monkeypatches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("oterminus.doctor.sys.version_info", (3, 13, 2))
    monkeypatch.setattr("oterminus.doctor.sys.version", "3.13.2")
    monkeypatch.setattr("oterminus.doctor.sys.executable", str(tmp_path / "bin" / "python"))
    monkeypatch.setattr("oterminus.doctor.sys.prefix", str(tmp_path / ".venv"))
    monkeypatch.setattr("oterminus.doctor.sys.base_prefix", str(tmp_path / "python"))
    monkeypatch.setattr("oterminus.doctor.get_version", lambda: "1.2.3")
    monkeypatch.delenv("PIPX_HOME", raising=False)
    monkeypatch.delenv("PIPX_BIN_DIR", raising=False)
    monkeypatch.delenv("PIPX_DEFAULT_PYTHON", raising=False)
    monkeypatch.setattr("oterminus.doctor.check_ollama_installed", lambda: True)
    monkeypatch.setattr("oterminus.doctor.check_ollama_running", lambda: True)
    monkeypatch.setattr("oterminus.doctor.get_available_models", lambda: ["gemma3:latest"])
    monkeypatch.setattr("oterminus.doctor.get_user_config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr("oterminus.doctor.load_eval_cases", lambda _: [object()])
    config = AppConfig(
        model="gemma3:latest",
        audit_enabled=True,
        audit_log_path=tmp_path / "audit" / "audit.jsonl",
        history_enabled=False,
        history_path=tmp_path / "history" / "history.jsonl",
    )
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)


def _status_by_name(report, name: str) -> CheckResult:
    return next(item for item in report.results if item.name == name)


def test_doctor_passes_with_healthy_environment(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)

    report = run_doctor()

    assert report.exit_code == 0
    assert _status_by_name(report, "oterminus version").status is Status.PASS
    assert _status_by_name(report, "python runtime").status is Status.PASS
    assert str(tmp_path / "bin" / "python") in _status_by_name(report, "python runtime").message
    assert _status_by_name(report, "environment").status is Status.PASS
    assert _status_by_name(report, "ollama CLI").status is Status.PASS
    assert _status_by_name(report, "ollama service").status is Status.PASS
    assert _status_by_name(report, "configured model").status is Status.PASS
    assert _status_by_name(report, "audit log path").status is Status.PASS
    assert _status_by_name(report, "history path").status is Status.PASS
    assert _status_by_name(report, "command registry").status is Status.PASS


def test_doctor_reports_installed_version_from_metadata(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.version.metadata.version", lambda _name: "4.5.6")
    monkeypatch.setattr("oterminus.doctor.get_version", real_get_version)

    report = run_doctor()

    version = _status_by_name(report, "oterminus version")
    assert version.status is Status.PASS
    assert version.message == "4.5.6"


def test_doctor_warns_when_version_metadata_uses_local_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    from importlib import metadata

    _base_monkeypatches(monkeypatch, tmp_path)

    def missing(_name: str) -> str:
        raise metadata.PackageNotFoundError(_name)

    monkeypatch.setattr("oterminus.version.metadata.version", missing)
    monkeypatch.setattr("oterminus.doctor.get_version", real_get_version)

    report = run_doctor()

    version = _status_by_name(report, "oterminus version")
    assert version.status is Status.WARN
    assert "Package metadata unavailable" in version.message


def test_doctor_unsupported_python_is_critical(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.doctor.sys.version_info", (3, 12, 8))
    monkeypatch.setattr("oterminus.doctor.sys.version", "3.12.8")

    report = run_doctor()

    runtime = _status_by_name(report, "python runtime")
    assert runtime.status is Status.FAIL
    assert "requires Python 3.13+" in runtime.message
    assert report.exit_code == 2


def test_doctor_detects_pipx_from_environment(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setenv("PIPX_HOME", str(tmp_path / "pipx"))

    report = run_doctor()

    install = _status_by_name(report, "install context")
    assert install.status is Status.PASS
    assert "pipx-managed" in install.message


def test_doctor_detects_pipx_from_prefix_path(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "oterminus.doctor.sys.prefix", str(tmp_path / "pipx" / "venvs" / "oterminus")
    )

    report = run_doctor()

    assert "pipx-managed" in _status_by_name(report, "install context").message


def test_doctor_detects_source_checkout(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.poetry]\nname = 'oterminus'\n", encoding="utf-8"
    )

    report = run_doctor()

    install = _status_by_name(report, "install context")
    assert install.status is Status.WARN
    assert "Source checkout detected" in install.message


def test_doctor_handles_unknown_install_context(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("oterminus.doctor.sys.prefix", str(tmp_path / "python"))
    monkeypatch.setattr("oterminus.doctor.sys.base_prefix", str(tmp_path / "python"))

    report = run_doctor()

    environment = _status_by_name(report, "environment")
    install = _status_by_name(report, "install context")
    assert environment.status is Status.WARN
    assert install.status is Status.WARN
    assert "unknown" in install.message


def test_doctor_reports_linux_platform(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.doctor.current_platform_id", lambda: "linux")

    report = run_doctor()

    platform = _status_by_name(report, "platform")
    assert platform.status is Status.PASS
    assert "Detected linux" in platform.message


def test_doctor_warns_on_native_windows(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.doctor.current_platform_id", lambda: "windows")

    report = run_doctor()

    platform = _status_by_name(report, "platform")
    assert platform.status is Status.WARN
    assert "native Windows" in platform.message
    assert platform.guidance is not None
    assert "WSL" in platform.guidance


def test_doctor_fails_when_ollama_cli_missing(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.doctor.check_ollama_installed", lambda: False)

    report = run_doctor()

    assert _status_by_name(report, "ollama CLI").status is Status.FAIL
    assert _status_by_name(report, "ollama service").status is Status.WARN
    assert "CLI is missing" in _status_by_name(report, "local ollama models").message
    assert report.exit_code == 2


def test_doctor_fails_when_ollama_service_down(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.doctor.check_ollama_running", lambda: False)

    report = run_doctor()

    assert _status_by_name(report, "ollama CLI").status is Status.PASS
    assert _status_by_name(report, "ollama service").status is Status.FAIL
    assert _status_by_name(report, "local ollama models").status is Status.WARN
    assert "service is unreachable" in _status_by_name(report, "local ollama models").message
    assert report.exit_code == 2


def test_doctor_fails_when_service_up_but_no_models(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.doctor.get_available_models", lambda: [])

    report = run_doctor()

    models = _status_by_name(report, "local ollama models")
    assert models.status is Status.FAIL
    assert "No local Ollama models" in models.message
    assert models.guidance is not None
    assert "ollama pull" in models.guidance
    assert report.exit_code == 2


def test_doctor_reports_config_parse_failure_instead_of_crashing(
    monkeypatch, tmp_path: Path
) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "oterminus.doctor.load_config", Mock(side_effect=ValueError("invalid timeout"))
    )

    report = run_doctor()

    assert _status_by_name(report, "app config").status is Status.FAIL
    assert _status_by_name(report, "configured model").status is Status.WARN
    assert _status_by_name(report, "audit log path").status is Status.WARN
    assert _status_by_name(report, "history path").status is Status.WARN
    assert report.exit_code == 2


def test_doctor_reports_invalid_user_config_without_crashing(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    config_path = tmp_path / "config.json"
    config_path.write_text('{"audit_log_path": 123}', encoding="utf-8")
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.setattr("oterminus.doctor.load_config", real_load_config)

    report = run_doctor()

    app_config = _status_by_name(report, "app config")
    assert app_config.status is Status.FAIL
    assert "audit_log_path" in (app_config.guidance or "")
    assert report.exit_code == 2


def test_doctor_warns_when_prompt_toolkit_missing(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)

    real_import_module = __import__("importlib").import_module

    def fake_import_module(name: str):
        if name == "prompt_toolkit":
            raise ImportError("missing")
        return real_import_module(name)

    monkeypatch.setattr("oterminus.doctor.importlib.import_module", fake_import_module)

    report = run_doctor()

    assert _status_by_name(report, "prompt_toolkit").status is Status.WARN


def test_doctor_fails_when_configured_model_missing(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    config = AppConfig(
        model="llama3.2:latest",
        audit_enabled=True,
        audit_log_path=tmp_path / "audit" / "audit.jsonl",
        history_enabled=False,
        history_path=tmp_path / "history" / "history.jsonl",
    )
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)

    report = run_doctor()

    assert _status_by_name(report, "configured model").status is Status.FAIL
    assert report.exit_code == 2


def test_doctor_warns_when_no_model_configured(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    config = AppConfig(
        model=None,
        audit_enabled=True,
        audit_log_path=tmp_path / "audit" / "audit.jsonl",
        history_enabled=False,
        history_path=tmp_path / "history" / "history.jsonl",
    )
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)

    report = run_doctor()

    configured = _status_by_name(report, "configured model")
    assert configured.status is Status.WARN
    assert "No model configured" in configured.message


def test_doctor_checks_audit_path(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "oterminus.doctor.os.access",
        lambda path, mode: False if Path(path) == tmp_path / "audit" else True,
    )

    report = run_doctor()

    assert _status_by_name(report, "audit log path").status is Status.FAIL


def test_doctor_reports_disabled_audit_path(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    config = AppConfig(
        model="gemma3:latest",
        audit_enabled=False,
        audit_log_path=tmp_path / "audit" / "audit.jsonl",
        history_enabled=False,
        history_path=tmp_path / "history" / "history.jsonl",
    )
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)

    report = run_doctor()

    audit = _status_by_name(report, "audit log path")
    assert audit.status is Status.WARN
    assert "disabled" in audit.message


def test_doctor_checks_enabled_history_path(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    config = AppConfig(
        model="gemma3:latest",
        audit_enabled=True,
        audit_log_path=tmp_path / "audit" / "audit.jsonl",
        history_enabled=True,
        history_path=tmp_path / "history" / "history.jsonl",
    )
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)

    report = run_doctor()

    history = _status_by_name(report, "history path")
    assert history.status is Status.PASS
    assert str(tmp_path / "history") in history.message


def test_doctor_checks_unwritable_history_path(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    config = AppConfig(
        model="gemma3:latest",
        audit_enabled=True,
        audit_log_path=tmp_path / "audit" / "audit.jsonl",
        history_enabled=True,
        history_path=tmp_path / "history" / "history.jsonl",
    )
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)
    monkeypatch.setattr(
        "oterminus.doctor.os.access",
        lambda path, mode: False if Path(path) == tmp_path / "history" else True,
    )

    report = run_doctor()

    assert _status_by_name(report, "history path").status is Status.FAIL


def test_doctor_checks_existing_history_file_writability(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    history_path = tmp_path / "history" / "history.jsonl"
    history_path.parent.mkdir()
    history_path.write_text("", encoding="utf-8")
    config = AppConfig(
        model="gemma3:latest",
        audit_enabled=True,
        audit_log_path=tmp_path / "audit" / "audit.jsonl",
        history_enabled=True,
        history_path=history_path,
    )
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)
    monkeypatch.setattr(
        "oterminus.doctor.os.access",
        lambda path, mode: False if Path(path) == history_path else True,
    )

    report = run_doctor()

    history = _status_by_name(report, "history path")
    assert history.status is Status.FAIL
    assert "file is not writable" in history.message


def test_doctor_rejects_history_path_that_is_existing_directory(
    monkeypatch, tmp_path: Path
) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    history_path = tmp_path / "history-dir"
    history_path.mkdir()
    config = AppConfig(
        model="gemma3:latest",
        audit_enabled=True,
        audit_log_path=tmp_path / "audit" / "audit.jsonl",
        history_enabled=True,
        history_path=history_path,
    )
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)

    report = run_doctor()

    history = _status_by_name(report, "history path")
    assert history.status is Status.FAIL
    assert "points to a directory" in history.message


def test_doctor_checks_registry_integrity(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)

    class Spec:
        def __init__(self, name: str) -> None:
            self.name = name

    monkeypatch.setattr(
        "oterminus.doctor.COMMAND_PACKS",
        (
            (Spec("ls"),),
            (Spec("ls"),),
        ),
    )

    report = run_doctor()

    assert _status_by_name(report, "duplicate command names").status is Status.FAIL


def test_doctor_command_returns_proper_exit_code(monkeypatch, tmp_path: Path) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr(
        "oterminus.cli.run_doctor",
        lambda: type("R", (), {"results": (), "exit_code": 2})(),
    )
    monkeypatch.setattr("oterminus.cli.print_report", lambda report: None)

    code = main(["doctor"])

    assert code == 2


def test_doctor_skips_eval_fixture_check_outside_repo(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)

    report = run_doctor()

    assert _status_by_name(report, "eval fixtures").status is Status.WARN


def test_print_report_groups_checks_and_guidance(capsys) -> None:
    report = DoctorReport(
        results=(
            CheckResult("oterminus version", Status.PASS, "1.2.3"),
            CheckResult("python runtime", Status.PASS, "Python 3.13.2 at /tmp/python"),
            CheckResult(
                "ollama CLI",
                Status.FAIL,
                "`ollama` was not found on PATH.",
                guidance="Install Ollama.",
                critical=True,
            ),
            CheckResult("configured model", Status.WARN, "No model configured."),
        )
    )

    print_report(report)

    output = capsys.readouterr().out
    assert "Package/runtime:" in output
    assert "Ollama:" in output
    assert "Model/config:" in output
    assert "FAIL  ollama CLI" in output
    assert "Install Ollama." in output
    assert "Summary: 4 checks, 1 failed, 1 warnings" in output


def test_print_report_styles_statuses_and_summary_when_enabled(capsys) -> None:
    report = DoctorReport(
        results=(
            CheckResult("pass check", Status.PASS, "ok"),
            CheckResult("warn check", Status.WARN, "careful", guidance="Review config."),
            CheckResult("fail check", Status.FAIL, "broken", guidance="Fix it.", critical=True),
        )
    )

    print_report(report, style=TerminalStyle(color_enabled=True))

    output = capsys.readouterr().out
    assert ANSI_RE.search(output)
    assert "PASS" in output
    assert "WARN" in output
    assert "FAIL" in output
    assert "Review config." in output
    assert "Summary: 3 checks, 1 failed, 1 warnings" in output


def test_print_report_disabled_style_is_plain(capsys) -> None:
    report = DoctorReport(results=(CheckResult("pass check", Status.PASS, "ok"),))

    print_report(report, style=TerminalStyle(color_enabled=False))

    output = capsys.readouterr().out
    assert not ANSI_RE.search(output)
    assert "PASS  pass check" in output
    assert "Summary: 1 checks, 0 failed, 0 warnings" in output


@pytest.mark.parametrize(
    ("critical", "status", "expected"),
    [
        (True, Status.FAIL, 2),
        (False, Status.FAIL, 0),
        (True, Status.WARN, 0),
    ],
)
def test_doctor_exit_code_depends_only_on_critical_failures(
    critical: bool, status: Status, expected: int
) -> None:
    report = DoctorReport(results=(CheckResult("check", status, "message", critical=critical),))

    assert report.exit_code == expected

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from oterminus.doctor import CheckResult, Status, run_doctor


def _base_monkeypatches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("oterminus.doctor.sys.version_info", (3, 13, 2))
    monkeypatch.setattr("oterminus.doctor.sys.version", "3.13.2")
    monkeypatch.setattr("oterminus.doctor.check_ollama_installed", lambda: True)
    monkeypatch.setattr("oterminus.doctor.check_ollama_running", lambda: True)
    monkeypatch.setattr("oterminus.doctor.get_available_models", lambda: ["gemma3:latest"])
    monkeypatch.setattr("oterminus.doctor.get_user_config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr("oterminus.doctor.load_eval_cases", lambda _: [object()])
    config = Mock()
    config.model = "gemma3:latest"
    config.audit_enabled = True
    config.audit_log_path = tmp_path / "audit" / "audit.jsonl"
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)


def _status_by_name(report, name: str) -> CheckResult:
    return next(item for item in report.results if item.name == name)


def test_doctor_passes_with_healthy_environment(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)

    report = run_doctor()

    assert report.exit_code == 0
    assert _status_by_name(report, "ollama CLI").status is Status.PASS
    assert _status_by_name(report, "ollama service").status is Status.PASS
    assert _status_by_name(report, "configured model").status is Status.PASS
    assert _status_by_name(report, "audit log path").status is Status.PASS
    assert _status_by_name(report, "command registry").status is Status.PASS


def test_doctor_fails_when_ollama_cli_missing(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.doctor.check_ollama_installed", lambda: False)

    report = run_doctor()

    assert _status_by_name(report, "ollama CLI").status is Status.FAIL
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
    config = Mock()
    config.model = "llama3.2:latest"
    config.audit_enabled = True
    config.audit_log_path = tmp_path / "audit" / "audit.jsonl"
    monkeypatch.setattr("oterminus.doctor.load_config", lambda: config)

    report = run_doctor()

    assert _status_by_name(report, "configured model").status is Status.FAIL
    assert report.exit_code == 2


def test_doctor_checks_audit_path(monkeypatch, tmp_path: Path) -> None:
    _base_monkeypatches(monkeypatch, tmp_path)
    monkeypatch.setattr("oterminus.doctor.os.access", lambda path, mode: False if Path(path) == tmp_path / "audit" else True)

    report = run_doctor()

    assert _status_by_name(report, "audit log path").status is Status.FAIL


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

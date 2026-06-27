from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import ANY, Mock

import pytest

from oterminus.config import AppConfig
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel
from oterminus.policies import PolicyConfig
from oterminus.terminal_style import ColorMode
from oterminus.validator import ProposalOrigin, Validator


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _config(tmp_path: Path, *, audit_enabled: bool = True) -> AppConfig:
    return AppConfig(
        timeout_seconds=30,
        policy=PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False),
        audit_log_path=tmp_path / "audit.jsonl",
        audit_enabled=audit_enabled,
        audit_redact=False,
    )


def _planned_ls_proposal() -> Proposal:
    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="ls",
        arguments={
            "path": ".",
            "long": False,
            "human_readable": False,
            "all": False,
            "recursive": False,
        },
        summary="show files in this directory",
        explanation="List files in the current directory.",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )


def _planned_project_health_proposal() -> Proposal:
    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="project_health",
        arguments={"operation": "run_tests"},
        summary="run project tests",
        explanation="Run the configured project test suite.",
        risk_level=RiskLevel.WRITE,
        needs_confirmation=True,
        notes=[],
    )


def _planned_file_identify_proposal() -> Proposal:
    return Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="file",
        arguments={"paths": ["README.md"]},
        summary="identify README.md",
        explanation="Inspect the file type for README.md.",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )


def _install_main_dependencies(monkeypatch, config: AppConfig) -> tuple[Mock, Mock]:
    validator = Mock(wraps=Validator(config.policy))
    executor = Mock()
    executor.timeout_seconds = config.timeout_seconds
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = ""

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    return validator, executor


def _read_audit_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8").strip())


def test_doctor_command_is_diagnostics_only(monkeypatch, tmp_path: Path) -> None:
    from oterminus.cli import main

    report = type("Report", (), {"results": (), "exit_code": 2})()
    run_doctor = Mock(return_value=report)
    print_report = Mock()
    config = _config(tmp_path)

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.run_doctor", run_doctor)
    monkeypatch.setattr("oterminus.cli.print_report", print_report)
    monkeypatch.setattr("oterminus.cli.load_config", Mock(return_value=config))
    monkeypatch.setattr("oterminus.cli.repl", Mock(side_effect=AssertionError("no REPL")))
    monkeypatch.setattr("oterminus.cli.Executor", Mock(side_effect=AssertionError("no executor")))
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr(
        "oterminus.cli.OllamaPlannerClient",
        Mock(side_effect=AssertionError("no planner client")),
    )

    code = main(["doctor"])

    assert code == 2
    run_doctor.assert_called_once_with()
    print_report.assert_called_once_with(report, style=ANY)


def test_doctor_honors_env_color_mode_for_redirected_output(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main
    from oterminus.doctor import CheckResult, DoctorReport, Status

    report = DoctorReport(results=(CheckResult("check", Status.PASS, "ok"),))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OTERMINUS_COLOR", "always")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.run_doctor", Mock(return_value=report))

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert ANSI_RE.search(output)
    assert "PASS" in output


def test_doctor_honors_persisted_color_mode_always_for_redirected_output(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main
    from oterminus.doctor import CheckResult, DoctorReport, Status

    config_path = tmp_path / "config.json"
    config_path.write_text('{"color_mode": "always"}', encoding="utf-8")
    report = DoctorReport(results=(CheckResult("check", Status.PASS, "ok"),))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.run_doctor", Mock(return_value=report))

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert ANSI_RE.search(output)
    assert "PASS" in output


def test_doctor_honors_persisted_color_mode_never(monkeypatch, tmp_path: Path, capsys) -> None:
    from oterminus.cli import main
    from oterminus.doctor import CheckResult, DoctorReport, Status

    config_path = tmp_path / "config.json"
    config_path.write_text('{"color_mode": "never"}', encoding="utf-8")
    report = DoctorReport(results=(CheckResult("check", Status.PASS, "ok"),))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OTERMINUS_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("OTERMINUS_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.run_doctor", Mock(return_value=report))

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert not ANSI_RE.search(output)
    assert "PASS  check" in output


@pytest.mark.parametrize(
    "argv",
    (
        ["--dry-run", "--explain", "ls"],
        ["doctor", "--dry-run"],
        ["doctor", "--explain"],
        ["--dry-run", "doctor"],
        ["--explain", "doctor"],
    ),
)
def test_parser_rejects_mutually_exclusive_or_invalid_modes(argv, capsys) -> None:
    from oterminus.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2
    error = capsys.readouterr().err
    assert "error:" in error


def test_direct_dry_run_validates_previews_audits_and_skips_execution(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    validator, executor = _install_main_dependencies(monkeypatch, config)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct dry-run should not require Ollama")),
    )
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

    code = main(["--dry-run", "ls"])

    assert code == 0
    output = capsys.readouterr().out
    assert "--- command preview ---" in output
    assert "Dry-run mode: execution skipped" in output
    validator.validate.assert_called_once()
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["user_input"] == "ls"
    assert payload["direct_command_detected"] is True
    assert payload["planner_invoked"] is False
    assert payload["planner_skipped"] is True
    assert payload["planner_skip_reason"] == "direct_command"
    assert payload["validation_accepted"] is True
    assert payload["confirmation_result"] == "skipped_dry_run"
    assert payload["execution_exit_code"] is None


def test_direct_explain_validates_renders_explanation_audits_and_skips_execution(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    validator, executor = _install_main_dependencies(monkeypatch, config)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct explain should not require Ollama")),
    )
    monkeypatch.setattr("oterminus.cli.Planner", Mock(side_effect=AssertionError("no planner")))
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

    code = main(["--explain", "ls"])

    assert code == 0
    output = capsys.readouterr().out
    assert "--- command preview ---" in output
    assert "--- oterminus explanation ---" in output
    assert "Execution     : Blocked by explain mode" in output
    validator.validate.assert_called_once()
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["user_input"] == "ls"
    assert payload["direct_command_detected"] is True
    assert payload["planner_invoked"] is False
    assert payload["planner_skipped"] is True
    assert payload["planner_skip_reason"] == "direct_command"
    assert payload["validation_accepted"] is True
    assert payload["confirmation_result"] == "skipped_explain"
    assert payload["execution_exit_code"] is None


@pytest.mark.parametrize(
    ("flag", "expected_status"),
    (("--dry-run", "skipped_dry_run"), ("--explain", "skipped_explain")),
)
def test_natural_language_inspection_modes_use_planner_without_executor(
    monkeypatch, tmp_path: Path, capsys, flag: str, expected_status: str
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    validator, executor = _install_main_dependencies(monkeypatch, config)
    planner = Mock()
    planner.plan.return_value = _planned_ls_proposal()

    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", Mock(return_value="gemma3:latest"))
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", Mock(return_value=Mock()))
    monkeypatch.setattr("oterminus.cli.Planner", lambda client: planner)
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

    code = main([flag, "show", "files", "in", "this", "directory"])

    assert code == 0
    output = capsys.readouterr().out
    assert "--- oterminus proposal ---" in output
    if flag == "--dry-run":
        assert "Dry-run mode: execution skipped" in output
    else:
        assert "--- oterminus explanation ---" in output
    planner.plan.assert_called_once_with("show files in this directory")
    validator.validate.assert_called_once()
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["user_input"] == "show files in this directory"
    assert payload["direct_command_detected"] is False
    assert payload["routed_category"] == "filesystem_inspect"
    assert payload["confirmation_result"] == expected_status
    assert payload["execution_exit_code"] is None


def test_one_shot_execute_mode_decline_stops_before_executor(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    validator, executor = _install_main_dependencies(monkeypatch, config)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(return_value="n"))

    code = main(["ls"])

    assert code == 0
    assert "Cancelled." in capsys.readouterr().out
    validator.validate.assert_called_once()
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["confirmation_result"] == "cancelled"
    assert payload["execution_exit_code"] is None


def test_direct_ls_passthrough_skips_planner_and_uses_direct_validation_origin(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    validator, executor = _install_main_dependencies(monkeypatch, config)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("dry-run")))

    code = main(["--dry-run", "--", "ls", "-ltrh"])

    assert code == 0
    output = capsys.readouterr().out
    assert "ls -ltrh" in output
    validator.validate.assert_called_once()
    assert validator.validate.call_args.kwargs["origin"] == ProposalOrigin.DIRECT_COMMAND
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["direct_command_detected"] is True
    assert payload["planner_skip_reason"] == "direct_command"
    assert payload["proposal_origin"] == "direct_command"
    assert payload["rendered_command"] == "ls -ltrh"
    assert payload["argv"] == ["ls", "-ltrh"]


def test_natural_language_project_health_uses_planner_and_requires_confirmation(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    validator, executor = _install_main_dependencies(monkeypatch, config)
    planner = Mock()
    planner.plan.return_value = _planned_project_health_proposal()
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", Mock(return_value="test-model"))
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", Mock())
    monkeypatch.setattr("oterminus.cli.Planner", Mock(return_value=planner))
    monkeypatch.setattr("builtins.input", Mock(return_value="n"))

    code = main(["run", "tests"])

    assert code == 0
    output = capsys.readouterr().out
    assert "poetry run pytest" in output
    assert "Cancelled." in output
    planner.plan.assert_called_once_with("run tests")
    validator.validate.assert_called_once()
    assert validator.validate.call_args.kwargs["origin"] == ProposalOrigin.LLM_PLANNER
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["direct_command_detected"] is False
    assert payload["planner_invoked"] is True
    assert payload["planner_skipped"] is False
    assert payload["planner_skip_reason"] is None
    assert payload["proposal_origin"] == "llm_planner"
    assert payload["routed_category"] == "project_health"
    assert payload["command_family"] == "project_health"
    assert payload["confirmation_result"] == "cancelled"
    assert payload["execution_exit_code"] is None


def test_deterministic_shortcuts_off_routes_natural_language_to_planner(
    monkeypatch, tmp_path: Path
) -> None:
    from oterminus.cli import main

    config = AppConfig(**(_config(tmp_path).__dict__ | {"deterministic_shortcuts": "off"}))
    validator, executor = _install_main_dependencies(monkeypatch, config)
    planner = Mock()
    planner.plan.return_value = _planned_ls_proposal()
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", Mock(return_value="test-model"))
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", Mock())
    monkeypatch.setattr("oterminus.cli.Planner", Mock(return_value=planner))

    code = main(["--dry-run", "show", "current", "directory"])

    assert code == 0
    planner.plan.assert_called_once_with("show current directory")
    validator.validate.assert_called_once()
    assert validator.validate.call_args.kwargs["origin"] == ProposalOrigin.LLM_PLANNER
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["planner_invoked"] is True
    assert payload["planner_skipped"] is False
    assert payload["proposal_origin"] == "llm_planner"


def test_one_shot_execute_mode_confirmation_runs_executor(monkeypatch, tmp_path: Path) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(return_value="y"))

    code = main(["ls"])

    assert code == 0
    executor.run.assert_called_once_with(["ls", "."], display_command="ls .")
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["confirmation_result"] == "confirmed"
    assert payload["execution_exit_code"] == 0


def test_auto_execute_safe_direct_command_skips_confirmation_and_runs_executor(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = AppConfig(**(_config(tmp_path).__dict__ | {"auto_execute_safe": True}))
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

    code = main(["pwd"])

    assert code == 0
    output = capsys.readouterr().out
    assert "--- command preview ---" in output
    assert "Safe auto-execute is enabled. Confirmation skipped" in output
    executor.run.assert_called_once_with(["pwd"], display_command="pwd")
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["confirmation_result"] == "skipped_auto_execute_safe"
    assert payload["auto_execute_safe_enabled"] is True
    assert payload["auto_execute_safe_eligible"] is True
    assert payload["auto_execute_safe_reason"] == "eligible"
    assert payload["proposal_origin"] == "direct_command"


def test_auto_execute_safe_deterministic_shortcut_command_skips_confirmation(
    monkeypatch, tmp_path: Path
) -> None:
    from oterminus.cli import main

    config = AppConfig(**(_config(tmp_path).__dict__ | {"auto_execute_safe": True}))
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("deterministic shortcut should not need Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

    code = main(["show", "current", "directory"])

    assert code == 0
    executor.run.assert_called_once_with(["pwd"], display_command="pwd")
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["confirmation_result"] == "skipped_auto_execute_safe"
    assert payload["proposal_origin"] == "deterministic_shortcut"


def test_auto_execute_safe_removed_shortcut_recipe_uses_planner_and_requires_confirmation(
    monkeypatch, tmp_path: Path
) -> None:
    from oterminus.cli import main

    config = AppConfig(**(_config(tmp_path).__dict__ | {"auto_execute_safe": True}))
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    planner = Mock()
    planner.plan.return_value = _planned_file_identify_proposal()
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", Mock(return_value="test-model"))
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", Mock())
    monkeypatch.setattr("oterminus.cli.Planner", Mock(return_value=planner))
    monkeypatch.setattr("builtins.input", Mock(return_value="n"))

    code = main(["identify", "README.md"])

    assert code == 0
    planner.plan.assert_called_once_with("identify README.md")
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["confirmation_result"] == "cancelled"
    assert payload["proposal_origin"] == "llm_planner"
    assert payload["auto_execute_safe_eligible"] is False


def test_auto_execute_safe_network_command_still_calls_confirmation(
    monkeypatch, tmp_path: Path
) -> None:
    from oterminus.cli import main

    config = AppConfig(**(_config(tmp_path).__dict__ | {"auto_execute_safe": True}))
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    confirmation = Mock(return_value="n")
    monkeypatch.setattr("builtins.input", confirmation)

    code = main(["--", "ping", "-c", "4", "example.com"])

    assert code == 0
    confirmation.assert_called_once()
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["confirmation_result"] == "cancelled"
    assert payload["auto_execute_safe_eligible"] is False


def test_auto_execute_safe_write_command_still_calls_confirmation(
    monkeypatch, tmp_path: Path
) -> None:
    from oterminus.cli import main

    config = AppConfig(**(_config(tmp_path).__dict__ | {"auto_execute_safe": True}))
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    confirmation = Mock(return_value="n")
    monkeypatch.setattr("builtins.input", confirmation)

    code = main(["mkdir", "logs"])

    assert code == 0
    confirmation.assert_called_once()
    executor.run.assert_not_called()
    payload = _read_audit_payload(config.audit_log_path)
    assert payload["confirmation_result"] == "cancelled"
    assert payload["auto_execute_safe_eligible"] is False


def test_auto_execute_safe_dry_run_and_explain_do_not_execute_or_prompt(
    monkeypatch, tmp_path: Path
) -> None:
    from oterminus.cli import main

    for flag in ("--dry-run", "--explain"):
        config = AppConfig(
            **(_config(tmp_path / flag.replace("--", "")).__dict__ | {"auto_execute_safe": True})
        )
        _validator, executor = _install_main_dependencies(monkeypatch, config)
        monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

        code = main([flag, "pwd"])

        assert code == 0
        executor.run.assert_not_called()
        payload = _read_audit_payload(config.audit_log_path)
        assert payload["confirmation_result"] in {"skipped_dry_run", "skipped_explain"}
        assert payload["auto_execute_safe_eligible"] is None


def test_execute_mode_prints_truncation_notice_when_output_truncated(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    config = AppConfig(**(config.__dict__ | {"max_output_chars": 4}))
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    executor.max_output_chars = 4
    executor.run.return_value.stdout = "abcd"
    executor.run.return_value.stderr = ""
    executor.run.return_value.stdout_truncated = True
    executor.run.return_value.stderr_truncated = False
    executor.run.return_value.stdout_original_chars = 10
    executor.run.return_value.stderr_original_chars = 0
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(return_value="y"))

    code = main(["ls"])
    assert code == 0
    output = capsys.readouterr().out
    assert "[oterminus] stdout truncated to 4 characters." in output


def test_colored_lifecycle_output_does_not_store_ansi_in_audit(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = AppConfig(**(_config(tmp_path).__dict__ | {"color_mode": ColorMode.ALWAYS}))
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct dry-run should not require Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("no confirmation")))

    code = main(["--dry-run", "ls"])

    assert code == 0
    output = capsys.readouterr().out
    assert ANSI_RE.search(output)
    executor.run.assert_not_called()
    raw_audit = config.audit_log_path.read_text(encoding="utf-8")
    assert not ANSI_RE.search(raw_audit)
    payload = json.loads(raw_audit)
    assert payload["rendered_command"] == "ls ."


def test_colored_execution_keeps_subprocess_stdout_pass_through(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = AppConfig(**(_config(tmp_path).__dict__ | {"color_mode": ColorMode.ALWAYS}))
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    executor.run.return_value.stdout = "plain subprocess output\n"
    executor.run.return_value.stderr = ""
    executor.run.return_value.stdout_truncated = False
    executor.run.return_value.stderr_truncated = False
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(return_value="y"))

    code = main(["ls"])

    assert code == 0
    output = capsys.readouterr().out
    assert ANSI_RE.search(output)
    assert "plain subprocess output\n" in output
    assert "plain subprocess output\x1b" not in output


def test_machine_oriented_commands_stay_plain_with_color_forced(monkeypatch, capsys) -> None:
    from oterminus.cli import main

    monkeypatch.setenv("OTERMINUS_COLOR", "always")
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)

    assert main(["--version"]) == 0
    version_output = capsys.readouterr().out
    assert not ANSI_RE.search(version_output)

    assert main(["version"]) == 0
    version_command_output = capsys.readouterr().out
    assert not ANSI_RE.search(version_command_output)

    assert main(["completion", "bash"]) == 0
    completion_output = capsys.readouterr().out
    assert not ANSI_RE.search(completion_output)
    assert "complete -F _oterminus_completion oterminus" in completion_output


def test_repl_documented_built_ins_are_handled_without_ollama_or_execution(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    inputs = iter(["help", "dry-run ls", "explain ls", "audit status", "history", "exit"])

    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct REPL built-ins should not require Ollama")),
    )
    monkeypatch.setattr("builtins.input", Mock(side_effect=lambda _prompt: next(inputs)))

    code = main(["--verbose"])

    assert code == 0
    output = capsys.readouterr().out
    assert "Built-ins: help" in output
    assert "Dry-run mode: execution skipped" in output
    assert "--- oterminus explanation ---" in output
    assert "audit enabled: yes" in output
    assert "skipped_dry_run" in output
    assert "skipped_explain" in output
    executor.run.assert_not_called()


def test_one_shot_audit_tail_and_clear_do_not_call_planner_or_executor(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    from oterminus.cli import main

    config = _config(tmp_path)
    _validator, executor = _install_main_dependencies(monkeypatch, config)
    config.audit_log_path.write_text(
        '{"timestamp":"t","user_input":"x [REDACTED]","confirmation_result":"confirmed","execution_exit_code":0}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("audit commands should not require Ollama")),
    )

    code = main(["audit", "tail"])
    assert code == 0
    assert "x [REDACTED]" in capsys.readouterr().out
    executor.run.assert_not_called()

    monkeypatch.setattr("builtins.input", Mock(return_value="CLEAR AUDIT"))
    code = main(["audit", "clear"])
    assert code == 0
    assert "Cleared audit log" in capsys.readouterr().out
    assert config.audit_log_path.read_text(encoding="utf-8") == ""
    executor.run.assert_not_called()

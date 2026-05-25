import json
from pathlib import Path
from unittest.mock import Mock

import subprocess

import pytest

from oterminus.cli import (
    RunMode,
    SessionHistory,
    ask_confirmation,
    handle_repl_discovery_command,
    handle_repl_history_command,
    parse_args,
    render_audit_status,
    render_audit_tail,
    clear_audit_log,
)
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel, ValidationResult
from oterminus.ollama_client import parse_ollama_list_output
from oterminus.policies import ConfirmationLevel


def test_parse_args_one_shot() -> None:
    args = parse_args(["show", "files"])
    assert args.request == ["show", "files"]
    assert args.cli_mode == "request"


def test_parse_args_doctor_mode() -> None:
    args = parse_args(["doctor"])
    assert args.request == ["doctor"]
    assert args.cli_mode == "doctor"
    assert args.dry_run is False
    assert args.explain is False


def test_parse_args_rejects_doctor_with_dry_run() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["doctor", "--dry-run"])

    assert exc_info.value.code == 2


def test_parse_args_rejects_dry_run_doctor_request() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--dry-run", "doctor"])

    assert exc_info.value.code == 2


def test_parse_args_rejects_explain_doctor_request() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--explain", "doctor"])

    assert exc_info.value.code == 2


def test_parse_args_rejects_mutually_exclusive_run_modes() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--dry-run", "--explain", "show", "files"])

    assert exc_info.value.code == 2


def test_parse_args_dry_run_mode() -> None:
    args = parse_args(["--dry-run", "show", "files"])
    assert args.dry_run is True
    assert args.explain is False
    assert args.cli_mode == "request"


def test_parse_args_explain_mode() -> None:
    args = parse_args(["--explain", "show", "files"])
    assert args.explain is True
    assert args.dry_run is False
    assert args.cli_mode == "request"


def test_parse_ollama_list_output_returns_model_names() -> None:
    output = (
        "NAME                ID              SIZE      MODIFIED\n"
        "gemma3:latest       abc123          3.3 GB    2 days ago\n"
        "llama3.2:latest     def456          2.0 GB    1 day ago\n"
    )

    assert parse_ollama_list_output(output) == ["gemma3:latest", "llama3.2:latest"]


def test_repl_help_capabilities_describes_model() -> None:
    output = handle_repl_discovery_command("help capabilities")

    assert output is not None
    assert "capability-first" in output
    assert "curated workflows" in output


def test_repl_capabilities_lists_known_capability_ids() -> None:
    output = handle_repl_discovery_command("capabilities")

    assert output is not None
    assert "filesystem_inspection" in output
    assert "destructive_operations" in output


def test_repl_help_for_capability_includes_commands_and_examples() -> None:
    output = handle_repl_discovery_command("help filesystem_inspection")

    assert output is not None
    assert "Capability: filesystem_inspection" in output
    assert "Supported command families" in output
    assert "Examples:" in output


def test_repl_help_for_command_family_includes_risk_and_maturity() -> None:
    output = handle_repl_discovery_command("help rm")

    assert output is not None
    assert "Command family: rm" in output
    assert "Risk level:" in output
    assert "Maturity:" in output


def test_repl_examples_includes_grouped_capabilities() -> None:
    output = handle_repl_discovery_command("examples")

    assert output is not None
    assert "Example requests by capability" in output
    assert "filesystem_inspection" in output


def test_repl_examples_for_capability_stays_local_and_returns_examples() -> None:
    output = handle_repl_discovery_command("examples filesystem_inspection")

    assert output is not None
    assert "Examples for filesystem_inspection" in output
    assert "find . -name '*.py'" in output or "ls -la" in output


def test_repl_unknown_help_target_returns_guidance() -> None:
    output = handle_repl_discovery_command("help not_a_target")

    assert output is not None
    assert "Unknown help target" in output


def test_main_doctor_runs_diagnostics_without_repl_or_startup(monkeypatch) -> None:
    from oterminus.cli import main

    doctor_cli = Mock(return_value=2)
    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.run_doctor_cli", doctor_cli)
    monkeypatch.setattr("oterminus.cli.load_config", Mock(side_effect=AssertionError("no config")))
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("no Ollama startup check")),
    )
    monkeypatch.setattr("oterminus.cli.repl", Mock(side_effect=AssertionError("no REPL")))

    code = main(["doctor"])

    assert code == 2
    doctor_cli.assert_called_once_with()


def test_main_repl_defers_startup_until_planner_is_needed(monkeypatch) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", Mock())
    setup_check = Mock(side_effect=AssertionError("startup should be lazy"))
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", setup_check)
    monkeypatch.setattr(
        "oterminus.cli.repl",
        lambda repl_planner, repl_validator, repl_executor, **kwargs: 0,
    )

    code = main(["--verbose"])

    assert code == 0
    setup_check.assert_not_called()


def test_main_repl_passes_global_run_mode(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = True
    config.audit_redact = True
    captured: dict[str, object] = {}

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", lambda: "gemma3:latest")
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: Mock())
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: Mock())
    monkeypatch.setattr("oterminus.cli.AuditLogger", lambda path, redact: Mock())

    def fake_repl(_planner, _validator, _executor, **kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("oterminus.cli.repl", fake_repl)

    code = main(["--dry-run"])

    assert code == 0
    assert captured["default_run_mode"] == RunMode.DRY_RUN


def test_main_request_exits_when_startup_setup_fails(monkeypatch, capsys) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = False
    config.audit_redact = True

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)

    def fail_setup() -> str:
        from oterminus.setup import SetupError

        raise SetupError(
            "Ollama is installed but not running. Please start it using `ollama serve`."
        )

    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", fail_setup)

    code = main(["--verbose", "show", "files"])

    assert code == 2
    assert "Ollama is installed but not running." in capsys.readouterr().out


def test_main_dry_run_direct_command_does_not_require_startup(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = True
    config.audit_redact = True

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    startup_check = Mock(side_effect=AssertionError("startup should not be called"))
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", startup_check)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: Mock())
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: Mock())
    monkeypatch.setattr("oterminus.cli.AuditLogger", lambda path, redact: Mock())
    monkeypatch.setattr("oterminus.cli.handle_request", lambda *_args, **_kwargs: 0)

    code = main(["--dry-run", "pwd"])

    assert code == 0
    startup_check.assert_not_called()


def test_main_dry_run_direct_command_does_not_call_planner_or_executor(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = False
    config.audit_redact = True
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls",
        argv=["ls"],
    )
    executor = Mock()

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr(
        "oterminus.cli.OllamaPlannerClient", Mock(side_effect=AssertionError("no planner client"))
    )

    code = main(["--dry-run", "ls"])

    assert code == 0
    executor.run.assert_not_called()


def test_main_explain_direct_command_does_not_call_planner_or_executor(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = False
    config.audit_redact = True
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls",
        argv=["ls"],
    )
    executor = Mock()

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("direct command should not need Ollama")),
    )
    monkeypatch.setattr(
        "oterminus.cli.OllamaPlannerClient", Mock(side_effect=AssertionError("no planner client"))
    )

    code = main(["--explain", "ls"])

    assert code == 0
    executor.run.assert_not_called()


def test_main_dry_run_natural_language_uses_planner_and_skips_executor(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = False
    config.audit_redact = True
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls",
        argv=["ls"],
    )
    executor = Mock()
    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="ls",
        arguments={"path": "."},
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", Mock(return_value="gemma3:latest"))
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", Mock(return_value=Mock()))
    monkeypatch.setattr("oterminus.cli.Planner", lambda client: planner)

    code = main(["--dry-run", "show", "files"])

    assert code == 0
    planner.plan.assert_called_once_with("show files")
    executor.run.assert_not_called()


def test_main_explain_natural_language_uses_planner_and_skips_executor(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = False
    config.audit_redact = True
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls",
        argv=["ls"],
    )
    executor = Mock()
    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="ls",
        arguments={"path": "."},
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", Mock(return_value="gemma3:latest"))
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", Mock(return_value=Mock()))
    monkeypatch.setattr("oterminus.cli.Planner", lambda client: planner)

    code = main(["--explain", "show", "files"])

    assert code == 0
    planner.plan.assert_called_once_with("show files")
    executor.run.assert_not_called()


def test_main_uses_selected_model(monkeypatch) -> None:
    from oterminus.cli import main

    planner_client = Mock()
    planner = Mock()
    validator = Mock()
    executor = Mock()
    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 45
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = True
    config.audit_redact = True

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", lambda: "llama3.2:latest")
    monkeypatch.setattr("oterminus.cli.OllamaPlannerClient", planner_client)
    monkeypatch.setattr("oterminus.cli.Planner", lambda client: planner)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    monkeypatch.setattr(
        "oterminus.cli.handle_request",
        lambda request, planner_factory, req_validator, req_executor, **kwargs: (
            planner_factory().plan(request),
            17,
        )[1],
    )

    code = main(["--verbose", "show", "files"])

    assert code == 17
    planner_client.assert_called_once_with(model="llama3.2:latest")
    assert planner_client.call_args.kwargs == {"model": "llama3.2:latest"}


def test_render_audit_status_disabled() -> None:
    output = render_audit_status(audit_logger=None, enabled=False)

    assert "audit enabled: no" in output
    assert "disabled by OTERMINUS_AUDIT_ENABLED=false" in output


def test_main_audit_disabled_skips_audit_logger(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = False
    config.audit_redact = True

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: Mock())
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: Mock())
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", lambda: "model")
    monkeypatch.setattr(
        "oterminus.cli.AuditLogger", Mock(side_effect=AssertionError("should not create logger"))
    )
    monkeypatch.setattr("oterminus.cli.handle_request", lambda *_args, **_kwargs: 0)

    code = main(["pwd"])

    assert code == 0


def test_main_audit_status_command(monkeypatch, capsys) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = True
    config.audit_redact = True

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: Mock())
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: Mock())
    monkeypatch.setattr(
        "oterminus.cli.AuditLogger",
        lambda path, redact: Mock(
            path=path,
            redact=True,
            status=lambda: {"path": str(path), "exists": "no", "redaction": "enabled"},
        ),
    )

    code = main(["audit", "status"])

    assert code == 0
    output = capsys.readouterr().out
    assert "audit enabled: yes" in output
    assert "redaction enabled: true" in output


def test_render_audit_tail_missing_file(tmp_path: Path) -> None:
    logger = Mock(path=tmp_path / "audit.jsonl")
    output = render_audit_tail("audit tail", audit_logger=logger, enabled=True)
    assert "Audit log not found" in output


def test_render_audit_tail_limit_and_redacted_output(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"timestamp":"t1","user_input":"one","confirmation_result":"confirmed","execution_exit_code":0}',
                '{"timestamp":"t2","user_input":"two [REDACTED]","confirmation_result":"cancelled","execution_exit_code":null}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    logger = Mock(path=path)
    output = render_audit_tail("audit tail 1", audit_logger=logger, enabled=True)
    assert "Showing 1 most recent audit event(s)" in output
    assert "two [REDACTED]" in output
    assert "input='one'" not in output


def test_render_audit_tail_unreadable_path(tmp_path: Path) -> None:
    path = tmp_path / "audit-dir"
    path.mkdir()
    logger = Mock(path=path)
    output = render_audit_tail("audit tail", audit_logger=logger, enabled=True)
    assert "Unable to read audit log" in output


def test_clear_audit_log_cancelled_and_confirmed(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text("line\n", encoding="utf-8")
    logger = Mock(path=path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "nope")
    cancelled = clear_audit_log(logger, enabled=True)
    assert cancelled == "Audit clear cancelled."
    assert path.read_text(encoding="utf-8") == "line\n"
    monkeypatch.setattr("builtins.input", lambda _prompt: "CLEAR AUDIT")
    confirmed = clear_audit_log(logger, enabled=True)
    assert "Cleared audit log" in confirmed
    assert path.read_text(encoding="utf-8") == ""


def test_clear_audit_log_unwritable_path(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "audit-dir"
    path.mkdir()
    logger = Mock(path=path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "CLEAR AUDIT")
    output = clear_audit_log(logger, enabled=True)
    assert "Unable to clear audit log" in output


def test_handle_request_cancel(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="ls",
        arguments={
            "path": ".",
            "long": True,
            "human_readable": True,
            "all": False,
            "recursive": False,
        },
        command="ls -lh",
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls -lh",
        argv=["ls", "-lh"],
    )
    executor = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    code = handle_request("show files", planner, validator, executor)
    assert code == 0
    executor.run.assert_not_called()


def test_handle_request_timeout(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        command="find . -name '*.py'",
        summary="find files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )
    executor = Mock()
    executor.timeout_seconds = 1
    executor.run.side_effect = subprocess.TimeoutExpired(cmd=["find"], timeout=1)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request("find files", planner, validator, executor)
    assert code == 124


def test_handle_request_direct_command_skips_planner(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="cd /tmp",
        argv=["cd", "/tmp"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = "/tmp\n"
    executor.run.return_value.stderr = ""
    monkeypatch.setattr("builtins.input", lambda _: "EXECUTE EXPERIMENTAL")

    code = handle_request("cd /tmp", planner, validator, executor)

    assert code == 0
    planner.plan.assert_not_called()
    executor.run.assert_called_once_with(["cd", "/tmp"], display_command="cd /tmp")


def test_handle_request_direct_command_default_output_is_concise(monkeypatch, capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="pwd",
        argv=["pwd"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = "/tmp\n"
    executor.run.return_value.stderr = ""
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request("pwd", planner, validator, executor)

    assert code == 0
    output = capsys.readouterr().out
    assert "--- command preview ---" in output
    assert "Command: pwd" in output
    assert "Risk: safe" in output
    assert "Skipped Ollama planner." not in output


def test_handle_request_dry_run_skips_confirmation_and_execution(capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        summary="find files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        warnings=["safe warning"],
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )
    executor = Mock()

    code = handle_request("find files", planner, validator, executor, run_mode=RunMode.DRY_RUN)

    assert code == 0
    output = capsys.readouterr().out
    assert "Dry-run mode: execution skipped" in output
    executor.run.assert_not_called()


def test_handle_request_explain_skips_execution(monkeypatch, capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="ps",
        arguments={"all_processes": True},
        summary="list processes",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ps -A",
        argv=["ps", "-A"],
    )
    executor = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request(
        "show running processes", planner, validator, executor, run_mode=RunMode.EXPLAIN
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "--- oterminus explanation ---" in output
    assert "Execution     : Blocked by explain mode" in output
    executor.run.assert_not_called()


def test_handle_request_dry_run_direct_command_skips_planner_and_execution(capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.WRITE,
        rendered_command="chmod +x run.sh",
        argv=["chmod", "+x", "run.sh"],
    )
    executor = Mock()

    code = handle_request("chmod +x run.sh", planner, validator, executor, run_mode=RunMode.DRY_RUN)

    assert code == 0
    assert "execution skipped" in capsys.readouterr().out.lower()
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_archive_extraction_dry_run_does_not_execute(capsys) -> None:
    from oterminus.cli import handle_request
    from oterminus.policies import PolicyConfig
    from oterminus.validator import Validator

    planner = Mock()
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    executor = Mock()

    code = handle_request(
        "tar -xf archive.tar -C out", planner, validator, executor, run_mode=RunMode.DRY_RUN
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Archive extraction can write or overwrite files" in output
    assert "execution skipped" in output.lower()
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_archive_creation_dry_run_does_not_execute(capsys) -> None:
    from oterminus.cli import handle_request
    from oterminus.policies import PolicyConfig
    from oterminus.validator import Validator

    planner = Mock()
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    executor = Mock()

    code = handle_request(
        "zip -r backup.zip src README.md", planner, validator, executor, run_mode=RunMode.DRY_RUN
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Archive creation is write-risk" in output
    assert "execution skipped" in output.lower()
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_archive_creation_explain_does_not_execute(capsys) -> None:
    from oterminus.cli import handle_request
    from oterminus.policies import PolicyConfig
    from oterminus.validator import Validator

    planner = Mock()
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    executor = Mock()

    code = handle_request(
        "tar -czf backup.tar.gz src", planner, validator, executor, run_mode=RunMode.EXPLAIN
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Archive creation is write-risk" in output
    assert "Blocked by explain mode" in output
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_archive_extraction_requires_confirmation(monkeypatch, capsys) -> None:
    from oterminus.cli import handle_request
    from oterminus.policies import PolicyConfig
    from oterminus.validator import Validator

    planner = Mock()
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    executor = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    code = handle_request("unzip archive.zip -d restore", planner, validator, executor)

    assert code == 0
    assert "Cancelled." in capsys.readouterr().out
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_archive_creation_requires_confirmation(monkeypatch, capsys) -> None:
    from oterminus.cli import handle_request
    from oterminus.policies import PolicyConfig
    from oterminus.validator import Validator

    planner = Mock()
    validator = Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False))
    executor = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    code = handle_request("tar -czf backup.tar.gz src", planner, validator, executor)

    assert code == 0
    assert "Cancelled." in capsys.readouterr().out
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_explain_validation_failure_reports_policy_and_skips_executor(
    capsys,
) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.EXPERIMENTAL,
        command_family="rm",
        command="rm -rf /",
        summary="dangerous",
        explanation="desc",
        risk_level=RiskLevel.DANGEROUS,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=False,
        risk_level=RiskLevel.DANGEROUS,
        reasons=["dangerous commands are disabled by policy"],
        rendered_command="rm -rf /",
        argv=["rm", "-rf", "/"],
    )
    executor = Mock()

    code = handle_request("delete /", planner, validator, executor, run_mode=RunMode.EXPLAIN)

    assert code == 3
    output = capsys.readouterr().out
    assert "Policy        : Blocked by current policy checks." in output
    assert "dangerous commands are disabled by policy" in output
    executor.run.assert_not_called()


def test_handle_request_explain_does_not_expand_single_dash_long_options(capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )
    executor = Mock()

    code = handle_request(
        "find . -name '*.py'", planner, validator, executor, run_mode=RunMode.EXPLAIN
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Flags         :" not in output


def test_handle_request_direct_command_verbose_shows_trace(monkeypatch, capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="pwd",
        argv=["pwd"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = "/tmp\n"
    executor.run.return_value.stderr = ""
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request("pwd", planner, validator, executor, debug_trace=True)

    assert code == 0
    output = capsys.readouterr().out
    assert "[trace] Detected as direct shell command." in output
    assert "[trace] Skipped Ollama planner." in output
    assert "[trace] Validation accepted." in output


def test_handle_request_natural_language_uses_planner(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = ""
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request("show files in this directory", planner, validator, executor)

    assert code == 0
    planner.plan.assert_called_once_with("show files in this directory")
    executor.run.assert_called_once_with(
        ["find", ".", "-name", "*.py"],
        display_command="find . -name '*.py'",
    )


def test_handle_request_ambiguous_request_is_intercepted(capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    executor = Mock()

    code = handle_request("delete unnecessary files", planner, validator, executor)

    assert code == 0
    output = capsys.readouterr().out
    assert "This request is ambiguous." in output
    assert "list large files" in output
    planner.plan.assert_not_called()
    validator.validate.assert_not_called()
    executor.run.assert_not_called()


def test_ask_confirmation_requires_experimental_phrase(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "EXECUTE")
    assert ask_confirmation(ConfirmationLevel.VERY_STRONG) is False

    monkeypatch.setattr("builtins.input", lambda _: "EXECUTE EXPERIMENTAL")
    assert ask_confirmation(ConfirmationLevel.VERY_STRONG) is True


def test_handle_request_writes_structured_audit_log(monkeypatch, tmp_path: Path) -> None:
    from oterminus.audit import AuditLogger
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        warnings=["test-warning"],
        reasons=[],
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = ""

    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request(
        "show files in this directory",
        planner,
        validator,
        executor,
        audit_logger=AuditLogger(audit_path),
    )

    assert code == 0
    payload = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert payload["user_input"] == "show files in this directory"
    assert payload["direct_command_detected"] is False
    assert payload["routed_category"] == "filesystem_inspect"
    assert payload["proposal_mode"] == "structured"
    assert payload["command_family"] == "find"
    assert payload["validation_accepted"] is True
    assert payload["warnings"] == ["test-warning"]
    assert payload["confirmation_result"] == "confirmed"
    assert payload["execution_exit_code"] == 0
    assert payload["argv"] == ["find", ".", "-name", "*.py"]
    assert payload["duration_ms"] >= 0


def test_handle_request_dry_run_writes_audit_without_execution(tmp_path: Path) -> None:
    from oterminus.audit import AuditLogger
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="find",
        arguments={"path": ".", "name": "*.py"},
        summary="list files",
        explanation="desc",
        risk_level=RiskLevel.SAFE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="find . -name '*.py'",
        argv=["find", ".", "-name", "*.py"],
    )
    executor = Mock()
    audit_path = tmp_path / "audit.jsonl"

    code = handle_request(
        "show files in this directory",
        planner,
        validator,
        executor,
        run_mode=RunMode.DRY_RUN,
        audit_logger=AuditLogger(audit_path),
    )

    assert code == 0
    payload = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert payload["confirmation_result"] == "skipped_dry_run"
    assert payload["execution_exit_code"] is None


def test_handle_request_ambiguous_writes_audit_without_executor(tmp_path: Path) -> None:
    from oterminus.audit import AuditLogger
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    executor = Mock()
    audit_path = tmp_path / "audit.jsonl"

    code = handle_request(
        "repair permissions",
        planner,
        validator,
        executor,
        audit_logger=AuditLogger(audit_path),
    )

    assert code == 0
    payload = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert payload["ambiguity_detected"] is True
    assert payload["ambiguity_reason"] is not None
    assert payload["ambiguity_safe_options"] == [
        "list large files",
        "list recently modified files",
        "inspect permissions",
        "show temporary-looking files",
        "show project files",
    ]
    assert payload["confirmation_result"] == "blocked_ambiguous"
    validator.validate.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_ambiguous_lifecycle_blocks_before_confirmation(monkeypatch, capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    executor = Mock()
    monkeypatch.setattr(
        "builtins.input", Mock(side_effect=AssertionError("confirmation should not be shown"))
    )

    for request in ("clean this folder", "delete unnecessary files", "repair permissions"):
        code = handle_request(request, planner, validator, executor)

        assert code == 0

    output = capsys.readouterr().out
    assert output.count("This request is ambiguous.") == 3
    assert "Safer inspections I can do instead:" in output
    planner.plan.assert_not_called()
    validator.validate.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_ambiguous_dry_run_and_explain_stop_before_planner_or_executor() -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    executor = Mock()

    dry_run_code = handle_request(
        "clean this folder", planner, validator, executor, run_mode=RunMode.DRY_RUN
    )
    explain_code = handle_request(
        "repair permissions", planner, validator, executor, run_mode=RunMode.EXPLAIN
    )

    assert dry_run_code == 0
    assert explain_code == 0
    planner.plan.assert_not_called()
    validator.validate.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_direct_commands_skip_ambiguity_and_go_to_validator() -> None:
    from oterminus.cli import handle_request
    from oterminus.policies import PolicyConfig
    from oterminus.validator import Validator

    planner = Mock()
    validator = Mock(wraps=Validator(PolicyConfig(mode=RiskLevel.WRITE, allow_dangerous=False)))
    executor = Mock()

    chmod_code = handle_request(
        "chmod +x run.sh", planner, validator, executor, run_mode=RunMode.DRY_RUN
    )
    rm_code = handle_request("rm -rf build", planner, validator, executor, run_mode=RunMode.DRY_RUN)

    assert chmod_code == 0
    assert rm_code == 3
    assert validator.validate.call_count == 2
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_explicit_disabled_packs_does_not_require_validator_policy() -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls",
        argv=["ls"],
    )
    executor = Mock()

    code = handle_request(
        "ls",
        planner,
        validator,
        executor,
        run_mode=RunMode.DRY_RUN,
        disabled_pack_ids=frozenset(),
    )

    assert code == 0
    validator.validate.assert_called_once()
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_without_policy_disabled_pack_attribute_does_not_error() -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.policy = type("PolicyStub", (), {})()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="ls",
        argv=["ls"],
    )
    executor = Mock()

    code = handle_request("ls", planner, validator, executor, run_mode=RunMode.DRY_RUN)

    assert code == 0
    validator.validate.assert_called_once()
    planner.plan.assert_not_called()
    executor.run.assert_not_called()


def test_handle_request_specific_natural_language_permission_request_uses_planner(
    monkeypatch,
) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    planner.plan.return_value = Proposal(
        action_type=ActionType.SHELL_COMMAND,
        mode=ProposalMode.STRUCTURED,
        command_family="chmod",
        arguments={"path": "run.sh", "mode": "755"},
        summary="make executable",
        explanation="desc",
        risk_level=RiskLevel.WRITE,
        needs_confirmation=True,
        notes=[],
    )
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.WRITE,
        rendered_command="chmod 755 run.sh",
        argv=["chmod", "755", "run.sh"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = ""
    monkeypatch.setattr("builtins.input", lambda _: "y")

    code = handle_request("make run.sh executable", planner, validator, executor)

    assert code == 0
    planner.plan.assert_called_once_with("make run.sh executable")
    validator.validate.assert_called_once()
    executor.run.assert_called_once_with(
        ["chmod", "755", "run.sh"], display_command="chmod 755 run.sh"
    )


def test_main_ambiguous_request_does_not_require_startup_or_planner(
    monkeypatch, tmp_path: Path
) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = tmp_path / "audit.jsonl"
    config.audit_enabled = True
    config.audit_redact = False
    validator = Mock()
    executor = Mock()

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: validator)
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: executor)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("ambiguous request should not need Ollama setup")),
    )
    monkeypatch.setattr(
        "oterminus.cli.OllamaPlannerClient", Mock(side_effect=AssertionError("no planner client"))
    )

    code = main(["clean", "this", "folder"])

    assert code == 0
    payload = json.loads(config.audit_log_path.read_text(encoding="utf-8").strip())
    assert payload["ambiguity_detected"] is True
    assert payload["confirmation_result"] == "blocked_ambiguous"
    validator.validate.assert_not_called()
    executor.run.assert_not_called()


def test_history_records_are_created(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="pwd",
        argv=["pwd"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = "/tmp\n"
    executor.run.return_value.stderr = ""
    monkeypatch.setattr("builtins.input", lambda _: "y")

    history = SessionHistory()
    code = handle_request("pwd", planner, validator, executor, session_history=history)

    assert code == 0
    items = history.all_items()
    assert len(items) == 1
    assert items[0].id == 1
    assert items[0].user_input == "pwd"
    assert items[0].execution_status == "executed"
    assert items[0].exit_code == 0


def test_history_command_displays_records() -> None:
    history = SessionHistory()
    item = history.start("show files")
    item.rendered_command = "find . -name '*.py'"
    item.risk_level = "safe"
    item.execution_status = "executed"

    output = handle_repl_history_command(
        "history",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )

    assert output is not None
    assert "id" in output
    assert "show files" in output
    assert "find . -name '*.py'" in output


def test_history_empty_state_message() -> None:
    output = handle_repl_history_command(
        "history",
        session_history=SessionHistory(),
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )
    assert output == "No session history yet."


def test_history_limit_and_invalid_limit_usage() -> None:
    history = SessionHistory()
    for idx in range(1, 4):
        item = history.start(f"request {idx}")
        item.rendered_command = f"echo {idx}"
        item.risk_level = "safe"
        item.execution_status = "executed"

    limited = handle_repl_history_command(
        "history 2",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )
    assert limited is not None
    assert "request 1" not in limited
    assert "request 2" in limited
    assert "request 3" in limited

    invalid = handle_repl_history_command(
        "history -2",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )
    assert invalid == "Usage: history | history <n>"


def test_explain_history_item_does_not_execute(monkeypatch, capsys) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="pwd",
        argv=["pwd"],
    )
    executor = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "n")
    history = SessionHistory()

    handle_request("pwd", planner, validator, executor, session_history=history)
    executor.run.assert_not_called()

    output = handle_repl_history_command(
        "explain 1",
        session_history=history,
        planner_factory=planner,
        validator=validator,
        executor=executor,
        audit_logger=None,
        debug_trace=False,
    )

    assert output is not None
    assert "--- oterminus explanation ---" in output
    assert executor.run.call_count == 0
    assert "blocked by explain mode" in output.lower()
    assert "execution output" not in capsys.readouterr().out.lower()


def test_explain_history_id_not_found_and_limited_details() -> None:
    history = SessionHistory()
    item = history.start("clean this folder")
    item.execution_status = "blocked_ambiguous"

    missing = handle_repl_history_command(
        "explain 42",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )
    assert missing == "History id 42 not found."

    limited = handle_repl_history_command(
        "explain 1",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )
    assert limited is not None
    assert "limited details" in limited.lower()
    assert "blocked_ambiguous" in limited


def test_explain_invalid_numeric_target_shows_usage() -> None:
    output = handle_repl_history_command(
        "explain -1",
        session_history=SessionHistory(),
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )
    assert output == "Usage: explain <history_id> | explain <request>"


def test_history_row_truncates_newlines_and_long_text() -> None:
    history = SessionHistory()
    item = history.start("very long\nrequest " + ("x" * 100))
    item.rendered_command = "echo start\t" + ("y" * 100)
    item.risk_level = "safe"
    item.execution_status = "executed"

    output = history.render_table()
    assert "\nrequest" not in output
    assert "…" in output


def test_rerun_revalidates_and_requires_confirmation(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.side_effect = [
        ValidationResult(
            accepted=True,
            risk_level=RiskLevel.SAFE,
            rendered_command="pwd",
            argv=["pwd"],
        ),
        ValidationResult(
            accepted=True,
            risk_level=RiskLevel.SAFE,
            rendered_command="pwd",
            argv=["pwd"],
        ),
    ]
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = ""
    answers = iter(["n", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    history = SessionHistory()

    handle_request("pwd", planner, validator, executor, session_history=history)
    output = handle_repl_history_command(
        "rerun 1",
        session_history=history,
        planner_factory=planner,
        validator=validator,
        executor=executor,
        audit_logger=None,
        debug_trace=False,
    )

    assert output == ""
    assert validator.validate.call_count == 2
    assert executor.run.call_count == 1


def test_rerun_cannot_bypass_rejection(monkeypatch) -> None:
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=False,
        risk_level=RiskLevel.DANGEROUS,
        reasons=["dangerous commands are disabled by policy"],
        rendered_command="rm -rf /",
        argv=["rm", "-rf", "/"],
    )
    executor = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "y")
    history = SessionHistory()

    handle_request("rm -rf /", planner, validator, executor, session_history=history)
    handle_repl_history_command(
        "rerun 1",
        session_history=history,
        planner_factory=planner,
        validator=validator,
        executor=executor,
        audit_logger=None,
        debug_trace=False,
    )

    assert validator.validate.call_count == 2
    executor.run.assert_not_called()


def test_history_id_not_found_is_clean() -> None:
    output = handle_repl_history_command(
        "rerun 99",
        session_history=SessionHistory(),
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )

    assert output == "History id 99 not found."


def test_rerun_writes_audit_source_history_id(monkeypatch, tmp_path: Path) -> None:
    from oterminus.audit import AuditLogger
    from oterminus.cli import handle_request

    planner = Mock()
    validator = Mock()
    validator.validate.return_value = ValidationResult(
        accepted=True,
        risk_level=RiskLevel.SAFE,
        rendered_command="pwd",
        argv=["pwd"],
    )
    executor = Mock()
    executor.run.return_value.returncode = 0
    executor.run.return_value.stdout = ""
    executor.run.return_value.stderr = ""
    answers = iter(["n", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    history = SessionHistory()
    audit_path = tmp_path / "audit.jsonl"
    audit_logger = AuditLogger(audit_path)

    handle_request(
        "pwd", planner, validator, executor, session_history=history, audit_logger=audit_logger
    )
    handle_repl_history_command(
        "rerun 1",
        session_history=history,
        planner_factory=planner,
        validator=validator,
        executor=executor,
        audit_logger=audit_logger,
        debug_trace=False,
    )

    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    rerun_payload = json.loads(lines[-1])
    assert rerun_payload["rerun_source_history_id"] == 1


def test_create_prompt_session_falls_back_when_prompt_toolkit_unavailable(monkeypatch) -> None:
    from oterminus.cli import create_prompt_session

    monkeypatch.setattr(
        "oterminus.cli.get_completion_backend_status", lambda: ("plain_input", None)
    )

    session, backend = create_prompt_session()

    assert session is None
    assert backend == "plain_input"


def test_repl_debug_trace_reports_plain_input_backend(monkeypatch, capsys) -> None:
    from oterminus.cli import repl

    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    answers = iter(["exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    code = repl(Mock(), Mock(), Mock(), debug_trace=True)

    assert code == 0
    output = capsys.readouterr().out
    assert "[trace] prompt_toolkit unavailable; falling back to plain input()" in output


def test_repl_debug_trace_reports_prompt_toolkit_backend(monkeypatch, capsys) -> None:
    from oterminus.cli import repl

    class FakePromptSession:
        def prompt(self, _prompt: str) -> str:
            return "exit"

    monkeypatch.setattr(
        "oterminus.cli.create_prompt_session", lambda: (FakePromptSession(), "prompt_toolkit")
    )

    code = repl(Mock(), Mock(), Mock(), debug_trace=True)

    assert code == 0
    output = capsys.readouterr().out
    assert "[trace] prompt_toolkit completion enabled" in output


def test_repl_passes_persistent_store_to_handle_request(monkeypatch) -> None:
    from oterminus.cli import repl

    captured: dict[str, object] = {}

    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    answers = iter(["show files", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    def fake_handle_request(*_args, **kwargs) -> int:
        captured["persistent_store"] = kwargs.get("persistent_store")
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)

    store = Mock()
    store.load.return_value = []
    code = repl(Mock(), Mock(), Mock(), persistent_store=store)

    assert code == 0
    assert captured["persistent_store"] is store


def test_main_explain_failures_does_not_require_startup_before_request_handling(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    config.audit_enabled = False
    config.audit_redact = True
    config.explain_failures = True
    config.failure_explanation_max_chars = 4000

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr(
        "oterminus.cli.ensure_startup_ready",
        Mock(side_effect=AssertionError("startup should not be called eagerly")),
    )
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: Mock())
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: Mock())

    def fake_handle_request(*_args, **kwargs) -> int:
        assert kwargs.get("failure_explainer_factory") is not None
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)

    code = main(["pwd"])
    assert code == 0


def test_repl_propagates_failure_explainer_to_requests(monkeypatch) -> None:
    from oterminus.cli import repl

    captured: list[dict[str, object]] = []
    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    answers = iter(["pwd", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    explainer = Mock()

    def fake_handle_request(*_args, **kwargs) -> int:
        captured.append(kwargs)
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)

    code = repl(Mock(), Mock(), Mock(), failure_explainer=explainer)

    assert code == 0
    assert captured[0].get("failure_explainer") is explainer


def test_handle_repl_history_rerun_propagates_failure_explainer(monkeypatch) -> None:
    from oterminus.cli import handle_repl_history_command
    from oterminus.history import SessionHistory

    history = SessionHistory()
    item = history.start("pwd")
    item.persisted_id = 42

    captured: dict[str, object] = {}

    def fake_handle_request(*_args, **kwargs) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)

    explainer = Mock()
    out = handle_repl_history_command(
        "rerun 1",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
        failure_explainer=explainer,
    )

    assert out == ""
    assert captured.get("failure_explainer") is explainer

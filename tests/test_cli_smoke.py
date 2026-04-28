import json
from pathlib import Path
from unittest.mock import Mock

import subprocess

from oterminus.cli import (
    RunMode,
    SessionHistory,
    ask_confirmation,
    handle_repl_discovery_command,
    handle_repl_history_command,
    parse_args,
)
from oterminus.models import ActionType, Proposal, ProposalMode, RiskLevel, ValidationResult
from oterminus.ollama_client import parse_ollama_list_output
from oterminus.policies import ConfirmationLevel


def test_parse_args_one_shot() -> None:
    args = parse_args(["show", "files"])
    assert args.request == ["show", "files"]


def test_parse_args_dry_run_mode() -> None:
    args = parse_args(["--dry-run", "show", "files"])
    assert args.dry_run is True
    assert args.explain is False


def test_parse_args_explain_mode() -> None:
    args = parse_args(["--explain", "show", "files"])
    assert args.explain is True
    assert args.dry_run is False


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
    assert "Maturity levels" in output


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
    assert "Example requests" in output


def test_repl_help_for_command_family_includes_risk_and_maturity() -> None:
    output = handle_repl_discovery_command("help rm")

    assert output is not None
    assert "Command family: rm" in output
    assert "Risk level:" in output
    assert "Maturity:" in output


def test_repl_examples_includes_grouped_capabilities() -> None:
    output = handle_repl_discovery_command("examples")

    assert output is not None
    assert "Common example requests by capability" in output
    assert "filesystem_inspection" in output


def test_repl_unknown_help_target_returns_guidance() -> None:
    output = handle_repl_discovery_command("help not_a_target")

    assert output is not None
    assert "Unknown help target" in output


def test_main_repl_startup_validates_once(monkeypatch) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", Mock())
    setup_check = Mock(return_value="gemma3:latest")
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", setup_check)
    monkeypatch.setattr(
        "oterminus.cli.repl",
        lambda repl_planner, repl_validator, repl_executor, **kwargs: 0,
    )

    code = main(["--verbose"])

    assert code == 0
    setup_check.assert_called_once()


def test_main_repl_passes_global_run_mode(monkeypatch) -> None:
    from oterminus.cli import main

    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 30
    config.audit_log_path = Path("/tmp/oterminus-audit.jsonl")
    captured: dict[str, object] = {}

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", lambda: "gemma3:latest")
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: Mock())
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: Mock())
    monkeypatch.setattr("oterminus.cli.AuditLogger", lambda path: Mock())

    def fake_repl(_planner, _validator, _executor, **kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("oterminus.cli.repl", fake_repl)

    code = main(["--dry-run"])

    assert code == 0
    assert captured["default_run_mode"] == RunMode.DRY_RUN


def test_main_request_exits_when_startup_setup_fails(monkeypatch, capsys) -> None:
    from oterminus.cli import main

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", Mock())

    def fail_setup() -> str:
        from oterminus.setup import SetupError

        raise SetupError("Ollama is installed but not running. Please start it using `ollama serve`.")

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

    monkeypatch.setattr("oterminus.cli.configure_logging", lambda verbose: None)
    monkeypatch.setattr("oterminus.cli.load_config", lambda: config)
    startup_check = Mock(side_effect=AssertionError("startup should not be called"))
    monkeypatch.setattr("oterminus.cli.ensure_startup_ready", startup_check)
    monkeypatch.setattr("oterminus.cli.Validator", lambda policy: Mock())
    monkeypatch.setattr("oterminus.cli.Executor", lambda timeout_seconds: Mock())
    monkeypatch.setattr("oterminus.cli.AuditLogger", lambda path: Mock())
    monkeypatch.setattr("oterminus.cli.handle_request", lambda *_args, **_kwargs: 0)

    code = main(["--dry-run", "pwd"])

    assert code == 0
    startup_check.assert_not_called()


def test_main_uses_selected_model(monkeypatch) -> None:
    from oterminus.cli import main

    planner_client = Mock()
    planner = Mock()
    validator = Mock()
    executor = Mock()
    config = Mock()
    config.policy = Mock()
    config.timeout_seconds = 45

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

    code = handle_request("show running processes", planner, validator, executor, run_mode=RunMode.EXPLAIN)

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


def test_handle_request_explain_validation_failure_reports_policy_and_skips_executor(capsys) -> None:
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

    code = handle_request("find . -name '*.py'", planner, validator, executor, run_mode=RunMode.EXPLAIN)

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

    handle_request("pwd", planner, validator, executor, session_history=history, audit_logger=audit_logger)
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

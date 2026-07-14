from unittest.mock import Mock

from oterminus.cli import handle_repl_history_command
from oterminus.history import SessionHistory
from oterminus.models import FailureExplanation


def _history_with_failure() -> SessionHistory:
    history = SessionHistory()
    item = history.start("list missing")
    item.rendered_command = "ls /missing"
    item.execution_status = "executed"
    item.exit_code = 2
    item.stderr = "ls: cannot access '/missing': No such file or directory"
    return history


def test_last_failure_no_failure_message() -> None:
    output = handle_repl_history_command(
        "last failure",
        session_history=SessionHistory(),
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )

    assert output == "No failed command has been recorded in this REPL session."


def test_last_failure_includes_details_and_does_not_execute_or_plan() -> None:
    history = _history_with_failure()
    planner = Mock()
    validator = Mock()
    executor = Mock()

    output = handle_repl_history_command(
        "last failure",
        session_history=history,
        planner_factory=planner,
        validator=validator,
        executor=executor,
        audit_logger=None,
        debug_trace=False,
    )

    assert output is not None
    assert "History id: 1" in output
    assert "list missing" in output
    assert "ls /missing" in output
    assert "Exit code: 2" in output
    assert "No such file" in output
    planner.plan.assert_not_called()
    validator.validate.assert_not_called()
    executor.run.assert_not_called()


def test_last_failure_handles_missing_stderr_gracefully() -> None:
    history = SessionHistory()
    item = history.start("bad")
    item.rendered_command = "false"
    item.execution_status = "executed"
    item.exit_code = 1

    output = handle_repl_history_command(
        "last failure",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )

    assert output is not None
    assert "stderr: (none recorded)" in output


def test_explain_last_failure_uses_stored_explanation_without_llm() -> None:
    history = _history_with_failure()
    item = history.latest_failure()
    assert item is not None
    item.failure_likely_cause = "The path does not exist."
    item.failure_stderr_summary = "No such file or directory."
    explainer = Mock()

    output = handle_repl_history_command(
        "explain last failure",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
        failure_explainer=explainer,
    )

    assert output is not None
    assert "The path does not exist." in output
    explainer.explain.assert_not_called()


def test_explain_last_failure_invokes_configured_explainer_and_stores_result() -> None:
    history = _history_with_failure()
    explainer = Mock()
    explainer.explain.return_value = FailureExplanation(
        command="ls /missing",
        exit_code=2,
        stderr_summary="No such file.",
        likely_cause="The target path is missing.",
        suggested_next_action="ls /",
        suggested_next_action_mode="copy-only",
    )

    output = handle_repl_history_command(
        "explain last failure",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
        failure_explainer=explainer,
    )

    assert output is not None
    assert "The target path is missing." in output
    explainer.explain.assert_called_once()
    assert history.latest_failure().failure_likely_cause == "The target path is missing."


def test_explain_last_failure_disabled_message() -> None:
    history = _history_with_failure()

    output = handle_repl_history_command(
        "explain last failure",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )

    assert output is not None
    assert "disabled or unavailable" in output
    assert "Exit code: 2" in output


def test_recover_last_failure_no_failure_does_not_call_lifecycle(monkeypatch) -> None:
    called = False

    def fake_handle_request(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)
    planner = Mock()
    validator = Mock()
    executor = Mock()
    explainer = Mock()

    output = handle_repl_history_command(
        "suggest fix for last failure",
        session_history=SessionHistory(),
        planner_factory=planner,
        validator=validator,
        executor=executor,
        audit_logger=None,
        debug_trace=False,
        failure_explainer=explainer,
    )

    assert output == "No failed command has been recorded in this REPL session."
    assert called is False
    explainer.explain.assert_not_called()
    validator.validate.assert_not_called()
    executor.run.assert_not_called()


def test_recover_last_failure_uses_stored_suggestion_dry_run(monkeypatch) -> None:
    calls = []

    def fake_handle_request(*args, **kwargs):
        calls.append((args, kwargs))
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)
    history = _history_with_failure()
    item = history.latest_failure()
    assert item is not None
    item.failure_suggested_next_action = "ls /"
    item.failure_suggested_next_action_mode = "dry-run"

    output = handle_repl_history_command(
        "recover last failure",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
        auto_execute_safe=True,
    )

    assert output == ""
    assert calls
    args, kwargs = calls[0]
    assert args[0] == "ls /"
    assert kwargs["run_mode"].value == "dry-run"
    assert kwargs["recovery_source_history_id"] == item.id
    assert kwargs["auto_execute_safe"] is True


def test_recover_last_failure_copy_only_suggestion_is_display_only(monkeypatch) -> None:
    calls = []

    def fake_handle_request(*args, **kwargs):
        calls.append((args, kwargs))
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)
    history = _history_with_failure()
    item = history.latest_failure()
    assert item is not None
    item.failure_suggested_next_action = "ls /"
    item.failure_suggested_next_action_mode = "copy-only"
    validator = Mock()
    executor = Mock()

    output = handle_repl_history_command(
        "recover last failure",
        session_history=history,
        planner_factory=Mock(),
        validator=validator,
        executor=executor,
        audit_logger=None,
        debug_trace=False,
    )

    assert output is not None
    assert "copy-only" in output
    assert "ls /" in output
    assert calls == []
    validator.validate.assert_not_called()
    executor.run.assert_not_called()


def test_suggest_fix_last_failure_generates_and_stores_suggestion(monkeypatch) -> None:
    calls = []

    def fake_handle_request(*args, **kwargs):
        calls.append((args, kwargs))
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)
    history = _history_with_failure()
    explainer = Mock()
    explainer.explain.return_value = FailureExplanation(
        command="ls /missing",
        exit_code=2,
        stderr_summary="No such file.",
        likely_cause="The target path is missing.",
        suggested_next_action="stat /missing",
        suggested_next_action_mode="dry-run",
    )

    output = handle_repl_history_command(
        "suggest fix for last failure",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
        failure_explainer=explainer,
    )

    assert output == ""
    assert calls[0][0][0] == "stat /missing"
    assert history.latest_failure().failure_suggested_next_action == "stat /missing"


def test_suggest_fix_generated_copy_only_suggestion_is_display_only(monkeypatch) -> None:
    calls = []

    def fake_handle_request(*args, **kwargs):
        calls.append((args, kwargs))
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)
    history = _history_with_failure()
    explainer = Mock()
    explainer.explain.return_value = FailureExplanation(
        command="ls /missing",
        exit_code=2,
        stderr_summary="No such file.",
        likely_cause="The target path is missing.",
        suggested_next_action="ls /",
        suggested_next_action_mode="copy-only",
    )

    output = handle_repl_history_command(
        "suggest fix for last failure",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
        failure_explainer=explainer,
    )

    assert output is not None
    assert "copy-only" in output
    assert "ls /" in output
    assert calls == []
    assert history.latest_failure().failure_suggested_next_action_mode == "copy-only"


def test_recover_last_failure_disabled_without_suggestion() -> None:
    output = handle_repl_history_command(
        "recover last failure",
        session_history=_history_with_failure(),
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )

    assert output is not None
    assert "Failure recovery needs failure explanations" in output


def test_repl_ambiguous_cancel_returns_to_prompt(monkeypatch, capsys) -> None:
    from oterminus.cli import repl

    handle = Mock()
    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    answers = iter(["clean this folder", "cancel", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr("oterminus.cli.handle_request", handle)

    assert repl(Mock(), Mock(), Mock()) == 0

    output = capsys.readouterr().out
    assert "This request is ambiguous and has not been planned." in output
    handle.assert_not_called()


def test_repl_ambiguous_unresolved_returns_to_prompt(monkeypatch, capsys) -> None:
    from oterminus.cli import repl

    handle = Mock()
    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    answers = iter(["clean this folder", "fix this", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr("oterminus.cli.handle_request", handle)

    assert repl(Mock(), Mock(), Mock()) == 0

    assert "still ambiguous" in capsys.readouterr().out
    handle.assert_not_called()


def test_repl_clarified_enters_handle_request_once_preserving_mode_and_disabling_auto_execute(
    monkeypatch,
) -> None:
    from oterminus.cli import RunMode, repl

    captured: dict[str, object] = {}
    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    answers = iter(["dry-run clean this folder", "list large files in ~/Downloads", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    def fake_handle_request(request, *_args, **kwargs) -> int:
        captured["request"] = request
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)

    assert repl(Mock(), Mock(), Mock(), auto_execute_safe=True) == 0

    assert captured["request"] == "list large files in ~/Downloads"
    assert captured["run_mode"] == RunMode.DRY_RUN
    assert captured["auto_execute_safe"] is False


def test_repl_direct_input_skips_clarification(monkeypatch) -> None:
    from oterminus.cli import repl

    captured: dict[str, object] = {}
    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    answers = iter(["pwd", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    def fake_handle_request(request, *_args, **kwargs) -> int:
        captured["request"] = request
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("oterminus.cli.handle_request", fake_handle_request)

    assert repl(Mock(), Mock(), Mock(), auto_execute_safe=True) == 0

    assert captured["request"] == "pwd"
    assert captured["auto_execute_safe"] is True


def test_repl_clarification_eof_exits_without_planning(monkeypatch, capsys) -> None:
    from oterminus.cli import repl

    handle = Mock()
    monkeypatch.setattr("oterminus.cli.create_prompt_session", lambda: (None, "plain_input"))
    calls = iter(["clean this folder"])

    def fake_input(_prompt: str) -> str:
        try:
            return next(calls)
        except StopIteration as exc:
            raise EOFError from exc

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("oterminus.cli.handle_request", handle)

    assert repl(Mock(), Mock(), Mock()) == 0

    assert "This request is ambiguous and has not been planned." in capsys.readouterr().out
    handle.assert_not_called()


def test_explain_history_renders_clarification_source_details() -> None:
    history = SessionHistory()
    item = history.start("clean this folder")
    item.ambiguity_detected = True
    item.ambiguity_reason = "Matched ambiguous phrase"
    item.clarification_requested = True
    item.clarification_prompt = "clarify> "
    item.clarification_answer = "list files in ."
    item.clarification_outcome = "clarified"
    item.clarified_request_text = "list files in ."
    item.execution_status = "clarified"

    output = handle_repl_history_command(
        "explain 1",
        session_history=history,
        planner_factory=Mock(),
        validator=Mock(),
        executor=Mock(),
        audit_logger=None,
        debug_trace=False,
    )

    assert output is not None
    assert "Ambiguity: detected" in output
    assert "Clarification outcome: clarified" in output
    assert "Clarified request: list files in ." in output


def test_record_repl_clarification_source_has_no_lifecycle_details() -> None:
    from oterminus.ambiguity import AmbiguityResult, ClarificationResult, ClarificationStatus
    from oterminus.cli import _record_repl_clarification_source

    history = SessionHistory()
    result = ClarificationResult(
        ClarificationStatus.CLARIFIED,
        original_request="clean this folder",
        ambiguity=AmbiguityResult(True, "broad", ("list files",)),
        prompt="prompt text",
        answer="list files in .",
        clarified_request="list files in .",
    )

    source_id = _record_repl_clarification_source(
        result,
        session_history=history,
        persistent_store=None,
        audit_logger=None,
        debug_trace=False,
    )

    item = history.find(source_id or 0)
    assert item is not None
    assert item.execution_status == "clarified"
    assert item.proposal is None
    assert item.validation is None
    assert item.rendered_command is None
    assert item.clarification_outcome == "clarified"
    assert item.clarified_request_text == "list files in ."

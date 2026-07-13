from oterminus.ambiguity import detect_ambiguity


def test_detect_ambiguity_known_vague_requests() -> None:
    result = detect_ambiguity("clean this folder")

    assert result.is_ambiguous is True
    assert "ambiguous phrase" in result.reason.lower()
    assert result.suggested_safe_options == (
        "list large files",
        "list recently modified files",
        "inspect permissions",
        "show temporary-looking files",
        "show project files",
    )
    assert result.follow_up_questions


def test_detect_ambiguity_generic_broad_scope_request() -> None:
    result = detect_ambiguity("optimize this directory")

    assert result.is_ambiguous is True
    assert "broad mutation wording" in result.reason.lower()


def test_detect_ambiguity_safe_specific_request_not_intercepted() -> None:
    result = detect_ambiguity("list files in /tmp sorted by size")

    assert result.is_ambiguous is False
    assert result.suggested_safe_options == ()


def test_detect_ambiguity_specific_permission_request_not_intercepted() -> None:
    result = detect_ambiguity("make run.sh executable")

    assert result.is_ambiguous is False


def test_detect_ambiguity_direct_shell_command_text_is_not_ambiguous() -> None:
    result = detect_ambiguity("chmod +x run.sh")

    assert result.is_ambiguous is False


def test_detect_ambiguity_does_not_match_inside_words() -> None:
    result = detect_ambiguity("prefix this variable names")

    assert result.is_ambiguous is False


def test_detect_ambiguity_archive_extraction_missing_destination() -> None:
    result = detect_ambiguity("extract archive.tar")

    assert result.is_ambiguous is True
    assert "missing an explicit destination" in result.reason


def test_detect_ambiguity_guarded_archive_extraction_not_intercepted() -> None:
    result = detect_ambiguity("extract archive.tar into ./out")

    assert result.is_ambiguous is False


def test_detect_ambiguity_guarded_unpack_archive_not_intercepted_by_phrase() -> None:
    result = detect_ambiguity("unpack archive.zip into ./out")

    assert result.is_ambiguous is False


def test_detect_ambiguity_scoped_restore_backup_not_intercepted() -> None:
    result = detect_ambiguity("restore backup.zip into ./out")

    assert result.is_ambiguous is False


def test_detect_ambiguity_guarded_archive_cli_destination_flags_not_intercepted() -> None:
    assert detect_ambiguity("please extract archive.tar -C out").is_ambiguous is False
    assert detect_ambiguity("please unzip archive.zip -d restore").is_ambiguous is False


from unittest.mock import Mock

from oterminus.ambiguity import ClarificationStatus
from oterminus.cli import clarify_repl_request


def test_clarify_repl_request_direct_command_not_needed() -> None:
    input_fn = Mock(side_effect=AssertionError("no prompt"))
    output_fn = Mock()

    result = clarify_repl_request("pwd", input_fn=input_fn, output_fn=output_fn)

    assert result.status == ClarificationStatus.NOT_NEEDED
    input_fn.assert_not_called()
    output_fn.assert_not_called()


def test_clarify_repl_request_specific_natural_language_not_needed() -> None:
    input_fn = Mock(side_effect=AssertionError("no prompt"))
    output_fn = Mock()

    result = clarify_repl_request(
        "list files in /tmp sorted by size", input_fn=input_fn, output_fn=output_fn
    )

    assert result.status == ClarificationStatus.NOT_NEEDED
    input_fn.assert_not_called()
    output_fn.assert_not_called()


def test_clarify_repl_request_known_ambiguity_prompts_once() -> None:
    input_fn = Mock(return_value="list large files in ~/Downloads")
    output_fn = Mock()

    result = clarify_repl_request("clean this folder", input_fn=input_fn, output_fn=output_fn)

    assert result.status == ClarificationStatus.CLARIFIED
    assert result.clarified_request == "list large files in ~/Downloads"
    input_fn.assert_called_once_with("clarify> ")
    output_fn.assert_called_once()
    assert "Safer inspection ideas:" in output_fn.call_args.args[0]


def test_clarify_repl_request_blank_and_cancel_are_cancelled() -> None:
    for answer in ("", "cancel"):
        result = clarify_repl_request(
            "clean this folder", input_fn=Mock(return_value=answer), output_fn=Mock()
        )
        assert result.status == ClarificationStatus.CANCELLED


def test_clarify_repl_request_ambiguous_answer_unresolved() -> None:
    output_fn = Mock()

    result = clarify_repl_request(
        "clean this folder", input_fn=Mock(return_value="fix this"), output_fn=output_fn
    )

    assert result.status == ClarificationStatus.UNRESOLVED
    assert result.clarified_request is None
    assert output_fn.call_count == 2
    assert "still ambiguous" in output_fn.call_args.args[0]


def test_clarify_repl_request_specific_direct_answer_clarified() -> None:
    result = clarify_repl_request(
        "clean this folder", input_fn=Mock(return_value="ls -la ~/Downloads"), output_fn=Mock()
    )

    assert result.status == ClarificationStatus.CLARIFIED
    assert result.clarified_request == "ls -la ~/Downloads"


def test_clarify_repl_request_interruption_is_cancelled() -> None:
    result = clarify_repl_request(
        "clean this folder", input_fn=Mock(side_effect=KeyboardInterrupt), output_fn=Mock()
    )

    assert result.status == ClarificationStatus.CANCELLED


def test_clarify_repl_request_never_calls_planner() -> None:
    planner = Mock()

    result = clarify_repl_request(
        "clean this folder",
        input_fn=Mock(return_value="list large files in /tmp"),
        output_fn=Mock(),
    )

    assert result.status == ClarificationStatus.CLARIFIED
    planner.plan.assert_not_called()

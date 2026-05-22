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


def test_detect_ambiguity_scoped_restore_backup_not_intercepted() -> None:
    result = detect_ambiguity("restore backup.zip into ./out")

    assert result.is_ambiguous is False


def test_detect_ambiguity_guarded_archive_cli_destination_flags_not_intercepted() -> None:
    assert detect_ambiguity("please extract archive.tar -C out").is_ambiguous is False
    assert detect_ambiguity("please unzip archive.zip -d restore").is_ambiguous is False

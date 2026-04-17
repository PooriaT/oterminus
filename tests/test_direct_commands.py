from oterminus.direct_commands import detect_direct_command


def test_detect_direct_command_for_cd() -> None:
    proposal = detect_direct_command("cd src")

    assert proposal is not None
    assert proposal.command == "cd src"


def test_detect_direct_command_rejects_natural_language_find() -> None:
    proposal = detect_direct_command("find all .py files")

    assert proposal is None


def test_detect_direct_command_preserves_registry_notes() -> None:
    proposal = detect_direct_command("cd src")

    assert proposal is not None
    assert any("working directory" in note for note in proposal.notes)

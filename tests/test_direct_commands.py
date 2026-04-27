import oterminus.direct_commands as direct_commands
from oterminus.direct_commands import detect_direct_command
from oterminus.models import ProposalMode
from oterminus.structured_commands import StructuredCommandError


def test_detect_direct_command_for_cd() -> None:
    proposal = detect_direct_command("cd src")

    assert proposal is not None
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command_family == "cd"
    assert proposal.command == "cd src"


def test_detect_direct_command_rejects_natural_language_find() -> None:
    proposal = detect_direct_command("find all .py files")

    assert proposal is None


def test_detect_direct_command_for_new_curated_family() -> None:
    proposal = detect_direct_command("open .")

    assert proposal is not None
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "open"
    assert proposal.command == "open ."


def test_detect_direct_command_for_process_family() -> None:
    proposal = detect_direct_command("ps -Af")

    assert proposal is not None
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "ps"


def test_detect_direct_command_preserves_registry_notes() -> None:
    proposal = detect_direct_command("cd src")

    assert proposal is not None
    assert any("working directory" in note for note in proposal.notes)


def test_detect_direct_command_falls_back_when_structured_parse_errors(monkeypatch) -> None:
    def _raise(_: str) -> None:
        raise StructuredCommandError("boom")

    monkeypatch.setattr(direct_commands, "parse_raw_command_as_structured", _raise)

    proposal = detect_direct_command("open .")

    assert proposal is not None
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "open ."
    assert any("Structured parsing skipped: boom" in note for note in proposal.notes)

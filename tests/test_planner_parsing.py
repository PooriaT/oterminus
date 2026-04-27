import pytest

from oterminus.models import ActionType, Proposal, ProposalMode
from oterminus.planner import Planner, PlannerError


def test_parse_supported_command_ls_proposal_is_normalized_to_structured() -> None:
    raw = (
        '{"action_type":"shell_command","command":"ls -lh",'
        '"summary":"list files with sizes","explanation":"show a long listing",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.action_type == ActionType.SHELL_COMMAND
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command is None
    assert proposal.command_family == "ls"
    assert proposal.arguments == {
        "path": ".",
        "long": True,
        "human_readable": True,
        "all": False,
        "recursive": False,
    }


@pytest.mark.parametrize(
    ("command", "expected_family", "expected_arguments"),
    [
        (
            "cat README.md",
            "cat",
            {"paths": ["README.md"]},
        ),
        (
            "du -sh .",
            "du",
            {"path": ".", "human_readable": True, "summarize": True, "max_depth": None},
        ),
        (
            "open -R .",
            "open",
            {"path": ".", "reveal": True},
        ),
        ("whoami", "whoami", {}),
        ("df -h .", "df", {"path": ".", "human_readable": True}),
        ("df", "df", {"path": None, "human_readable": False}),
        ("ps -Af", "ps", {"all_processes": True, "full_format": True, "user": None, "pid": None}),
    ],
)
def test_parse_supported_command_proposal_is_normalized_to_structured(
    command: str, expected_family: str, expected_arguments: dict[str, object]
) -> None:
    raw = (
        f'{{"action_type":"shell_command","command":"{command}",'
        '"summary":"normalized","explanation":"prefer structured rendering",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )

    proposal = Planner.parse_proposal(raw)

    assert proposal.action_type == ActionType.SHELL_COMMAND
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command is None
    assert proposal.command_family == expected_family
    assert proposal.arguments == expected_arguments


def test_parse_valid_experimental_fallback_for_unstructured_variant() -> None:
    raw = (
        '{"action_type":"shell_command","command":"stat -f %z README.md",'
        '"summary":"show file size","explanation":"custom stat format",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.action_type == ActionType.SHELL_COMMAND
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "stat -f %z README.md"
    assert proposal.command_family is None


def test_parse_legacy_raw_mode_is_normalized_to_experimental_with_note() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"raw","command":"stat -f %z README.md",'
        '"summary":"show file size","explanation":"legacy compatibility payload",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "stat -f %z README.md"
    assert any("Legacy raw mode was normalized to experimental mode." in note for note in proposal.notes)


def test_parse_legacy_raw_mode_with_unparseable_structured_command_returns_planner_error() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"raw","command_family":"ls","command":"ls -h",'
        '"summary":"list files","explanation":"legacy payload with raw command",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_validate_legacy_raw_mode_with_command_family_and_command_stays_experimental() -> None:
    proposal = Proposal.model_validate(
        {
            "action_type": "shell_command",
            "mode": "raw",
            "command_family": "ls",
            "command": "ls -lh",
            "summary": "list files",
            "explanation": "legacy payload with family metadata only",
            "risk_level": "safe",
            "needs_confirmation": True,
            "notes": [],
        }
    )
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "ls -lh"
    assert proposal.command_family == "ls"


def test_validate_missing_mode_with_command_family_and_command_stays_experimental() -> None:
    proposal = Proposal.model_validate(
        {
            "action_type": "shell_command",
            "command_family": "ls",
            "command": "ls -lh",
            "summary": "list files",
            "explanation": "mode omitted legacy payload",
            "risk_level": "safe",
            "needs_confirmation": True,
            "notes": [],
        }
    )
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "ls -lh"
    assert proposal.command_family == "ls"


def test_parse_structured_proposal_without_raw_command() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","command_family":"find",'
        '"arguments":{"path":".","name":"*.py"},"summary":"find python files",'
        '"explanation":"structured search plan","risk_level":"safe",'
        '"needs_confirmation":true,"notes":["future-ready"]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command is None
    assert proposal.command_family == "find"
    assert proposal.arguments == {"path": ".", "name": "*.py"}


def test_parse_structured_proposal_with_legacy_raw_command_keeps_structured_authority() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","command_family":"find",'
        '"arguments":{"path":".","name":"*.py"},"command":"find src -name \'*.py\'",'
        '"summary":"find python files","explanation":"structured search plan","risk_level":"safe",'
        '"needs_confirmation":true,"notes":["legacy command retained for compatibility"]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command == "find src -name '*.py'"
    assert proposal.command_family == "find"
    assert proposal.arguments == {"path": ".", "name": "*.py"}


def test_parse_legacy_raw_mode_with_supported_structured_fields_is_normalized() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"raw","command_family":"cp",'
        '"arguments":{"source":"src.txt","destination":"dest.txt","recursive":false,"preserve":true,"no_clobber":true},'
        '"command":"cp -p -n src.txt dest.txt",'
        '"summary":"copy file carefully","explanation":"use deterministic copy rendering",'
        '"risk_level":"write","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command == "cp -p -n src.txt dest.txt"
    assert proposal.command_family == "cp"
    assert proposal.arguments == {
        "source": "src.txt",
        "destination": "dest.txt",
        "recursive": False,
        "preserve": True,
        "no_clobber": True,
    }


def test_parse_symbolic_chmod_stays_experimental_when_structured_not_feasible() -> None:
    raw = (
        '{"action_type":"shell_command","command":"chmod u+x run.sh",'
        '"summary":"make script executable","explanation":"symbolic chmod",'
        '"risk_level":"write","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "chmod u+x run.sh"


def test_parse_explicit_experimental_proposal_is_preserved() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"experimental","command_family":"stat",'
        '"command":"stat -f %z README.md","summary":"show size",'
        '"explanation":"experimental raw fallback","risk_level":"safe",'
        '"needs_confirmation":true,"notes":["experimental"]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "stat -f %z README.md"
    assert proposal.command_family == "stat"


def test_parse_rejects_arguments_without_command_family() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","arguments":{"path":"src"},'
        '"summary":"bad structured proposal","explanation":"missing family",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_rejects_structured_without_arguments() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","command_family":"find",'
        '"summary":"bad structured proposal","explanation":"missing args",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_rejects_unsupported_structured_family() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","command_family":"python",'
        '"arguments":{"script":"app.py"},"summary":"run python",'
        '"explanation":"bad structured family","risk_level":"safe",'
        '"needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_rejects_malformed_structured_arguments() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","command_family":"open",'
        '"arguments":{"path":"https://example.com","reveal":false},"summary":"open url",'
        '"explanation":"bad target","risk_level":"safe",'
        '"needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_rejects_invalid_structured_arguments_even_in_legacy_raw_mode() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"raw","command_family":"du",'
        '"arguments":{"path":".","human_readable":false,"summarize":true,"max_depth":1},"command":"du -s -d 1 .",'
        '"summary":"bad du payload","explanation":"conflicting structured payload",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_rejects_structured_arguments_in_experimental_mode() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"experimental","command_family":"cat",'
        '"arguments":{"paths":["README.md"]},"command":"cat README.md",'
        '"summary":"readme","explanation":"bad experimental payload",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_invalid_json() -> None:
    with pytest.raises(PlannerError):
        Planner.parse_proposal("not-json")

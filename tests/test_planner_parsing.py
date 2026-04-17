import pytest

from oterminus.models import ActionType, ProposalMode
from oterminus.planner import Planner, PlannerError


def test_parse_supported_raw_ls_proposal_is_normalized_to_structured() -> None:
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


def test_parse_valid_raw_fallback_for_unsupported_structured_family() -> None:
    raw = (
        '{"action_type":"shell_command","command":"cat README.md",'
        '"summary":"show the readme","explanation":"display the file contents",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.action_type == ActionType.SHELL_COMMAND
    assert proposal.mode == ProposalMode.RAW
    assert proposal.command == "cat README.md"
    assert proposal.command_family is None


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


def test_parse_raw_mode_with_supported_structured_fields_is_normalized() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"raw","command_family":"chmod",'
        '"arguments":{"path":"run.sh","mode":"755"},"command":"chmod 755 run.sh",'
        '"summary":"make script executable","explanation":"use numeric chmod",'
        '"risk_level":"write","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command is None
    assert proposal.command_family == "chmod"
    assert proposal.arguments == {"path": "run.sh", "mode": "755"}


def test_parse_symbolic_chmod_stays_raw_when_structured_not_feasible() -> None:
    raw = (
        '{"action_type":"shell_command","command":"chmod u+x run.sh",'
        '"summary":"make script executable","explanation":"symbolic chmod",'
        '"risk_level":"write","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.RAW
    assert proposal.command == "chmod u+x run.sh"


def test_parse_rejects_arguments_without_command_family() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","arguments":{"path":"src"},'
        '"summary":"bad structured proposal","explanation":"missing family",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_rejects_unsupported_structured_family() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","command_family":"cat",'
        '"arguments":{"path":"README.md"},"summary":"readme",'
        '"explanation":"bad structured family","risk_level":"safe",'
        '"needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_rejects_malformed_structured_arguments() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","command_family":"chmod",'
        '"arguments":{"path":"run.sh","mode":"u+x"},"summary":"chmod",'
        '"explanation":"bad mode","risk_level":"write",'
        '"needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_rejects_invalid_structured_arguments_even_in_raw_mode() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"raw","command_family":"chmod",'
        '"arguments":{"path":"run.sh","mode":"u+x"},"command":"chmod u+x run.sh",'
        '"summary":"chmod","explanation":"bad structured payload",'
        '"risk_level":"write","needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_invalid_json() -> None:
    with pytest.raises(PlannerError):
        Planner.parse_proposal("not-json")

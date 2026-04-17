import pytest

from oterminus.models import ActionType, ProposalMode
from oterminus.planner import Planner, PlannerError


def test_parse_valid_legacy_raw_proposal() -> None:
    raw = (
        '{"action_type":"shell_command","command":"find . -name \\"*.py\\"",'
        '"summary":"find python files","explanation":"search recursively",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.action_type == ActionType.SHELL_COMMAND
    assert proposal.mode == ProposalMode.RAW
    assert proposal.command.startswith("find")


def test_parse_structured_proposal_without_raw_command() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","command_family":"find",'
        '"arguments":{"root":".","name":"*.py"},"summary":"find python files",'
        '"explanation":"structured search plan","risk_level":"safe",'
        '"needs_confirmation":true,"notes":["future-ready"]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command is None
    assert proposal.command_family == "find"
    assert proposal.arguments == {"root": ".", "name": "*.py"}


def test_parse_rejects_arguments_without_command_family() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"structured","arguments":{"path":"src"},'
        '"summary":"bad structured proposal","explanation":"missing family",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


def test_parse_invalid_json() -> None:
    with pytest.raises(PlannerError):
        Planner.parse_proposal("not-json")

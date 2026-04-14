import pytest

from oterminus.models import ActionType
from oterminus.planner import Planner, PlannerError


def test_parse_valid_proposal() -> None:
    raw = (
        '{"action_type":"shell_command","command":"find . -name \"*.py\"",'
        '"summary":"find python files","explanation":"search recursively",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    proposal = Planner.parse_proposal(raw)
    assert proposal.action_type == ActionType.SHELL_COMMAND
    assert proposal.command.startswith("find")


def test_parse_invalid_json() -> None:
    with pytest.raises(PlannerError):
        Planner.parse_proposal("not-json")

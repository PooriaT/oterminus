import json

import pytest

from oterminus.models import ActionType, Proposal, ProposalMode
from oterminus.planner import Planner, PlannerError


class _StubClient:
    def __init__(self, *payloads: str):
        self.payloads = list(payloads)
        self.calls: list[dict[str, object]] = []

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "output_schema": output_schema,
            }
        )
        return self.payloads.pop(0)


def _proposal_payload(**overrides: object) -> str:
    payload = {
        "action_type": "shell_command",
        "mode": "structured",
        "command_family": "man",
        "arguments": {"topic": "ls", "section": None},
        "summary": "show manual",
        "explanation": "Use the local manual page for ls.",
        "risk_level": "safe",
        "needs_confirmation": True,
        "notes": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_proposal_mode_exposes_only_structured_and_experimental() -> None:
    assert {mode.value for mode in ProposalMode} == {"structured", "experimental"}


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
    assert any(
        "Legacy raw mode was normalized to experimental mode." in note for note in proposal.notes
    )


def test_parse_legacy_raw_mode_with_unparseable_structured_command_returns_planner_error() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"raw","command_family":"ls","command":"ls -h",'
        '"summary":"list files","explanation":"legacy payload with command text",'
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


def test_parse_structured_proposal_without_command_text() -> None:
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


def test_parse_structured_proposal_with_legacy_command_text_keeps_structured_authority() -> None:
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


def test_parse_legacy_raw_mode_with_structured_arguments_is_rejected() -> None:
    raw = (
        '{"action_type":"shell_command","mode":"raw","command_family":"cp",'
        '"arguments":{"source":"src.txt","destination":"dest.txt","recursive":false,"preserve":true,"no_clobber":true},'
        '"command":"cp -p -n src.txt dest.txt",'
        '"summary":"copy file carefully","explanation":"legacy mode with structured arguments",'
        '"risk_level":"write","needs_confirmation":true,"notes":[]}'
    )

    with pytest.raises(PlannerError):
        Planner.parse_proposal(raw)


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
        '"explanation":"experimental fallback","risk_level":"safe",'
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


def test_planner_first_call_valid_structured_proposal_passes() -> None:
    client = _StubClient(_proposal_payload())
    planner = Planner(client)

    proposal = planner.plan("show me the manual of ls")

    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "man"
    assert proposal.arguments == {"topic": "ls", "section": None}
    assert len(client.calls) == 1
    assert client.calls[0]["output_schema"] is not None


def test_planner_first_call_valid_experimental_proposal_passes() -> None:
    client = _StubClient(
        _proposal_payload(
            mode="experimental",
            command_family=None,
            arguments=None,
            command="stat -f %z README.md",
            summary="show exact file size",
            explanation="Use a single stat command with a custom format.",
            notes=["Experimental proposal; review before running."],
        )
    )
    planner = Planner(client)

    proposal = planner.plan("show README size in bytes exactly")

    assert proposal.mode == ProposalMode.EXPERIMENTAL
    assert proposal.command == "stat -f %z README.md"
    assert len(client.calls) == 1


def test_planner_repairs_invalid_action_type_and_mode_once() -> None:
    invalid = _proposal_payload(
        action_type="cat",
        mode="file",
        command_family=None,
        arguments=None,
        command="cat README.md",
    )
    repaired = _proposal_payload()
    client = _StubClient(invalid, repaired)
    planner = Planner(client)

    proposal = planner.plan("show me the manual of ls")

    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "man"
    assert proposal.arguments == {"topic": "ls", "section": None}
    assert len(client.calls) == 2
    repair_prompt = str(client.calls[1]["user_prompt"])
    assert "Original user request:" in repair_prompt
    assert "Original planner context:" in repair_prompt
    assert "show me the manual of ls" in repair_prompt
    assert "suggested_families=man" in repair_prompt
    assert "Invalid JSON returned:" in repair_prompt
    assert "field `action_type`" in repair_prompt
    assert '"shell_command"' in repair_prompt
    assert '"structured" or "experimental"' in repair_prompt
    assert "Every corrected object must include" in repair_prompt
    assert "Valid structured shape:" in repair_prompt


def test_planner_repairs_structured_proposal_missing_command_family() -> None:
    invalid = json.dumps(
        {
            "action_type": "shell_command",
            "mode": "structured",
            "summary": "Display manual of ls command",
            "explanation": "Using cat to show the manual page for ls utility.",
            "needs_confirmation": False,
            "notes": ["No alternative command fits better."],
        }
    )
    repaired = _proposal_payload()
    client = _StubClient(invalid, repaired)
    planner = Planner(client)

    proposal = planner.plan("show me the manual of ls")

    assert proposal.mode == ProposalMode.STRUCTURED
    assert proposal.command_family == "man"
    assert proposal.arguments == {"topic": "ls", "section": None}
    assert len(client.calls) == 2
    repair_prompt = str(client.calls[1]["user_prompt"])
    assert "Structured proposals require command_family" in repair_prompt
    assert "Valid structured shape:" in repair_prompt
    assert "needs_confirmation to true" in repair_prompt


def test_planner_repairs_false_needs_confirmation() -> None:
    invalid = _proposal_payload(needs_confirmation=False)
    repaired = _proposal_payload()
    client = _StubClient(invalid, repaired)
    planner = Planner(client)

    proposal = planner.plan("show me the manual of ls")

    assert proposal.needs_confirmation is True
    assert len(client.calls) == 2
    repair_prompt = str(client.calls[1]["user_prompt"])
    assert "field `needs_confirmation`" in repair_prompt
    assert "needs_confirmation to true" in repair_prompt


def test_planner_repair_failure_raises_concise_error() -> None:
    invalid = _proposal_payload(
        action_type="cat",
        mode="file",
        command_family=None,
        arguments=None,
        command="cat README.md",
    )
    client = _StubClient(invalid, invalid)
    planner = Planner(client)

    with pytest.raises(PlannerError) as exc_info:
        planner.plan("show me the manual of ls")

    message = str(exc_info.value)
    assert "after one repair attempt" in message
    assert "Details:" in message
    assert "field `action_type`" in message
    assert len(client.calls) == 2


def test_planner_malformed_json_fails_without_repair() -> None:
    client = _StubClient("not-json")
    planner = Planner(client)

    with pytest.raises(PlannerError, match="Invalid JSON from model"):
        planner.plan("show me the manual of ls")

    assert len(client.calls) == 1

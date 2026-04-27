from oterminus.planner import Planner
from oterminus.prompts import build_system_prompt


class _StubClient:
    def __init__(self, payload: str):
        self.payload = payload
        self.calls: list[dict[str, str]] = []

    def chat_json(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.payload


def test_planner_includes_router_context_in_prompt() -> None:
    client = _StubClient(
        '{"action_type":"shell_command","mode":"structured","command_family":"grep",'
        '"arguments":{"pattern":"TODO","paths":["src"],"ignore_case":false,"line_number":false,'
        '"fixed_strings":false,"recursive":false,"files_with_matches":false,"max_count":null},'
        '"summary":"search TODO","explanation":"text search","risk_level":"safe",'
        '"needs_confirmation":true,"notes":[]}'
    )
    planner = Planner(client)

    planner.plan("find lines containing TODO in src")

    prompt = client.calls[0]["user_prompt"]
    assert "Capability route:" in prompt
    assert "category=text_search" in prompt
    assert "suggested_families=find" in prompt
    assert "suggested_capabilities=text_inspection, filesystem_inspection" in prompt


def test_planner_includes_unsupported_router_context() -> None:
    client = _StubClient(
        '{"action_type":"shell_command","mode":"experimental","command":"pwd",'
        '"summary":"fallback","explanation":"unsupported request fallback",'
        '"risk_level":"safe","needs_confirmation":true,"notes":["experimental"]}'
    )
    planner = Planner(client)

    planner.plan("tell me a joke")

    prompt = client.calls[0]["user_prompt"]
    assert "category=unsupported" in prompt
    assert "limitations" in prompt


def test_planner_system_prompt_includes_supported_capabilities() -> None:
    prompt = build_system_prompt()

    assert "filesystem_inspection" in prompt
    assert "process_inspection" in prompt
    assert "commands:" in prompt

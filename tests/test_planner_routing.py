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
    assert "project_health" in prompt
    assert "may execute local project code and tooling" in prompt
    assert "Do not propose arbitrary `poetry run ...`" in prompt


def test_planner_system_prompt_env_shape_requires_variable_operand() -> None:
    prompt = build_system_prompt()

    assert '- `env`: `{"variable": "PATH"}`' in prompt


def test_planner_system_prompt_filters_platform_unsupported_commands() -> None:
    prompt = build_system_prompt(platform_id="linux")
    assert "`open`" not in prompt
    assert "macos_desktop" not in prompt


def test_planner_system_prompt_includes_git_inspection_when_enabled() -> None:
    prompt = build_system_prompt()

    assert "git_inspection" in prompt
    assert "status_short|branch_current|log_oneline|diff_stat|diff_name_only" in prompt


def test_planner_system_prompt_includes_archive_inspection_when_enabled() -> None:
    prompt = build_system_prompt()

    assert "archive_inspection" in prompt
    assert '"operation": "list|extract_tar|create_tar_gz"' in prompt
    assert '"operation": "list|extract_zip"' in prompt
    assert '"operation": "create_zip"' in prompt
    assert "explicit destination" in prompt
    assert "explicit output archive path and explicit source paths" in prompt


def test_planner_system_prompt_includes_network_diagnostics_when_enabled() -> None:
    prompt = build_system_prompt()

    assert "network_diagnostics" in prompt
    assert '"host": "example.com", "count": 4' in prompt
    assert '"operation": "http_head", "url": "https://example.com"' in prompt
    assert "Network diagnostics contact external hosts" in prompt
    assert "POST/PUT/PATCH/DELETE" in prompt
    assert "authorization" in prompt


def test_planner_system_prompt_excludes_archive_inspection_when_disabled() -> None:
    prompt = build_system_prompt(disabled_pack_ids=frozenset({"archive"}))

    assert "archive_inspection" not in prompt
    assert "`tar`" not in prompt
    assert "`unzip`" not in prompt
    assert "`zip`" not in prompt


def test_planner_system_prompt_excludes_git_inspection_when_disabled() -> None:
    prompt = build_system_prompt(disabled_pack_ids=frozenset({"git"}))

    assert "git_inspection" not in prompt
    assert "`git`" not in prompt


def test_planner_system_prompt_excludes_network_diagnostics_when_disabled() -> None:
    prompt = build_system_prompt(disabled_pack_ids=frozenset({"network"}))

    assert "network_diagnostics" not in prompt
    assert "`ping`" not in prompt
    assert "`curl`" not in prompt


def test_planner_system_prompt_excludes_project_health_when_project_pack_disabled() -> None:
    prompt = build_system_prompt(disabled_pack_ids=frozenset({"project"}))
    assert "project_health" not in prompt
    assert "run_tests|lint_check|format_check|build_docs|run_evals" not in prompt

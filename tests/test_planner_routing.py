from oterminus.planner import Planner
from oterminus.policies import PolicyConfig
from oterminus.prompts import build_system_prompt


class _StubClient:
    def __init__(self, payload: str):
        self.payload = payload
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


def test_planner_routes_manual_page_requests_to_man() -> None:
    client = _StubClient(
        '{"action_type":"shell_command","mode":"structured","command_family":"man",'
        '"arguments":{"topic":"ls","section":null},"command":null,'
        '"summary":"show manual","explanation":"display the ls manual page",'
        '"risk_level":"safe","needs_confirmation":true,"notes":[]}'
    )
    planner = Planner(client)

    planner.plan("provide the manual page for ls")

    prompt = client.calls[0]["user_prompt"]
    assert "category=metadata_inspect" in prompt
    assert "suggested_families=man" in prompt
    assert "suggested_capabilities=system_inspection" in prompt


def test_planner_route_context_excludes_disabled_profile_capabilities() -> None:
    client = _StubClient(
        '{"action_type":"shell_command","mode":"experimental","command":"pwd",'
        '"summary":"fallback","explanation":"unsupported request fallback",'
        '"risk_level":"safe","needs_confirmation":true,"notes":["experimental"]}'
    )
    planner = Planner(
        client, policy=PolicyConfig(disabled_command_packs=frozenset({"dangerous", "network"}))
    )

    planner.plan("ping example.com 4 times")

    prompt = client.calls[0]["user_prompt"]
    assert "category=unsupported" in prompt
    assert "network_diagnostics" not in prompt
    assert "suggested_families=none" in prompt


def test_planner_system_prompt_includes_supported_capabilities() -> None:
    prompt = build_system_prompt()

    assert "filesystem_inspection" in prompt
    assert "process_inspection" in prompt
    assert "commands:" in prompt
    assert "project_health" in prompt
    assert "run_tests|lint_check|format_check|build_docs|run_evals" in prompt
    assert "may execute local project code" in prompt
    assert "arbitrary `poetry run ...`" in prompt
    assert "write-formatting" in prompt
    assert "deploy/publish" in prompt


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


def test_planner_route_context_includes_project_health_when_enabled() -> None:
    client = _StubClient(
        '{"action_type":"shell_command","mode":"structured","command_family":"project_health",'
        '"arguments":{"operation":"run_tests"},'
        '"summary":"run tests","explanation":"curated project health",'
        '"risk_level":"write","needs_confirmation":true,"notes":[]}'
    )
    planner = Planner(client)

    planner.plan("run the test suite")

    prompt = client.calls[0]["user_prompt"]
    assert "category=project_health" in prompt
    assert "project_health" in prompt
    assert "suggested_families=project_health" in prompt


def test_planner_route_context_excludes_project_health_when_disabled() -> None:
    client = _StubClient(
        '{"action_type":"shell_command","mode":"experimental","command":"pwd",'
        '"summary":"fallback","explanation":"unsupported request fallback",'
        '"risk_level":"safe","needs_confirmation":true,"notes":["experimental"]}'
    )
    planner = Planner(client, policy=PolicyConfig(disabled_command_packs=frozenset({"project"})))

    planner.plan("run the test suite")

    prompt = client.calls[0]["user_prompt"]
    assert "category=unsupported" in prompt
    assert "project_health" not in prompt
    assert "suggested_families=none" in prompt


def test_planner_system_prompt_respects_beginner_profile_disabled_packs() -> None:
    disabled = frozenset({"archive", "dangerous", "git", "macos", "network", "process", "project"})

    prompt = build_system_prompt(disabled_pack_ids=disabled, platform_id="darwin")

    assert "archive_inspection" not in prompt
    assert "git_inspection" not in prompt
    assert "network_diagnostics" not in prompt
    assert "process_inspection" not in prompt
    assert "project_health" not in prompt
    assert "macos_desktop" not in prompt
    assert "`git`" not in prompt
    assert "`ping`" not in prompt
    assert "`ps`" not in prompt

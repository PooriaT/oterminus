from oterminus.local_planner import plan_locally
from oterminus.router import route_request


def test_local_planner_maps_current_directory() -> None:
    match = plan_locally("show current directory", route_request("show current directory"))
    assert match is not None
    assert match.proposal.command_family == "pwd"


def test_local_planner_maps_files_with_sizes() -> None:
    match = plan_locally("list files with sizes", route_request("list files with sizes"))
    assert match is not None
    assert match.proposal.command_family == "ls"
    assert match.proposal.arguments == {
        "path": ".",
        "long": True,
        "human_readable": True,
        "all": False,
        "recursive": False,
    }


def test_local_planner_maps_disk_usage_folder() -> None:
    match = plan_locally(
        "show disk usage for this folder", route_request("show disk usage for this folder")
    )
    assert match is not None
    assert match.proposal.command_family == "du"


def test_local_planner_respects_disabled_git_pack() -> None:
    match = plan_locally(
        "show git status",
        route_request("show git status"),
        disabled_pack_ids=frozenset({"git"}),
    )
    assert match is None


def test_local_planner_respects_beginner_profile_disabled_packs() -> None:
    disabled = frozenset({"archive", "dangerous", "git", "macos", "network", "process", "project"})

    match = plan_locally(
        "show git status",
        route_request("show git status", disabled_pack_ids=disabled),
        disabled_pack_ids=disabled,
    )

    assert match is None


def test_local_planner_maps_project_health_requests() -> None:
    cases = {
        "run tests": "run_tests",
        "run the test suite": "run_tests",
        "check linting": "lint_check",
        "run ruff check": "lint_check",
        "check formatting": "format_check",
        "run format check": "format_check",
        "build docs": "build_docs",
        "check docs build": "build_docs",
        "run evals": "run_evals",
    }

    for request, operation in cases.items():
        match = plan_locally(request, route_request(request))
        assert match is not None, request
        assert match.proposal.command_family == "project_health"
        assert match.proposal.arguments == {"operation": operation}
        assert match.proposal.needs_confirmation is True


def test_local_planner_respects_disabled_project_pack() -> None:
    disabled = frozenset({"project"})
    match = plan_locally(
        "run tests",
        route_request("run tests", disabled_pack_ids=disabled),
        disabled_pack_ids=disabled,
    )

    assert match is None


def test_local_planner_unsafe_requests_fall_back() -> None:
    assert plan_locally("delete junk", route_request("delete junk")) is None
    assert plan_locally("install dependencies", route_request("install dependencies")) is None
    assert plan_locally("format the code", route_request("format the code")) is None

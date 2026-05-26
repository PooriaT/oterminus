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


def test_local_planner_unsafe_requests_fall_back() -> None:
    assert plan_locally("delete junk", route_request("delete junk")) is None
    assert plan_locally("install dependencies", route_request("install dependencies")) is None

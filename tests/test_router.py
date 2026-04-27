from oterminus.router import route_request
from oterminus.commands import get_commands_by_capability


def test_route_request_common_buckets() -> None:
    assert route_request("find lines containing TODO in src").category == "text_search"
    assert route_request("create a new folder called logs").category == "filesystem_mutate"
    assert route_request("show file size for README.md").category == "metadata_inspect"
    assert route_request("list all files in this directory").category == "filesystem_inspect"
    assert route_request("show running python processes").category == "process_inspect"
    assert route_request("show disk space").category == "metadata_inspect"


def test_route_request_ambiguous_prefers_safe_inspection() -> None:
    route = route_request("show project files")

    assert route.category == "filesystem_inspect"
    assert route.confidence > 0.7
    assert route.suggested_families
    assert "find" in route.suggested_families


def test_route_request_unsupported_cases() -> None:
    assert route_request("write me a poem about oceans").category == "unsupported"
    assert route_request("   ").category == "unsupported"


def test_route_request_does_not_treat_embedded_ps_as_process_hint() -> None:
    route = route_request("list apps in this directory")

    assert route.category == "filesystem_inspect"


def test_route_request_process_suggestions_include_new_families() -> None:
    route = route_request("find processes matching python")
    assert route.category == "process_inspect"
    assert "pgrep" in route.suggested_families
    assert "process_inspection" in route.suggested_capabilities


def test_route_suggestions_come_from_capability_registry() -> None:
    route = route_request("show running python processes")

    capability_families = {
        family for capability_id in route.suggested_capabilities for family in get_commands_by_capability(capability_id)
    }
    assert set(route.suggested_families).issubset(capability_families)


def test_route_fallback_uses_category_affinity_not_alphabetical_pool() -> None:
    route = route_request("pattern in files")

    assert route.category == "text_search"
    assert route.suggested_families
    assert route.suggested_families[0] in {"grep", "find"}
    assert "cat" not in route.suggested_families[:2]


def test_route_capability_expansion_excludes_dangerous_families() -> None:
    route = route_request("delete old logs")

    assert route.category == "filesystem_mutate"
    assert "chown" not in route.suggested_families

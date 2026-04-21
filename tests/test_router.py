from oterminus.router import route_request


def test_route_request_common_buckets() -> None:
    assert route_request("find lines containing TODO in src").category == "text_search"
    assert route_request("create a new folder called logs").category == "filesystem_mutate"
    assert route_request("show file size for README.md").category == "metadata_inspect"
    assert route_request("list all files in this directory").category == "filesystem_inspect"
    assert route_request("show running python processes").category == "process_inspect"


def test_route_request_ambiguous_prefers_safe_inspection() -> None:
    route = route_request("show project files")

    assert route.category == "filesystem_inspect"
    assert route.confidence > 0.7
    assert "ls" in route.suggested_families


def test_route_request_unsupported_cases() -> None:
    assert route_request("write me a poem about oceans").category == "unsupported"
    assert route_request("   ").category == "unsupported"

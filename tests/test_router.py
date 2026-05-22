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
        family
        for capability_id in route.suggested_capabilities
        for family in get_commands_by_capability(capability_id)
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


def test_route_request_git_inspection_requests() -> None:
    assert route_request("show git status").category == "git_inspection"
    assert route_request("what branch am I on").category == "git_inspection"
    assert route_request("show last 5 commits").category == "git_inspection"
    assert route_request("show files changed in git diff").category == "git_inspection"


def test_route_request_show_last_non_git_stays_filesystem_inspection() -> None:
    assert route_request("show last 10 lines of README.md").category == "filesystem_inspect"


def test_route_request_git_mutating_requests_stay_unsupported() -> None:
    assert route_request("commit my changes").category == "unsupported"
    assert route_request("push this branch").category == "unsupported"
    assert route_request("reset this repo").category == "unsupported"
    assert route_request("clean untracked files").category == "unsupported"


def test_route_request_archive_extraction_requires_destination() -> None:
    route = route_request("extract archive.tar into ./out")

    assert route.category == "archive_operations"
    assert "tar" in route.suggested_families
    assert "archive_inspection" in route.suggested_capabilities

    missing_destination = route_request("extract archive.tar")
    assert missing_destination.category == "unsupported"
    assert "explicit destination" in missing_destination.reason


def test_route_request_archive_extraction_named_backup_does_not_hit_creation_gate() -> None:
    route = route_request("unpack backup.zip to out")

    assert route.category == "archive_operations"
    assert "unzip" in route.suggested_families
    assert "archive_inspection" in route.suggested_capabilities


def test_route_request_archive_creation_requires_explicit_output_and_source() -> None:
    route = route_request("create backup.tar.gz from src")

    assert route.category == "archive_operations"
    assert "tar" in route.suggested_families
    assert "archive_inspection" in route.suggested_capabilities

    missing_scope = route_request("archive everything")
    assert missing_scope.category == "unsupported"
    assert "explicit output archive path or source path" in missing_scope.reason


def test_route_request_archive_creation_accepts_to_connector() -> None:
    route = route_request("zip docs to docs.zip")

    assert route.category == "archive_operations"
    assert "zip" in route.suggested_families


def test_route_request_network_diagnostics() -> None:
    assert route_request("ping example.com 4 times").category == "network_diagnostics"
    assert route_request("check if example.com responds").category == "network_diagnostics"
    assert (
        route_request("show HTTP headers for https://example.com").category == "network_diagnostics"
    )
    assert route_request("get DNS records for example.com").category == "network_diagnostics"
    assert route_request("look up example.com with nslookup").category == "network_diagnostics"

    route = route_request("show HTTP headers for https://example.com")
    assert "curl" in route.suggested_families
    assert "network_diagnostics" in route.suggested_capabilities


def test_route_request_check_if_stays_with_local_inspection_when_not_network_specific() -> None:
    assert route_request("check if python is running").category == "process_inspect"
    assert route_request("check if README.md contains TODO").category == "text_search"


def test_route_request_unsupported_network_requests() -> None:
    assert route_request("send a POST request").category == "unsupported"
    assert route_request("download this URL").category == "unsupported"
    assert route_request("scan this host").category == "unsupported"
    assert route_request("ssh into this server").category == "unsupported"
    assert route_request("call this API with my token").category == "unsupported"
    assert route_request("upload this file").category == "unsupported"


def test_route_request_ssh_path_mentions_stay_local() -> None:
    assert route_request("list ~/.ssh directory").category == "filesystem_inspect"
    assert route_request("ssh into this server").category == "unsupported"

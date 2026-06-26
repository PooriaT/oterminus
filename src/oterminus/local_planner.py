from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from oterminus.commands import get_enabled_command_spec
from oterminus.models import Proposal, ProposalMode
from oterminus.router import RouteResult

_UNSAFE_FRAGMENTS = (";", "&&", "||", "|", ">", "<", "$(", "`", "\x00", "\n", "\r")
_WILDCARD_FRAGMENTS = ("*", "?", "[", "]", "{", "}")
_BROAD_ROOTS = {
    "/",
    "~",
    "$HOME",
    "${HOME}",
    "/bin",
    "/dev",
    "/etc",
    "/home",
    "/lib",
    "/private",
    "/root",
    "/sbin",
    "/Users",
    "/usr",
    "/var",
}
_LOCAL_PATH_RE = re.compile(r"^[A-Za-z0-9._@%+=:,/.-]+$")
_INTEGER_RE = re.compile(r"^[1-9][0-9]*$")
_MAN_TOPIC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_MAN_SECTIONS = frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "9"})


@dataclass(frozen=True, slots=True)
class LocalPlannerMatch:
    proposal: Proposal
    rule_id: str


def plan_locally(
    request: str,
    route: RouteResult | None,
    *,
    disabled_pack_ids: frozenset[str] = frozenset(),
    platform_id: str | None = None,
) -> LocalPlannerMatch | None:
    text = _normalize_request(request)
    if not text:
        return None

    if text in {"show current directory", "where am i", "print working directory"}:
        return _build_match(
            "show_current_directory", "pwd", {}, disabled_pack_ids, platform_id=platform_id
        )

    if text in {"clear screen", "clear the screen"}:
        return _build_match("clear_screen", "clear", {}, disabled_pack_ids, platform_id=platform_id)

    if text in {"show files", "list files", "show files here"}:
        return _build_match(
            "show_files",
            "ls",
            {"path": ".", "long": False, "human_readable": False},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if text in {"show hidden files", "show all files"}:
        return _build_match(
            "show_hidden_files",
            "ls",
            {"path": ".", "long": False, "human_readable": False, "all": True},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if text in {"show detailed files", "show files with details", "list files with sizes"}:
        return _build_match(
            "show_files_detailed",
            "ls",
            {"path": ".", "long": True, "human_readable": True},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    man_match = _plan_manual_recipe(request, text, disabled_pack_ids, platform_id=platform_id)
    if man_match is not None:
        return man_match

    filesystem_match = _plan_filesystem_recipe(
        request, text, disabled_pack_ids, platform_id=platform_id
    )
    if filesystem_match is not None:
        return filesystem_match

    if (
        route
        and route.category == "metadata_inspect"
        and text
        in {
            "show disk usage",
            "show disk usage for this folder",
        }
    ):
        if text.endswith("for this folder"):
            return _build_match(
                "disk_usage_folder",
                "du",
                {"path": ".", "summarize": True, "human_readable": True},
                disabled_pack_ids,
                platform_id=platform_id,
            )
        return _build_match(
            "disk_usage",
            "df",
            {"human_readable": True},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    process_match = _plan_process_recipe(request, text, disabled_pack_ids, platform_id=platform_id)
    if process_match is not None:
        return process_match

    text_match = _plan_text_recipe(request, text, disabled_pack_ids, platform_id=platform_id)
    if text_match is not None:
        return text_match

    if (
        route
        and route.category == "git_inspection"
        and text
        in {
            "show git status",
            "show short git status",
        }
    ):
        return _build_match(
            "git_status",
            "git",
            {"operation": "status_short"},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    git_match = _plan_git_recipe(request, text, disabled_pack_ids, platform_id=platform_id)
    if git_match is not None:
        return git_match

    if route and route.category == "project_health":
        operation = _project_health_operation(text)
        if operation is not None:
            return _build_match(
                f"project_health_{operation}",
                "project_health",
                {"operation": operation},
                disabled_pack_ids,
                platform_id=platform_id,
            )

    return None


def _plan_manual_recipe(
    request: str,
    text: str,
    disabled_pack_ids: frozenset[str],
    *,
    platform_id: str | None,
) -> LocalPlannerMatch | None:
    if match := _match_request(
        request,
        r"^(?:(?:show|sho)(?: me)?|open) (?:the )?(?:manual|man page|manual page) "
        r"(?:for|of) (?:(?:a|the) command (?:called|named) )?(?P<topic>\S+)$",
    ):
        return _build_manual_match(
            "manual_page_topic",
            match.group("topic"),
            None,
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(
        request,
        r"^(?:manual page|man page) for (?P<topic>\S+)$",
    ):
        return _build_manual_match(
            "manual_page_topic",
            match.group("topic"),
            None,
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(
        request,
        r"^what is the (?:manual|man page|manual page) for (?P<topic>\S+)$",
    ):
        return _build_manual_match(
            "manual_page_topic_question",
            match.group("topic"),
            None,
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(
        request,
        r"^show (?:the )?(?:manual|man page|manual page) section (?P<section>\S+) for (?P<topic>\S+)$",
    ):
        return _build_manual_match(
            "manual_page_section_before_topic",
            match.group("topic"),
            match.group("section"),
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(
        request,
        r"^show (?:the )?(?:manual|man page|manual page) for (?P<topic>\S+) section (?P<section>\S+)$",
    ):
        return _build_manual_match(
            "manual_page_section_after_topic",
            match.group("topic"),
            match.group("section"),
            disabled_pack_ids,
            platform_id=platform_id,
        )

    return None


def _build_manual_match(
    rule_id: str,
    topic_value: str,
    section_value: str | None,
    disabled_pack_ids: frozenset[str],
    *,
    platform_id: str | None,
) -> LocalPlannerMatch | None:
    topic = _parse_manual_topic_token(topic_value)
    section = _parse_manual_section_token(section_value) if section_value is not None else None
    if topic is None or (section_value is not None and section is None):
        return None
    arguments = {"topic": topic}
    if section is not None:
        arguments["section"] = section
    return _build_match(rule_id, "man", arguments, disabled_pack_ids, platform_id=platform_id)


def _plan_filesystem_recipe(
    request: str,
    text: str,
    disabled_pack_ids: frozenset[str],
    *,
    platform_id: str | None,
) -> LocalPlannerMatch | None:
    if match := _match_request(request, r"^(?:show file info|show metadata) for (?P<path>\S+)$"):
        path = _parse_local_path_token(match.group("path"))
        if path is None:
            return None
        return _build_match(
            "show_file_info",
            "stat",
            {"path": path},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(request, r"^identify(?: file)? (?P<path>\S+)$"):
        path = _parse_local_path_token(match.group("path"))
        if path is None:
            return None
        return _build_match(
            "identify_file",
            "file",
            {"paths": [path]},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    return None


def _plan_text_recipe(
    request: str,
    text: str,
    disabled_pack_ids: frozenset[str],
    *,
    platform_id: str | None,
) -> LocalPlannerMatch | None:
    if match := _match_request(request, r"^show first (?P<count>\S+) lines of (?P<path>\S+)$"):
        count = _parse_positive_integer(match.group("count"))
        path = _parse_local_file_path_token(match.group("path"))
        if count is None or path is None:
            return None
        return _build_match(
            "show_first_lines",
            "head",
            {"paths": [path], "lines": count},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(request, r"^show last (?P<count>\S+) lines of (?P<path>\S+)$"):
        count = _parse_positive_integer(match.group("count"))
        path = _parse_local_file_path_token(match.group("path"))
        if count is None or path is None:
            return None
        return _build_match(
            "show_last_lines",
            "tail",
            {"paths": [path], "lines": count},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(request, r"^count (?P<kind>lines|words) in (?P<path>\S+)$"):
        path = _parse_local_file_path_token(match.group("path"))
        if path is None:
            return None
        kind = match.group("kind").lower()
        return _build_match(
            f"count_{kind}",
            "wc",
            {"paths": [path], kind: True},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(
        request,
        r"^(?:search|find) (?P<term>\"[^\"]+\"|'[^']+'|\S+) in (?P<path>\S+)$",
    ):
        term = _parse_search_term(match.group("term"))
        path = _parse_local_path_token(match.group("path"))
        if term is None or path is None:
            return None
        return _build_match(
            "search_fixed_text",
            "grep",
            {
                "pattern": term,
                "paths": [path],
                "fixed_strings": True,
                "recursive": _should_search_recursively(path),
                "line_number": True,
            },
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(request, r"^(?:show file|show|print) (?P<path>\S+)$"):
        path = _parse_local_file_path_token(match.group("path"))
        if path is None:
            return None
        return _build_match(
            "show_file_contents",
            "cat",
            {"paths": [path]},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    return None


def _plan_process_recipe(
    request: str,
    text: str,
    disabled_pack_ids: frozenset[str],
    *,
    platform_id: str | None,
) -> LocalPlannerMatch | None:
    if text in {"show running processes", "show all processes", "show processes"}:
        return _build_match(
            "show_running_processes",
            "ps",
            {"all_processes": True},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(
        request,
        r"^(?:find (?P<term_a>\S+) processes|find process (?P<term_b>\S+)|find processes matching (?P<term_c>\S+))$",
    ):
        term = _parse_search_term(
            match.group("term_a") or match.group("term_b") or match.group("term_c")
        )
        if term is None:
            return None
        return _build_match(
            "find_process",
            "pgrep",
            {"pattern": term, "full_command": True, "list_names": True},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    return None


def _plan_git_recipe(
    request: str,
    text: str,
    disabled_pack_ids: frozenset[str],
    *,
    platform_id: str | None,
) -> LocalPlannerMatch | None:
    if text in {"show current branch", "show current git branch", "what branch am i on"}:
        return _build_match(
            "show_current_branch",
            "git",
            {"operation": "branch_current"},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if text in {"show recent commits", "show recent git commits"}:
        return _build_match(
            "show_recent_commits",
            "git",
            {"operation": "log_oneline", "count": 10},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if match := _match_request(request, r"^show last (?P<count>\S+) commits$"):
        count = _parse_positive_integer(match.group("count"), max_value=100)
        if count is None:
            return None
        return _build_match(
            "show_last_commits",
            "git",
            {"operation": "log_oneline", "count": count},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if text == "show changed files":
        return _build_match(
            "show_changed_files",
            "git",
            {"operation": "diff_name_only"},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    if text == "show git diff summary":
        return _build_match(
            "show_git_diff_summary",
            "git",
            {"operation": "diff_stat"},
            disabled_pack_ids,
            platform_id=platform_id,
        )

    return None


def _normalize_request(request: str) -> str:
    lowered = request.strip().lower()
    return re.sub(r"\s+", " ", lowered)


def _match_request(request: str, pattern: str) -> re.Match[str] | None:
    return re.fullmatch(pattern, request.strip(), flags=re.IGNORECASE)


def _build_match(
    rule_id: str,
    command_family: str,
    arguments: dict,
    disabled_pack_ids: frozenset[str],
    *,
    platform_id: str | None = None,
) -> LocalPlannerMatch | None:
    if (
        get_enabled_command_spec(
            command_family,
            disabled_pack_ids=disabled_pack_ids,
            platform_id=platform_id,
        )
        is None
    ):
        return None
    try:
        proposal = Proposal.model_validate(
            {
                "summary": "Execute a deterministic structured command.",
                "explanation": f"Matched deterministic shortcut rule: {rule_id}.",
                "mode": ProposalMode.STRUCTURED.value,
                "command_family": command_family,
                "arguments": arguments,
                "needs_confirmation": True,
                "notes": ["Generated by deterministic shortcut."],
            }
        )
    except ValueError:
        return None
    return LocalPlannerMatch(proposal=proposal, rule_id=rule_id)


def _has_unsafe_fragment(value: str) -> bool:
    return any(fragment in value for fragment in _UNSAFE_FRAGMENTS)


def _has_wildcard_fragment(value: str) -> bool:
    return any(fragment in value for fragment in _WILDCARD_FRAGMENTS)


def _looks_like_url(value: str) -> bool:
    lowered = value.lower()
    return "://" in lowered or lowered.startswith(("mailto:", "file:"))


def _parse_local_path_token(value: str) -> str | None:
    path = _strip_simple_quotes(value.strip())
    if path is None:
        return None
    if not path or path.startswith("-"):
        return None
    if _has_unsafe_fragment(path) or _has_wildcard_fragment(path) or _looks_like_url(path):
        return None
    if any(char.isspace() for char in path):
        return None
    if path in _BROAD_ROOTS:
        return None
    if path.rstrip("/") in _BROAD_ROOTS:
        return None
    if path.startswith(("~/", "$HOME/", "${HOME}/")):
        return None
    if Path(path).is_absolute():
        return None
    if not _LOCAL_PATH_RE.fullmatch(path):
        return None
    return path


def _parse_local_file_path_token(value: str) -> str | None:
    path = _parse_local_path_token(value)
    if path is None:
        return None
    if path in {".", "./"} or Path(path).suffix == "":
        return None
    return path


def _parse_positive_integer(value: str, *, max_value: int | None = None) -> int | None:
    stripped = value.strip()
    if not _INTEGER_RE.fullmatch(stripped):
        return None
    parsed = int(stripped, 10)
    if max_value is not None and parsed > max_value:
        return None
    return parsed


def _parse_manual_topic_token(value: str) -> str | None:
    topic = _strip_simple_quotes(value.strip())
    if topic is None:
        return None
    if not topic or topic.startswith("-"):
        return None
    if _has_unsafe_fragment(topic) or _has_wildcard_fragment(topic) or _looks_like_url(topic):
        return None
    if any(char.isspace() for char in topic):
        return None
    if "/" in topic or topic in {".", "..", "~"} or topic.startswith((".", "~")):
        return None
    if not _MAN_TOPIC_RE.fullmatch(topic):
        return None
    return topic


def _parse_manual_section_token(value: str) -> str | None:
    section = value.strip()
    if section in _MAN_SECTIONS:
        return section
    return None


def _extract_single_positive_integer(text: str, *, max_value: int | None = None) -> int | None:
    numbers = re.findall(r"(?<![\w.-])\d+(?![\w.-])", text)
    if len(numbers) != 1:
        return None
    return _parse_positive_integer(numbers[0], max_value=max_value)


def _parse_search_term(value: str) -> str | None:
    term = _strip_simple_quotes(value.strip())
    if term is None:
        return None
    if not term or term.startswith("-"):
        return None
    if _has_unsafe_fragment(term) or _has_wildcard_fragment(term):
        return None
    if any(char.isspace() for char in term):
        return None
    if "'" in term or '"' in term:
        return None
    return term


def _should_search_recursively(path: str) -> bool:
    return path in {".", "./"} or Path(path).suffix == ""


def _strip_simple_quotes(value: str) -> str | None:
    if len(value) < 2:
        return value
    first = value[0]
    last = value[-1]
    if first not in {"'", '"'} and last not in {"'", '"'}:
        return value
    if first != last or first not in {"'", '"'}:
        return None
    inner = value[1:-1]
    if first in inner:
        return None
    return inner


def _project_health_operation(text: str) -> str | None:
    if text in {"run tests", "run the test suite", "run project tests"}:
        return "run_tests"
    if text in {"check linting", "run ruff check", "check ruff", "run project lint"}:
        return "lint_check"
    if text in {
        "check formatting",
        "check if formatting is okay",
        "run format check",
        "check project formatting",
    }:
        return "format_check"
    if text in {"build docs", "check docs build", "run mkdocs build", "build project docs"}:
        return "build_docs"
    if text in {"run evals", "run oterminus evals", "run project evals"}:
        return "run_evals"
    return None

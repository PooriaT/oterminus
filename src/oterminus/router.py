from __future__ import annotations

from dataclasses import dataclass
import re

from oterminus.commands import COMMAND_REGISTRY, get_commands_by_capability
from oterminus.models import RiskLevel


ROUTE_CATEGORIES = {
    "filesystem_inspect",
    "filesystem_mutate",
    "text_search",
    "metadata_inspect",
    "process_inspect",
    "git_inspection",
    "archive_operations",
    "network_diagnostics",
    "unsupported",
}


@dataclass(frozen=True, slots=True)
class RouteResult:
    category: str
    confidence: float
    reason: str
    suggested_families: tuple[str, ...] = ()
    suggested_capabilities: tuple[str, ...] = ()


def route_request(user_input: str) -> RouteResult:
    text = user_input.strip().lower()
    if not text:
        return RouteResult(
            category="unsupported",
            confidence=0.0,
            reason="Empty request.",
            suggested_families=(),
        )

    if _has_any(text, _UNSUPPORTED_NETWORK_HINTS):
        return RouteResult(
            category="unsupported",
            confidence=0.92,
            reason="Request asks for network behavior outside constrained read-only diagnostics.",
            suggested_families=(),
            suggested_capabilities=(),
        )

    if _has_any(text, _NETWORK_DIAGNOSTIC_HINTS):
        families = _families_for_category("network_diagnostics", text)
        return RouteResult(
            category="network_diagnostics",
            confidence=0.9,
            reason="Request asks for constrained read-only network diagnostics.",
            suggested_families=families,
            suggested_capabilities=_capabilities_for_category("network_diagnostics"),
        )

    if _has_any(text, _TEXT_SEARCH_HINTS):
        families = _families_for_category("text_search", text)
        return RouteResult(
            category="text_search",
            confidence=0.92,
            reason="Request includes text-match/search wording.",
            suggested_families=families,
            suggested_capabilities=_capabilities_for_category("text_search"),
        )

    if _has_any(text, _PROCESS_INSPECT_HINTS):
        families = _families_for_category("process_inspect", text)
        return RouteResult(
            category="process_inspect",
            confidence=0.87,
            reason="Request references running processes or resource usage.",
            suggested_families=families,
            suggested_capabilities=_capabilities_for_category("process_inspect"),
        )

    if _has_any(text, _METADATA_HINTS):
        families = _families_for_category("metadata_inspect", text)
        return RouteResult(
            category="metadata_inspect",
            confidence=0.9,
            reason="Request asks for file metadata or disk usage properties.",
            suggested_families=families,
            suggested_capabilities=_capabilities_for_category("metadata_inspect"),
        )

    if _has_any(text, _GIT_MUTATION_HINTS):
        return RouteResult(
            category="unsupported",
            confidence=0.9,
            reason="Request includes mutating or network Git action not supported in curated mode.",
            suggested_families=(),
            suggested_capabilities=(),
        )

    if _has_any(text, _GIT_INSPECTION_HINTS):
        families = _families_for_category("git_inspection", text)
        return RouteResult(
            category="git_inspection",
            confidence=0.93,
            reason="Request asks for read-only Git repository inspection.",
            suggested_families=families,
            suggested_capabilities=_capabilities_for_category("git_inspection"),
        )

    archive_route = _route_archive_request(text)
    if archive_route is not None:
        return archive_route

    if _has_any(text, _MUTATION_HINTS):
        families = _families_for_category("filesystem_mutate", text)
        return RouteResult(
            category="filesystem_mutate",
            confidence=0.9,
            reason="Request implies creating or changing filesystem state.",
            suggested_families=families,
            suggested_capabilities=_capabilities_for_category("filesystem_mutate"),
        )

    if _has_any(text, _INSPECTION_HINTS):
        families = _families_for_category("filesystem_inspect", text)
        return RouteResult(
            category="filesystem_inspect",
            confidence=0.84,
            reason="Request asks to view files, folders, or contents.",
            suggested_families=families,
            suggested_capabilities=_capabilities_for_category("filesystem_inspect"),
        )

    return RouteResult(
        category="unsupported",
        confidence=0.35,
        reason="No strong local terminal/filesystem intent detected.",
        suggested_families=(),
    )


def _has_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(_matches_hint(text, hint) for hint in hints)


def _matches_hint(text: str, hint: str) -> bool:
    escaped = re.escape(hint.strip())
    if not escaped:
        return False

    pattern = rf"(?<!\w){escaped}(?!\w)"
    return re.search(pattern, text) is not None


def _capabilities_for_category(category: str) -> tuple[str, ...]:
    return _ROUTE_CAPABILITIES.get(category, ())


def _families_for_category(category: str, request_text: str) -> tuple[str, ...]:
    capability_ids = _ROUTE_CAPABILITIES.get(category, ())
    if not capability_ids:
        return ()

    family_pool: tuple[str, ...] = tuple(
        sorted(
            {
                family
                for capability_id in capability_ids
                for family in get_commands_by_capability(capability_id)
                if _is_hint_eligible_family(family)
            }
        )
    )
    if not family_pool:
        return ()

    scored: list[tuple[int, str]] = []
    for family in family_pool:
        score = _family_relevance_score(family, request_text)
        if score > 0:
            scored.append((score, family))

    if scored:
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return tuple(family for _, family in scored[:6])

    fallback_scored: list[tuple[int, str]] = []
    for family in family_pool:
        affinity = _category_affinity_score(family, category)
        if affinity > 0:
            fallback_scored.append((affinity, family))
    if fallback_scored:
        fallback_scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return tuple(family for _, family in fallback_scored[:6])

    return tuple(sorted(family_pool, key=_fallback_family_priority))[:6]


def _family_relevance_score(family: str, request_text: str) -> int:
    spec = COMMAND_REGISTRY.get(family)
    if spec is None:
        return 0

    score = 0
    for hint in _family_hints(spec):
        if _matches_hint(request_text, hint):
            score += max(1, len(hint.split()))
    return score


def _family_hints(spec) -> tuple[str, ...]:
    hints = {spec.name, spec.capability_label.lower(), spec.capability_id.replace("_", " ")}
    hints.update(alias.lower() for alias in spec.natural_language_aliases)
    for example in spec.examples[:2]:
        hints.add(example.split()[0].lower())
    return tuple(sorted(hint.strip() for hint in hints if hint.strip()))


def _is_hint_eligible_family(family: str) -> bool:
    spec = COMMAND_REGISTRY.get(family)
    if spec is None:
        return False
    return spec.risk_level != RiskLevel.DANGEROUS


def _category_affinity_score(family: str, category: str) -> int:
    seeds = _ROUTE_SEED_HINTS.get(category, ())
    if not seeds:
        return 0

    spec = COMMAND_REGISTRY.get(family)
    if spec is None:
        return 0

    family_hint_text = " ".join(_family_hints(spec))
    score = 0
    for seed in seeds:
        if _matches_hint(family_hint_text, seed):
            score += max(1, len(seed.split()))
    return score


def _fallback_family_priority(family: str) -> tuple[int, int, str]:
    spec = COMMAND_REGISTRY.get(family)
    if spec is None:
        return (2, 1, family)

    risk_rank = {RiskLevel.SAFE: 0, RiskLevel.WRITE: 1, RiskLevel.DANGEROUS: 2}[spec.risk_level]
    maturity_rank = 0 if spec.maturity_level.value == "structured" else 1
    return (risk_rank, maturity_rank, family)


def _route_archive_request(text: str) -> RouteResult | None:
    if not _has_any(text, _ARCHIVE_HINTS):
        return None

    is_extraction_request = _has_any(text, _ARCHIVE_EXTRACTION_HINTS)

    if _matches_hint(text, "archive everything"):
        return RouteResult(
            category="unsupported",
            confidence=0.86,
            reason="Archive creation request is missing an explicit output archive path or source path.",
            suggested_families=(),
            suggested_capabilities=(),
        )

    if (
        not is_extraction_request
        and (_has_any(text, _ARCHIVE_CREATION_HINTS) or text.startswith(("zip ", "tar ")))
    ) and not _has_archive_creation_shape_hint(text):
        return RouteResult(
            category="unsupported",
            confidence=0.84,
            reason="Archive creation request is missing an explicit output archive path or source path.",
            suggested_families=(),
            suggested_capabilities=(),
        )

    if is_extraction_request and not _has_archive_destination_hint(text):
        return RouteResult(
            category="unsupported",
            confidence=0.9,
            reason="Archive extraction request does not include an explicit destination.",
            suggested_families=(),
            suggested_capabilities=(),
        )

    families = _families_for_archive_route(text, is_extraction_request=is_extraction_request)
    return RouteResult(
        category="archive_operations",
        confidence=0.9,
        reason="Request references a supported archive inspection or guarded extraction operation.",
        suggested_families=families,
        suggested_capabilities=_capabilities_for_category("archive_operations"),
    )


def _families_for_archive_route(text: str, *, is_extraction_request: bool) -> tuple[str, ...]:
    if is_extraction_request:
        if re.search(r"\S+\.zip(?:\s|$)", text) is not None:
            return ("unzip",)
        if re.search(r"\S+\.(?:tar|tar\.gz|tgz)(?:\s|$)", text) is not None:
            return ("tar",)
    return _families_for_category("archive_operations", text)


def _has_archive_destination_hint(text: str) -> bool:
    return (
        any(fragment in text for fragment in (" into ", " to ", " in "))
        or " -c " in text
        or " -d " in text
        or _matches_hint(text, "destination")
    )


def _has_archive_creation_shape_hint(text: str) -> bool:
    has_archive_output = re.search(r"\S+\.(?:tar\.gz|tgz|zip)(?:\s|$)", text) is not None
    has_source_connector = any(fragment in text for fragment in (" from ", " into ", " to "))
    return has_archive_output and has_source_connector


_TEXT_SEARCH_HINTS = (
    "grep",
    "search",
    "find text",
    "contains",
    "containing",
    "match",
    "matches",
    "pattern",
    "regex",
    "string",
    "line with",
    "lines with",
    "line containing",
)

_MUTATION_HINTS = (
    "create",
    "make",
    "mkdir",
    "copy",
    "cp",
    "move",
    "mv",
    "rename",
    "chmod",
    "change permissions",
    "touch",
    "delete",
    "remove",
)

_METADATA_HINTS = (
    "metadata",
    "size",
    "sizes",
    "disk usage",
    "permissions",
    "owner",
    "type of file",
    "file type",
    "stat",
    "disk space",
    "filesystem",
    "system name",
    "kernel",
    "username",
    "current user",
    "where is",
    "which",
    "environment variable",
)

_PROCESS_INSPECT_HINTS = (
    "process",
    "processes",
    "running",
    "pid",
    "cpu",
    "memory",
    "top",
    "ps",
    "pgrep",
    "lsof",
    "open files",
)

_INSPECTION_HINTS = (
    "list",
    "show",
    "display",
    "what files",
    "which files",
    "where am i",
    "current directory",
    "print working directory",
    "read",
    "view",
    "open",
    "tree",
)

_ARCHIVE_HINTS = (
    "archive",
    "tar",
    "zip",
    "unzip",
    "extract",
    "unpack",
)

_ARCHIVE_CREATION_HINTS = (
    "create",
    "compress",
    "backup",
)

_ARCHIVE_EXTRACTION_HINTS = (
    "extract",
    "unpack",
    "unzip",
    "restore",
)


_ROUTE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "text_search": ("text_inspection", "filesystem_inspection"),
    "process_inspect": ("process_inspection",),
    "metadata_inspect": ("filesystem_inspection", "system_inspection"),
    "filesystem_mutate": ("filesystem_mutation",),
    "filesystem_inspect": ("filesystem_inspection", "text_inspection", "macos_desktop"),
    "git_inspection": ("git_inspection",),
    "archive_operations": ("archive_inspection",),
    "network_diagnostics": ("network_diagnostics",),
}

_ROUTE_SEED_HINTS: dict[str, tuple[str, ...]] = {
    "text_search": ("search text", "find matching lines", "find files", "pattern"),
    "process_inspect": ("show running processes", "find process by name", "open files for process"),
    "metadata_inspect": (
        "file metadata",
        "disk usage",
        "disk space",
        "environment variable",
        "system name",
    ),
    "filesystem_mutate": ("create folder", "copy file", "move file", "change permissions"),
    "filesystem_inspect": (
        "list files",
        "show directory contents",
        "print working directory",
        "find files",
    ),
    "git_inspection": (
        "show git status",
        "show current git branch",
        "show recent git commits",
        "show git diff summary",
        "show changed file names",
    ),
    "archive_operations": (
        "list archive contents",
        "inspect archive",
        "extract archive into destination",
        "unzip archive into destination",
        "create tar gz archive",
        "create zip archive",
    ),
    "network_diagnostics": (
        "ping host",
        "check host responds",
        "show HTTP headers",
        "dns lookup",
        "nslookup",
    ),
}


_GIT_INSPECTION_HINTS = (
    "git status",
    "short git status",
    "what branch am i on",
    "current git branch",
    "recent git commits",
    "last commits",
    "show last commit",
    "show last commits",
    "last 5 commits",
    "git log",
    "git diff summary",
    "changed file names",
    "files changed in git diff",
)

_GIT_MUTATION_HINTS = (
    "git add",
    "git commit",
    "commit my changes",
    "git checkout",
    "checkout ",
    "git switch",
    "git restore",
    "git reset",
    "reset this repo",
    "reset hard",
    "git clean",
    "clean untracked files",
    "git push",
    "push this branch",
    "push my branch",
    "git pull",
    "pull latest changes",
    "git fetch",
    "git merge",
    "git rebase",
    "git stash",
)

_NETWORK_DIAGNOSTIC_HINTS = (
    "ping",
    "http headers",
    "http head",
    "head request",
    "responds",
    "dns lookup",
    "dns records",
    "dig",
    "nslookup",
)

_UNSUPPORTED_NETWORK_HINTS = (
    "post to",
    "post request",
    "put to",
    "put request",
    "patch to",
    "patch request",
    "delete to",
    "delete request",
    "request body",
    "authorization header",
    "auth header",
    "with my token",
    "with token",
    "cookie",
    "download",
    "upload",
    "scan this host",
    "scan host",
    "nmap",
    "traceroute",
    "ssh into",
    "ssh to",
    "scp",
    "netcat",
    "nc ",
    "wget",
)

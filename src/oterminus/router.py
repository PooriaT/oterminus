from __future__ import annotations

from dataclasses import dataclass
import re

from oterminus.commands import COMMAND_REGISTRY, get_commands_by_capability


ROUTE_CATEGORIES = {
    "filesystem_inspect",
    "filesystem_mutate",
    "text_search",
    "metadata_inspect",
    "process_inspect",
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
        sorted({family for capability_id in capability_ids for family in get_commands_by_capability(capability_id)})
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

    return family_pool[:6]


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


_ROUTE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "text_search": ("text_inspection", "filesystem_inspection"),
    "process_inspect": ("process_inspection",),
    "metadata_inspect": ("filesystem_inspection", "system_inspection"),
    "filesystem_mutate": ("filesystem_mutation",),
    "filesystem_inspect": ("filesystem_inspection", "text_inspection", "macos_desktop"),
}

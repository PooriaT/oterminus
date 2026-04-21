from __future__ import annotations

from dataclasses import dataclass


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
        return RouteResult(
            category="text_search",
            confidence=0.92,
            reason="Request includes text-match/search wording.",
            suggested_families=("grep", "find"),
        )

    if _has_any(text, _PROCESS_INSPECT_HINTS):
        return RouteResult(
            category="process_inspect",
            confidence=0.87,
            reason="Request references running processes or resource usage.",
            suggested_families=(),
        )

    if _has_any(text, _METADATA_HINTS):
        return RouteResult(
            category="metadata_inspect",
            confidence=0.9,
            reason="Request asks for file metadata or disk usage properties.",
            suggested_families=("stat", "du", "file"),
        )

    if _has_any(text, _MUTATION_HINTS):
        return RouteResult(
            category="filesystem_mutate",
            confidence=0.9,
            reason="Request implies creating or changing filesystem state.",
            suggested_families=("mkdir", "cp", "mv", "chmod"),
        )

    if _has_any(text, _INSPECTION_HINTS):
        return RouteResult(
            category="filesystem_inspect",
            confidence=0.84,
            reason="Request asks to view files, folders, or contents.",
            suggested_families=("ls", "pwd", "find", "cat", "head", "tail", "open"),
        )

    return RouteResult(
        category="unsupported",
        confidence=0.35,
        reason="No strong local terminal/filesystem intent detected.",
        suggested_families=(),
    )


def _has_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


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
    "cp ",
    "move",
    "mv ",
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

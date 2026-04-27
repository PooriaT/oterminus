from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from oterminus.command_registry import supported_base_commands, supported_categories

REPL_BUILTINS: tuple[str, ...] = ("help", "exit", "quit")
NL_TEMPLATES: tuple[str, ...] = (
    "find all .py files",
    "show disk usage for this folder",
    "list files with details",
)


@dataclass(frozen=True, slots=True)
class CompletionCandidate:
    text: str
    start_position: int


def _word_start_index(text: str) -> int:
    idx = len(text)
    while idx > 0 and not text[idx - 1].isspace():
        idx -= 1
    return idx


def _split_path_fragment(fragment: str) -> tuple[str, str]:
    if "/" not in fragment:
        return "", fragment
    base, _, prefix = fragment.rpartition("/")
    return f"{base}/", prefix


def _resolve_scan_dir(base_prefix: str, cwd: Path) -> Path:
    if not base_prefix:
        return cwd

    if base_prefix.startswith("~/"):
        return Path(base_prefix).expanduser()
    if base_prefix.startswith("/"):
        return Path(base_prefix)
    return (cwd / base_prefix).resolve()


def _path_candidates(fragment: str, cwd: Path) -> list[str]:
    base_prefix, name_prefix = _split_path_fragment(fragment)
    display_base = base_prefix
    scan_dir = _resolve_scan_dir(base_prefix, cwd)

    try:
        if not scan_dir.exists() or not scan_dir.is_dir():
            return []
        entries = sorted(scan_dir.iterdir(), key=lambda p: p.name)
    except OSError:
        return []

    results: list[str] = []
    for entry in entries:
        if not entry.name.startswith(name_prefix):
            continue
        try:
            suffix = "/" if entry.is_dir() else ""
        except OSError:
            suffix = ""
        results.append(f"{display_base}{entry.name}{suffix}")
    return results


def build_repl_completions(text_before_cursor: str, cwd: Path | None = None) -> list[CompletionCandidate]:
    working_dir = cwd or Path.cwd()
    word_start = _word_start_index(text_before_cursor)
    fragment = text_before_cursor[word_start:]
    tokens = text_before_cursor[:word_start].split()
    is_first_token = len(tokens) == 0

    suggestions: set[str] = set()
    if is_first_token:
        suggestions.update(REPL_BUILTINS)
        suggestions.update(supported_base_commands())
        suggestions.update(supported_categories())
        suggestions.update(NL_TEMPLATES)
    suggestions.update(_path_candidates(fragment, working_dir))

    matches = sorted(s for s in suggestions if s.startswith(fragment))
    start_position = -len(fragment)
    return [CompletionCandidate(text=match, start_position=start_position) for match in matches]


def prompt_toolkit_completer() -> object | None:
    try:
        from prompt_toolkit.completion import Completer, Completion
    except ImportError:
        return None

    class OterminusCompleter(Completer):
        def get_completions(self, document, complete_event):  # type: ignore[override]
            del complete_event
            for candidate in build_repl_completions(document.text_before_cursor):
                yield Completion(candidate.text, start_position=candidate.start_position)

    return OterminusCompleter()

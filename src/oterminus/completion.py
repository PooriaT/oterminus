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


def _path_candidates(fragment: str, cwd: Path) -> list[str]:
    expanded_fragment = Path(fragment).expanduser()
    base_dir = expanded_fragment.parent if fragment and "/" in fragment else Path(".")
    prefix = expanded_fragment.name if fragment else ""

    scan_dir = (cwd / base_dir).resolve() if not expanded_fragment.is_absolute() else base_dir
    if not scan_dir.exists() or not scan_dir.is_dir():
        return []

    display_base = "" if str(base_dir) == "." else f"{base_dir.as_posix().rstrip('/')}/"
    results: list[str] = []
    for entry in sorted(scan_dir.iterdir(), key=lambda p: p.name):
        if not entry.name.startswith(prefix):
            continue
        suffix = "/" if entry.is_dir() else ""
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

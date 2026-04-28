from __future__ import annotations

from dataclasses import dataclass
import re


_SAFE_INSPECTION_OPTIONS: tuple[str, ...] = (
    "list large files",
    "list recently modified files",
    "inspect permissions",
    "show temporary-looking files",
    "show project files",
)

_AMBIGUOUS_PHRASES: tuple[str, ...] = (
    "clean this folder",
    "fix this",
    "remove junk",
    "make everything executable",
    "delete unnecessary files",
    "organize this directory",
    "repair permissions",
    "make this project work",
)

_BROAD_MUTATION_VERBS: tuple[str, ...] = (
    "clean",
    "fix",
    "remove",
    "delete",
    "organize",
    "repair",
    "optimize",
    "make",
)

_VAGUE_OBJECT_HINTS: tuple[str, ...] = (
    "this",
    "that",
    "everything",
    "junk",
    "unnecessary",
    "folder",
    "directory",
    "project",
    "permissions",
    "files",
)


@dataclass(frozen=True, slots=True)
class AmbiguityResult:
    is_ambiguous: bool
    reason: str
    suggested_safe_options: tuple[str, ...]
    follow_up_questions: tuple[str, ...] = ()


_NOT_AMBIGUOUS = AmbiguityResult(
    is_ambiguous=False,
    reason="Request is specific enough for planning.",
    suggested_safe_options=(),
)


def detect_ambiguity(user_input: str) -> AmbiguityResult:
    text = user_input.strip().lower()
    if not text:
        return _NOT_AMBIGUOUS

    matched_phrase = _match_phrase(text)
    if matched_phrase is not None:
        return AmbiguityResult(
            is_ambiguous=True,
            reason=f"Matched ambiguous phrase: '{matched_phrase}'.",
            suggested_safe_options=_SAFE_INSPECTION_OPTIONS,
            follow_up_questions=(
                "What exact folder or file set should I inspect first?",
                "Do you want a read-only inspection report before any changes?",
            ),
        )

    if _looks_broad_destructive_request(text):
        return AmbiguityResult(
            is_ambiguous=True,
            reason="Request combines broad mutation wording with vague target scope.",
            suggested_safe_options=_SAFE_INSPECTION_OPTIONS,
            follow_up_questions=(
                "Which exact path should be targeted?",
                "What should be considered junk or unnecessary in your context?",
            ),
        )

    return _NOT_AMBIGUOUS


def _match_phrase(text: str) -> str | None:
    for phrase in _AMBIGUOUS_PHRASES:
        if _matches_hint(text, phrase):
            return phrase
    return None


def _looks_broad_destructive_request(text: str) -> bool:
    tokens = re.findall(r"[a-z0-9_./-]+", text)
    if not tokens:
        return False

    has_broad_verb = any(_matches_hint(text, verb) for verb in _BROAD_MUTATION_VERBS)
    has_vague_target = any(_matches_hint(text, hint) for hint in _VAGUE_OBJECT_HINTS)
    has_explicit_scope = any(
        token.startswith(("/", "./", "../", "~"))
        or token.endswith((".py", ".md", ".txt", ".log", ".json", ".yaml", ".yml", ".toml"))
        for token in tokens
    )
    return has_broad_verb and has_vague_target and not has_explicit_scope


def _matches_hint(text: str, hint: str) -> bool:
    escaped = re.escape(hint.strip())
    if not escaped:
        return False
    return re.search(rf"(?<!\\w){escaped}(?!\\w)", text) is not None

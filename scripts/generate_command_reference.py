from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from oterminus.commands import (
    COMMAND_PACKS,
    COMMAND_REGISTRY,
    NETWORK_TOUCHING_WARNING,
    command_maturity_status,
)

DOCS_REFERENCE = REPO_ROOT / "docs" / "reference"
CAPABILITY_MAP_PATH = DOCS_REFERENCE / "capability-map.md"
COMMAND_FAMILIES_PATH = DOCS_REFERENCE / "command-families.md"
DEFAULT_DOCS_ROOTS: tuple[Path | str | None, ...] = (None, "website/docs")

GENERATED_NOTE = (
    "<!-- Generated from the command registry. Do not edit command tables manually; "
    "update command specs instead. -->"
)
TABLE_LINE_BREAK = "<br />"


def _normalize_level(value: object) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _direct_support_text(values: set[bool]) -> str:
    if values == {True}:
        return "yes"
    if values == {False}:
        return "no"
    return "mixed"


def _direct_flag_policy_text(values: set[str]) -> str:
    if len(values) == 1:
        return next(iter(values))
    return TABLE_LINE_BREAK.join(sorted(values))


def _platform_text(platforms: object) -> str:
    if not platforms:
        return "all"
    return ", ".join(sorted(str(item) for item in platforms))


def _escape_mdx_text(value: str) -> str:
    return value.replace("<", "&lt;").replace(">", "&gt;")


def _join_table_lines(values: list[str] | tuple[str, ...]) -> str:
    return TABLE_LINE_BREAK.join(_escape_mdx_text(value) for value in values)


def _notes_for_spec(spec: object) -> tuple[str, ...]:
    notes = tuple(getattr(spec, "notes", ()))
    if getattr(spec, "network_touching", False) and NETWORK_TOUCHING_WARNING not in notes:
        return (*notes, NETWORK_TOUCHING_WARNING)
    return notes


def _render_capability_map() -> str:
    by_capability = defaultdict(list)
    for spec in COMMAND_REGISTRY.values():
        by_capability[spec.capability_id].append(spec)

    has_network_touching = any(spec.network_touching for spec in COMMAND_REGISTRY.values())
    headers = [
        "Capability ID",
        "Label",
        "Description",
        "Commands",
        "Platforms",
        "Risk levels present",
        "Maturity/status",
        "Direct support",
        "Direct flag policy",
    ]
    if has_network_touching:
        headers.append("Network")
    headers.append("Notes")

    lines = [
        "# Capability Map",
        "",
        GENERATED_NOTE,
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]

    for capability_id in sorted(by_capability):
        specs = sorted(by_capability[capability_id], key=lambda item: item.name)
        first = specs[0]
        commands = ", ".join(f"`{spec.name}`" for spec in specs)
        risks = ", ".join(sorted({_normalize_level(spec.risk_level) for spec in specs}))
        maturities = TABLE_LINE_BREAK.join(
            sorted({command_maturity_status(spec) for spec in specs})
        )
        direct_support = _direct_support_text({spec.direct_supported for spec in specs})
        direct_flag_policy = _direct_flag_policy_text(
            {_normalize_level(spec.direct_flag_policy) for spec in specs}
        )
        notes = sorted({note for spec in specs for note in _notes_for_spec(spec)})
        notes_text = _join_table_lines(notes) if notes else "—"
        row = [
            capability_id,
            first.capability_label,
            _escape_mdx_text(first.capability_description),
            commands,
            _platform_text({p for spec in specs for p in (spec.supported_platforms or ())}),
            risks,
            maturities,
            direct_support,
            direct_flag_policy,
        ]
        if has_network_touching:
            row.append("yes" if any(spec.network_touching for spec in specs) else "no")
        row.append(notes_text)
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def _render_command_families() -> str:
    by_capability = defaultdict(list)
    for spec in COMMAND_REGISTRY.values():
        by_capability[spec.capability_id].append(spec)

    has_network_touching = any(spec.network_touching for spec in COMMAND_REGISTRY.values())
    lines = [
        "# Command Families Reference",
        "",
        GENERATED_NOTE,
        "",
    ]

    for capability_id in sorted(by_capability):
        specs = sorted(by_capability[capability_id], key=lambda item: item.name)
        first = specs[0]
        lines.extend(
            [
                f"## `{capability_id}`",
                "",
                f"**Label:** {first.capability_label}",
                "",
                f"**Description:** {first.capability_description}",
                "",
            ]
        )
        headers = [
            "Command",
            "Category",
            "Platforms",
            "Risk",
            "Maturity",
            "Status",
            "Direct support",
            "Direct flag policy",
        ]
        if has_network_touching:
            headers.append("Network")
        headers.extend(["Examples", "Natural-language aliases", "Notes"])
        lines.extend(
            [
                "| " + " | ".join(headers) + " |",
                "|" + "|".join("---" for _ in headers) + "|",
            ]
        )
        for spec in specs:
            examples = (
                TABLE_LINE_BREAK.join(f"`{example}`" for example in spec.examples)
                if spec.examples
                else "—"
            )
            aliases = (
                ", ".join(f"`{alias}`" for alias in spec.natural_language_aliases)
                if spec.natural_language_aliases
                else "—"
            )
            spec_notes = _notes_for_spec(spec)
            notes = _join_table_lines(spec_notes) if spec_notes else "—"
            row = [
                f"`{spec.name}`",
                spec.category,
                _platform_text(spec.supported_platforms),
                _normalize_level(spec.risk_level),
                _normalize_level(spec.maturity_level),
                command_maturity_status(spec),
                "yes" if spec.direct_supported else "no",
                _normalize_level(spec.direct_flag_policy),
            ]
            if has_network_touching:
                row.append("yes" if spec.network_touching else "no")
            row.extend([examples, aliases, notes])
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    return "\n".join(lines)


def _resolve_docs_root(docs_root: Path | str) -> Path:
    path = Path(docs_root)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _reference_paths(docs_root: Path | str | None = None) -> tuple[Path, Path]:
    if docs_root is None:
        return CAPABILITY_MAP_PATH, COMMAND_FAMILIES_PATH
    reference_dir = _resolve_docs_root(docs_root) / "reference"
    return reference_dir / "capability-map.md", reference_dir / "command-families.md"


def generate_reference_docs(docs_root: Path | str | None = None) -> dict[Path, str]:
    capability_map_path, command_families_path = _reference_paths(docs_root)
    return {
        capability_map_path: _render_capability_map(),
        command_families_path: _render_command_families(),
    }


def _check_docs(contents: dict[Path, str]) -> int:
    stale: list[Path] = []
    for path, expected in contents.items():
        actual = path.read_text(encoding="utf-8") if path.exists() else ""
        if actual != expected:
            stale.append(path)

    if stale:
        rel = ", ".join(str(path.relative_to(REPO_ROOT)) for path in stale)
        print(f"Generated command reference docs are stale: {rel}")
        print("Run: poetry run python scripts/generate_command_reference.py --write")
        return 1

    print("Generated command reference docs are up to date.")
    return 0


def _write_docs(contents: dict[Path, str]) -> int:
    for path, content in contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.relative_to(REPO_ROOT)}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate registry-backed command reference docs.")
    parser.add_argument("--write", action="store_true", help="Write generated docs to disk.")
    parser.add_argument("--check", action="store_true", help="Check generated docs are up to date.")
    parser.add_argument(
        "--docs-root",
        action="append",
        help=(
            "Documentation root that contains reference/. May be repeated. "
            "Defaults to docs and website/docs."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.write == args.check:
        print("Specify exactly one mode: --write or --check")
        return 2

    _ = COMMAND_PACKS
    docs_roots = args.docs_root or DEFAULT_DOCS_ROOTS
    contents: dict[Path, str] = {}
    for docs_root in docs_roots:
        contents.update(generate_reference_docs(docs_root))

    if args.write:
        return _write_docs(contents)
    return _check_docs(contents)


if __name__ == "__main__":
    raise SystemExit(main())

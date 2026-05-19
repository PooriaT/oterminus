from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from oterminus.commands import COMMAND_PACKS, COMMAND_REGISTRY

DOCS_REFERENCE = REPO_ROOT / "docs" / "reference"
CAPABILITY_MAP_PATH = DOCS_REFERENCE / "capability-map.md"
COMMAND_FAMILIES_PATH = DOCS_REFERENCE / "command-families.md"

GENERATED_NOTE = (
    "<!-- Generated from the command registry. Do not edit command tables manually; "
    "update command specs instead. -->"
)


def _normalize_level(value: object) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _render_capability_map() -> str:
    by_capability = defaultdict(list)
    for spec in COMMAND_REGISTRY.values():
        by_capability[spec.capability_id].append(spec)

    lines = [
        "# Capability Map",
        "",
        GENERATED_NOTE,
        "",
        "| Capability ID | Label | Description | Commands | Risk levels present | Maturity levels present | Notes |",
        "|---|---|---|---|---|---|---|",
    ]

    for capability_id in sorted(by_capability):
        specs = sorted(by_capability[capability_id], key=lambda item: item.name)
        first = specs[0]
        commands = ", ".join(f"`{spec.name}`" for spec in specs)
        risks = ", ".join(sorted({_normalize_level(spec.risk_level) for spec in specs}))
        maturities = ", ".join(sorted({_normalize_level(spec.maturity_level) for spec in specs}))
        notes = sorted({note for spec in specs for note in spec.notes})
        notes_text = "<br>".join(notes) if notes else "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    capability_id,
                    first.capability_label,
                    first.capability_description,
                    commands,
                    risks,
                    maturities,
                    notes_text,
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def _render_command_families() -> str:
    by_capability = defaultdict(list)
    for spec in COMMAND_REGISTRY.values():
        by_capability[spec.capability_id].append(spec)

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
                "| Command | Category | Risk | Maturity | Direct support | Examples | Natural-language aliases | Notes |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for spec in specs:
            examples = (
                "<br>".join(f"`{example}`" for example in spec.examples) if spec.examples else "—"
            )
            aliases = (
                ", ".join(f"`{alias}`" for alias in spec.natural_language_aliases)
                if spec.natural_language_aliases
                else "—"
            )
            notes = "<br>".join(spec.notes) if spec.notes else "—"
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{spec.name}`",
                        spec.category,
                        _normalize_level(spec.risk_level),
                        _normalize_level(spec.maturity_level),
                        "yes" if spec.direct_supported else "no",
                        examples,
                        aliases,
                        notes,
                    ]
                )
                + " |"
            )
        lines.append("")

    return "\n".join(lines)


def generate_reference_docs() -> dict[Path, str]:
    return {
        CAPABILITY_MAP_PATH: _render_capability_map(),
        COMMAND_FAMILIES_PATH: _render_command_families(),
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.write == args.check:
        print("Specify exactly one mode: --write or --check")
        return 2

    _ = COMMAND_PACKS
    contents = generate_reference_docs()

    if args.write:
        return _write_docs(contents)
    return _check_docs(contents)


if __name__ == "__main__":
    raise SystemExit(main())

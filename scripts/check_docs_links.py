#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
README = REPO_ROOT / "README.md"
MKDOCS_CONFIG = REPO_ROOT / "mkdocs.yml"

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
ANCHOR_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
PLACEHOLDER_PATTERNS = ("TODO", "TBD", "example.com", "your-", "REPLACE_ME")


def normalize_anchor(text: str) -> str:
    anchor = text.strip().lower()
    anchor = re.sub(r"[`*_~]", "", anchor)
    anchor = re.sub(r"[^a-z0-9\s-]", "", anchor)
    anchor = re.sub(r"\s+", "-", anchor)
    anchor = re.sub(r"-+", "-", anchor).strip("-")
    return anchor


def anchors_for_markdown(path: Path) -> set[str]:
    content = path.read_text(encoding="utf-8")
    return {normalize_anchor(match.group(1)) for match in ANCHOR_RE.finditer(content)}


def iter_markdown_links(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    return [m.group(1).strip() for m in LINK_RE.finditer(content)]


def is_external(link: str) -> bool:
    return link.startswith(("http://", "https://", "mailto:", "tel:"))


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def check_markdown_file(path: Path, errors: list[str]) -> None:
    base = path.parent
    for link in iter_markdown_links(path):
        if not link or link.startswith("#") or is_external(link):
            continue
        if link.startswith("<") and link.endswith(">"):
            link = link[1:-1]
        if any(pattern.lower() in link.lower() for pattern in PLACEHOLDER_PATTERNS):
            errors.append(f"{_display_path(path)}: placeholder-like link target: {link}")

        target_raw = link.split("#", 1)[0].split("?", 1)[0]
        anchor = link.split("#", 1)[1] if "#" in link else None

        target_path = (base / target_raw).resolve() if target_raw else path

        try:
            target_path.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"{_display_path(path)}: link escapes repository: {link}")
            continue

        if target_raw and not target_path.exists():
            errors.append(f"{_display_path(path)}: missing link target: {link}")
            continue

        if anchor and target_path.suffix.lower() == ".md":
            anchors = anchors_for_markdown(target_path)
            if normalize_anchor(anchor) not in anchors:
                errors.append(
                    f"{_display_path(path)}: missing anchor '#{anchor}' in "
                    f"{_display_path(target_path)}"
                )


def check_mkdocs_nav(errors: list[str]) -> None:
    content = MKDOCS_CONFIG.read_text(encoding="utf-8")
    for line_num, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        _, value = stripped.split(":", 1)
        nav_target = value.strip()
        if not nav_target.endswith(".md"):
            continue
        target = DOCS_DIR / nav_target
        if not target.exists():
            errors.append(f"mkdocs.yml:{line_num}: nav target does not exist: docs/{nav_target}")


def run_checks() -> list[str]:
    errors: list[str] = []
    markdown_files = [README, *sorted(DOCS_DIR.rglob("*.md"))]
    for md_file in markdown_files:
        check_markdown_file(md_file, errors)
    check_mkdocs_nav(errors)
    return errors


def main() -> int:
    errors = run_checks()
    if errors:
        print("Documentation link check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Documentation link check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

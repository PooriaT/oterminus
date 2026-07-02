#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
DOCUSAURUS_DOCS_DIR = REPO_ROOT / "website" / "docs"
DOCUSAURUS_SIDEBAR = REPO_ROOT / "website" / "sidebars.ts"

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
ANCHOR_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
SIDEBAR_ID_RE = re.compile(r"\bid:\s*['\"]([^'\"]+)['\"]")
SIDEBAR_ITEM_RE = re.compile(r"^\s*['\"]([^'\"]+)['\"],?\s*$", re.MULTILINE)
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


def _resolve_local_target(base: Path, raw_target: str) -> Path:
    if raw_target.startswith("/"):
        trimmed = raw_target.lstrip("/")
        if trimmed.startswith("oterminus/"):
            trimmed = trimmed.removeprefix("oterminus/")
        target = DOCUSAURUS_DOCS_DIR / trimmed
        if target.suffix:
            return target.resolve()
        for candidate in (
            DOCUSAURUS_DOCS_DIR / f"{trimmed}.md",
            DOCUSAURUS_DOCS_DIR / f"{trimmed}.mdx",
            DOCUSAURUS_DOCS_DIR / trimmed / "index.md",
            DOCUSAURUS_DOCS_DIR / trimmed / "index.mdx",
        ):
            if candidate.exists():
                return candidate.resolve()
        return target.resolve()
    return (base / raw_target).resolve()


def check_markdown_file(path: Path, errors: list[str]) -> None:
    base = path.parent
    for link in iter_markdown_links(path):
        if not link or is_external(link):
            continue
        if link.startswith("<") and link.endswith(">"):
            link = link[1:-1]
        if any(pattern.lower() in link.lower() for pattern in PLACEHOLDER_PATTERNS):
            errors.append(f"{_display_path(path)}: placeholder-like link target: {link}")

        target_raw = link.split("#", 1)[0].split("?", 1)[0]
        anchor = link.split("#", 1)[1] if "#" in link else None

        target_path = _resolve_local_target(base, target_raw) if target_raw else path

        try:
            target_path.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"{_display_path(path)}: link escapes repository: {link}")
            continue

        if target_raw and not target_path.exists():
            errors.append(f"{_display_path(path)}: missing link target: {link}")
            continue

        if anchor and target_path.suffix.lower() in {".md", ".mdx"}:
            anchors = anchors_for_markdown(target_path)
            if normalize_anchor(anchor) not in anchors:
                errors.append(
                    f"{_display_path(path)}: missing anchor '#{anchor}' in "
                    f"{_display_path(target_path)}"
                )


def _docusaurus_doc_exists(doc_id: str) -> bool:
    candidates = [
        DOCUSAURUS_DOCS_DIR / f"{doc_id}.md",
        DOCUSAURUS_DOCS_DIR / f"{doc_id}.mdx",
        DOCUSAURUS_DOCS_DIR / doc_id / "index.md",
        DOCUSAURUS_DOCS_DIR / doc_id / "index.mdx",
    ]
    return any(candidate.exists() for candidate in candidates)


def check_docusaurus_sidebar(errors: list[str]) -> None:
    content = DOCUSAURUS_SIDEBAR.read_text(encoding="utf-8")
    doc_ids = set(SIDEBAR_ID_RE.findall(content))
    doc_ids.update(SIDEBAR_ITEM_RE.findall(content))
    for doc_id in sorted(doc_ids):
        if not _docusaurus_doc_exists(doc_id):
            errors.append(f"website/sidebars.ts: sidebar doc target does not exist: {doc_id}")


def run_checks() -> list[str]:
    errors: list[str] = []
    markdown_files = [
        README,
        *sorted(DOCUSAURUS_DOCS_DIR.rglob("*.md")),
        *sorted(DOCUSAURUS_DOCS_DIR.rglob("*.mdx")),
    ]
    for md_file in markdown_files:
        check_markdown_file(md_file, errors)
    check_docusaurus_sidebar(errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args:
        print("Usage: check_docs_links.py")
        return 2

    errors = run_checks()
    if errors:
        print("Documentation link check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Docusaurus documentation link check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

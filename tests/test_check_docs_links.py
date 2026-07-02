from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_docs_links.py"
SPEC = spec_from_file_location("check_docs_links", MODULE_PATH)
assert SPEC and SPEC.loader
check_docs_links = module_from_spec(SPEC)
SPEC.loader.exec_module(check_docs_links)


def test_valid_local_file_link_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "docs" / "target.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Target\n", encoding="utf-8")

    page = tmp_path / "docs" / "page.md"
    page.write_text("[ok](target.md)\n", encoding="utf-8")

    monkeypatch.setattr(check_docs_links, "REPO_ROOT", tmp_path)

    errors: list[str] = []
    check_docs_links.check_markdown_file(page, errors)
    assert errors == []


def test_missing_local_file_link_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = tmp_path / "docs" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("[bad](missing.md)\n", encoding="utf-8")

    monkeypatch.setattr(check_docs_links, "REPO_ROOT", tmp_path)

    errors: list[str] = []
    check_docs_links.check_markdown_file(page, errors)
    assert any("missing link target" in err for err in errors)


def test_external_links_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = tmp_path / "docs" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("[ext](https://example.com/path)\n", encoding="utf-8")

    monkeypatch.setattr(check_docs_links, "REPO_ROOT", tmp_path)

    errors: list[str] = []
    check_docs_links.check_markdown_file(page, errors)
    assert errors == []


def test_mkdocs_nav_missing_file_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mkdocs = tmp_path / "mkdocs.yml"
    mkdocs.write_text("nav:\n  - Home: index.md\n", encoding="utf-8")

    monkeypatch.setattr(check_docs_links, "MKDOCS_CONFIG", mkdocs)
    monkeypatch.setattr(check_docs_links, "DOCS_DIR", tmp_path / "docs")

    errors: list[str] = []
    check_docs_links.check_mkdocs_nav(errors)
    assert any("nav target does not exist" in err for err in errors)


def test_same_file_anchor_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = tmp_path / "docs" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Section\n\n[Jump](#section)\n", encoding="utf-8")

    monkeypatch.setattr(check_docs_links, "REPO_ROOT", tmp_path)

    errors: list[str] = []
    check_docs_links.check_markdown_file(page, errors)
    assert errors == []


def test_same_file_anchor_missing_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = tmp_path / "docs" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Section\n\n[Jump](#renamed-section)\n", encoding="utf-8")

    monkeypatch.setattr(check_docs_links, "REPO_ROOT", tmp_path)

    errors: list[str] = []
    check_docs_links.check_markdown_file(page, errors)
    assert any("missing anchor" in err for err in errors)


def test_readme_docs_link_checked() -> None:
    errors = check_docs_links.run_checks()
    assert not any(err.startswith("README.md: missing link target") for err in errors)


def test_docusaurus_sidebar_missing_file_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "website" / "docs"
    docs.mkdir(parents=True)
    sidebar = tmp_path / "website" / "sidebars.ts"
    sidebar.write_text(
        "const sidebars = {docsSidebar: [{type: 'doc', id: 'missing'}]};\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(check_docs_links, "DOCUSAURUS_DOCS_DIR", docs)
    monkeypatch.setattr(check_docs_links, "DOCUSAURUS_SIDEBAR", sidebar)

    errors: list[str] = []
    check_docs_links.check_docusaurus_sidebar(errors)
    assert any("sidebar doc target does not exist" in err for err in errors)


def test_docusaurus_mode_checks_docs_and_sidebar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "website" / "docs"
    docs.mkdir(parents=True)
    (docs / "index.md").write_text("# Home\n\n[Next](guide.md)\n", encoding="utf-8")
    (docs / "guide.md").write_text("# Guide\n", encoding="utf-8")
    sidebar = tmp_path / "website" / "sidebars.ts"
    sidebar.write_text(
        "const sidebars = {docsSidebar: [{type: 'doc', id: 'index'}, 'guide']};\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(check_docs_links, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_docs_links, "DOCUSAURUS_DOCS_DIR", docs)
    monkeypatch.setattr(check_docs_links, "DOCUSAURUS_SIDEBAR", sidebar)

    assert check_docs_links.run_checks(docusaurus=True) == []

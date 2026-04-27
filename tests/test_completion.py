from pathlib import Path

from oterminus.completion import build_repl_completions


def _texts(candidates) -> list[str]:
    return [candidate.text for candidate in candidates]


def test_first_token_completion_includes_builtins_and_registry_commands() -> None:
    candidates = _texts(build_repl_completions("he"))

    assert "help" in candidates
    assert "head" in candidates


def test_first_token_completion_includes_supported_categories() -> None:
    candidates = _texts(build_repl_completions("proc"))

    assert "process_inspection" in candidates


def test_path_completion_for_relative_file_and_dir(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello")
    (tmp_path / "src").mkdir()

    file_candidates = _texts(build_repl_completions("cat READ", cwd=tmp_path))
    dir_candidates = _texts(build_repl_completions("cd sr", cwd=tmp_path))

    assert "README.md" in file_candidates
    assert "src/" in dir_candidates


def test_path_completion_for_nested_paths(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("guide")

    candidates = _texts(build_repl_completions("cat docs/gu", cwd=tmp_path))

    assert "docs/guide.md" in candidates


def test_path_completion_preserves_dot_slash_prefix(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()

    candidates = _texts(build_repl_completions("cd ./s", cwd=tmp_path))

    assert "./src/" in candidates


def test_path_completion_preserves_tilde_prefix(tmp_path: Path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    documents_dir = home_dir / "Documents"
    documents_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    candidates = _texts(build_repl_completions("cd ~/Do", cwd=tmp_path))

    assert "~/Documents/" in candidates


def test_path_completion_ignores_permission_errors(tmp_path: Path, monkeypatch) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()

    def raise_permission_error(_self):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "iterdir", raise_permission_error)
    candidates = _texts(build_repl_completions("cat protected/", cwd=tmp_path))

    assert candidates == []

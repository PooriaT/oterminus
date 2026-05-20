from pathlib import Path
from unittest.mock import Mock

from oterminus.completion import (
    build_repl_completions,
    get_completion_backend_status,
    prompt_toolkit_completer,
)


def _texts(candidates) -> list[str]:
    return [candidate.text for candidate in candidates]


def test_first_token_completion_includes_builtins_and_registry_commands() -> None:
    candidates = _texts(build_repl_completions("he"))

    assert "help" in candidates
    assert "head" in candidates


def test_first_token_completion_includes_dry_run_and_explain_builtins() -> None:
    dry_run_candidates = _texts(build_repl_completions("dry"))
    explain_candidates = _texts(build_repl_completions("exp"))
    history_candidates = _texts(build_repl_completions("his"))
    rerun_candidates = _texts(build_repl_completions("rer"))

    assert "dry-run" in dry_run_candidates
    assert "explain" in explain_candidates
    assert "history" in history_candidates
    assert "rerun" in rerun_candidates


def test_first_token_completion_includes_discovery_builtins() -> None:
    capability_candidates = _texts(build_repl_completions("cap"))
    command_candidates = _texts(build_repl_completions("com"))
    example_candidates = _texts(build_repl_completions("exa"))

    assert "capabilities" in capability_candidates
    assert "commands" in command_candidates
    assert "examples" in example_candidates


def test_first_token_completion_includes_clear_command() -> None:
    candidates = _texts(build_repl_completions("cle"))

    assert "clear" in candidates


def test_first_token_completion_includes_audit_command() -> None:
    candidates = _texts(build_repl_completions("aud"))

    assert "audit" in candidates
    assert "audit status" in candidates
    assert "audit tail" in candidates
    assert "audit clear" in candidates


def test_first_token_completion_includes_supported_capabilities() -> None:
    candidates = _texts(build_repl_completions("proc"))

    assert "process_inspection" in candidates


def test_first_token_completion_can_include_capability_aliases() -> None:
    candidates = _texts(build_repl_completions("search", include_capability_hints=True))

    assert "search text" in candidates


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


def test_prompt_toolkit_completer_returns_prompt_toolkit_completion_objects() -> None:
    completer = prompt_toolkit_completer()
    assert completer is not None

    document = Mock()
    document.text_before_cursor = "he"
    items = list(completer.get_completions(document, None))

    assert any(item.text == "help" for item in items)
    assert all(hasattr(item, "start_position") for item in items)


def test_get_completion_backend_status_reports_prompt_toolkit() -> None:
    backend, completer = get_completion_backend_status()

    assert backend == "prompt_toolkit"
    assert completer is not None


def test_help_completion_suggests_capabilities_and_command_families() -> None:
    capability_candidates = _texts(build_repl_completions("help file"))
    command_candidates = _texts(build_repl_completions("help pw"))

    assert "filesystem_inspection" in capability_candidates
    assert "pwd" in command_candidates


def test_completion_excludes_disabled_pack_commands() -> None:
    candidates = _texts(build_repl_completions("op", disabled_pack_ids=frozenset({"macos"})))

    assert "open" not in candidates


def test_completion_excludes_platform_unsupported_commands() -> None:
    candidates = _texts(build_repl_completions("op", platform_id="linux"))
    assert "open" not in candidates

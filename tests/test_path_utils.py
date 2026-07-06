from pathlib import Path

import pytest

from oterminus.path_utils import expand_user_path


@pytest.fixture
def fake_home(monkeypatch, tmp_path: Path) -> Path:
    class FakePath:
        @staticmethod
        def home() -> Path:
            return tmp_path

    monkeypatch.setattr("oterminus.path_utils.Path", FakePath)
    return tmp_path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("~", "{home}"),
        ("~/Downloads", "{home}/Downloads"),
        ("~//etc/passwd", "{home}//etc/passwd"),
        ("~/Library/Application Support", "{home}/Library/Application Support"),
    ],
)
def test_expand_user_path_expands_exact_current_user_home_cases(
    fake_home: Path, raw: str, expected: str
) -> None:
    assert expand_user_path(raw) == expected.replace("{home}", str(fake_home))


@pytest.mark.parametrize(
    "raw",
    [
        ".",
        "src",
        "/tmp",
        "~otheruser",
        "~otheruser/file",
        "$HOME/file",
        "${HOME}/file",
        "./~",
        "foo~",
        "*",
        "?",
        "$(pwd)",
        "`pwd`",
    ],
)
def test_expand_user_path_leaves_unsupported_shell_syntax_unchanged(
    fake_home: Path, raw: str
) -> None:
    assert expand_user_path(raw) == raw

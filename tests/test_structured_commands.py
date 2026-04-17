import pytest

from oterminus.structured_commands import (
    StructuredCommandError,
    render_structured_command,
    supports_structured_family,
)


def test_supported_structured_families_are_curated() -> None:
    assert supports_structured_family("ls") is True
    assert supports_structured_family("pwd") is True
    assert supports_structured_family("mkdir") is True
    assert supports_structured_family("chmod") is True
    assert supports_structured_family("find") is True
    assert supports_structured_family("cat") is False


@pytest.mark.parametrize(
    ("command_family", "arguments", "expected_argv", "expected_command"),
    [
        (
            "ls",
            {"path": ".", "long": True, "human_readable": True, "all": False, "recursive": False},
            ("ls", "-l", "-h", "."),
            "ls -l -h .",
        ),
        ("pwd", {}, ("pwd",), "pwd"),
        ("mkdir", {"path": "backup", "parents": True}, ("mkdir", "-p", "backup"), "mkdir -p backup"),
        ("chmod", {"path": "run.sh", "mode": "755"}, ("chmod", "755", "run.sh"), "chmod 755 run.sh"),
        ("find", {"path": ".", "name": "*.py"}, ("find", ".", "-name", "*.py"), "find . -name '*.py'"),
    ],
)
def test_render_structured_command(command_family: str, arguments: dict[str, object], expected_argv: tuple[str, ...], expected_command: str) -> None:
    rendered = render_structured_command(command_family, arguments)

    assert rendered.argv == expected_argv
    assert rendered.command == expected_command


def test_render_structured_command_rejects_unsupported_family() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("cat", {"path": "README.md"})


def test_render_structured_command_rejects_invalid_arguments() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("chmod", {"path": "run.sh", "mode": "u+x"})


def test_render_structured_command_rejects_human_readable_without_long() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("ls", {"path": ".", "human_readable": True})

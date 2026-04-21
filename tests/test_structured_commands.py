import pytest

from oterminus.structured_commands import (
    StructuredCommandError,
    parse_raw_command_as_structured,
    render_structured_command,
    supports_structured_family,
)


@pytest.mark.parametrize(
    "command_family",
    ["ls", "pwd", "mkdir", "chmod", "find", "cp", "mv", "du", "stat", "head", "tail", "grep", "cat", "open", "file"],
)
def test_supported_structured_families_are_curated(command_family: str) -> None:
    assert supports_structured_family(command_family) is True


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
        (
            "cp",
            {"source": "src.txt", "destination": "dest.txt", "recursive": False, "preserve": True, "no_clobber": True},
            ("cp", "-p", "-n", "src.txt", "dest.txt"),
            "cp -p -n src.txt dest.txt",
        ),
        (
            "mv",
            {"source": "draft.txt", "destination": "archive.txt", "no_clobber": True},
            ("mv", "-n", "draft.txt", "archive.txt"),
            "mv -n draft.txt archive.txt",
        ),
        (
            "du",
            {"path": ".", "human_readable": True, "summarize": True, "max_depth": None},
            ("du", "-h", "-s", "."),
            "du -h -s .",
        ),
        (
            "stat",
            {"path": "README.md", "dereference": True, "verbose": True},
            ("stat", "-L", "-x", "README.md"),
            "stat -L -x README.md",
        ),
        (
            "head",
            {"paths": ["README.md"], "lines": 5, "bytes": None},
            ("head", "-n", "5", "README.md"),
            "head -n 5 README.md",
        ),
        (
            "tail",
            {"paths": ["README.md"], "lines": None, "bytes": 32},
            ("tail", "-c", "32", "README.md"),
            "tail -c 32 README.md",
        ),
        (
            "grep",
            {
                "pattern": "TODO",
                "paths": ["src"],
                "ignore_case": True,
                "line_number": True,
                "fixed_strings": True,
                "recursive": True,
                "files_with_matches": False,
                "max_count": 2,
            },
            ("grep", "-F", "-i", "-n", "-r", "-m", "2", "TODO", "src"),
            "grep -F -i -n -r -m 2 TODO src",
        ),
        ("cat", {"paths": ["README.md", "pyproject.toml"]}, ("cat", "README.md", "pyproject.toml"), "cat README.md pyproject.toml"),
        ("open", {"path": ".", "reveal": True}, ("open", "-R", "."), "open -R ."),
        ("file", {"paths": ["README.md"], "brief": True}, ("file", "-b", "README.md"), "file -b README.md"),
    ],
)
def test_render_structured_command(
    command_family: str, arguments: dict[str, object], expected_argv: tuple[str, ...], expected_command: str
) -> None:
    rendered = render_structured_command(command_family, arguments)

    assert rendered.argv == expected_argv
    assert rendered.command == expected_command


@pytest.mark.parametrize(
    ("command", "expected_family", "expected_arguments"),
    [
        (
            "cp -pn src.txt dest.txt",
            "cp",
            {"source": "src.txt", "destination": "dest.txt", "recursive": False, "preserve": True, "no_clobber": True},
        ),
        (
            "du -sh .",
            "du",
            {"path": ".", "human_readable": True, "summarize": True, "max_depth": None},
        ),
        (
            "head -n 3 README.md",
            "head",
            {"paths": ["README.md"], "lines": 3, "bytes": None},
        ),
        (
            "tail -c32 README.md",
            "tail",
            {"paths": ["README.md"], "lines": None, "bytes": 32},
        ),
        (
            "grep -Finr -m2 TODO src",
            "grep",
            {
                "pattern": "TODO",
                "paths": ["src"],
                "ignore_case": True,
                "line_number": True,
                "fixed_strings": True,
                "recursive": True,
                "files_with_matches": False,
                "max_count": 2,
            },
        ),
        ("cat README.md pyproject.toml", "cat", {"paths": ["README.md", "pyproject.toml"]}),
        ("open -R .", "open", {"path": ".", "reveal": True}),
        ("file -b README.md", "file", {"paths": ["README.md"], "brief": True}),
    ],
)
def test_parse_raw_command_as_structured(
    command: str, expected_family: str, expected_arguments: dict[str, object]
) -> None:
    parsed = parse_raw_command_as_structured(command)

    assert parsed == (expected_family, expected_arguments)


def test_render_structured_command_rejects_invalid_arguments() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("chmod", {"path": "run.sh", "mode": "u+x"})


def test_render_structured_command_rejects_open_url_target() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("open", {"path": "https://example.com", "reveal": False})


def test_render_structured_command_rejects_conflicting_grep_flags() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "grep",
            {
                "pattern": "TODO",
                "paths": ["src"],
                "ignore_case": False,
                "line_number": True,
                "fixed_strings": False,
                "recursive": False,
                "files_with_matches": True,
                "max_count": None,
            },
        )


def test_parse_raw_command_as_structured_returns_none_for_unsupported_stat_format_variant() -> None:
    assert parse_raw_command_as_structured("stat -f '%z' README.md") is None


@pytest.mark.parametrize(
    "command",
    [
        "cp src.txt",
        "mv -z old.txt new.txt",
        "du -d nope .",
        "stat",
        "head -n 3",
        "tail -n 1",
        "grep -n TODO",
        "cat -n README.md",
        "open -Z .",
        "file",
    ],
)
def test_parse_raw_command_as_structured_rejects_invalid_variants(command: str) -> None:
    assert parse_raw_command_as_structured(command) is None


def test_parse_raw_command_as_structured_raises_for_disallowed_open_url_target() -> None:
    with pytest.raises(StructuredCommandError):
        parse_raw_command_as_structured("open https://example.com")

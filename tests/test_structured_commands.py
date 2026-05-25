import pytest

from oterminus.structured_commands import (
    StructuredCommandError,
    parse_raw_command_as_structured,
    render_structured_command,
    supports_structured_family,
)


@pytest.mark.parametrize(
    "command_family",
    [
        "ls",
        "pwd",
        "clear",
        "whoami",
        "uname",
        "which",
        "env",
        "mkdir",
        "chmod",
        "find",
        "cp",
        "mv",
        "du",
        "df",
        "stat",
        "head",
        "tail",
        "grep",
        "cat",
        "open",
        "file",
        "ps",
        "pgrep",
        "lsof",
        "wc",
        "sort",
        "uniq",
        "git",
        "ping",
        "curl",
        "dig",
        "nslookup",
        "tar",
        "unzip",
        "zip",
    ],
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
        ("clear", {}, ("clear",), "clear"),
        ("whoami", {}, ("whoami",), "whoami"),
        (
            "uname",
            {
                "all": False,
                "kernel_name": True,
                "node_name": False,
                "kernel_release": True,
                "kernel_version": False,
                "machine": False,
            },
            ("uname", "-s", "-r"),
            "uname -s -r",
        ),
        (
            "which",
            {"commands": ["python3"], "all_matches": True},
            ("which", "-a", "python3"),
            "which -a python3",
        ),
        ("env", {"variable": "PATH"}, ("env", "PATH"), "env PATH"),
        (
            "mkdir",
            {"path": "backup", "parents": True},
            ("mkdir", "-p", "backup"),
            "mkdir -p backup",
        ),
        (
            "chmod",
            {"path": "run.sh", "mode": "755"},
            ("chmod", "755", "run.sh"),
            "chmod 755 run.sh",
        ),
        (
            "find",
            {"path": ".", "name": "*.py"},
            ("find", ".", "-name", "*.py"),
            "find . -name '*.py'",
        ),
        (
            "cp",
            {
                "source": "src.txt",
                "destination": "dest.txt",
                "recursive": False,
                "preserve": True,
                "no_clobber": True,
            },
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
        ("df", {"path": ".", "human_readable": True}, ("df", "-h", "."), "df -h ."),
        ("df", {"path": None, "human_readable": False}, ("df",), "df"),
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
        (
            "cat",
            {"paths": ["README.md", "pyproject.toml"]},
            ("cat", "README.md", "pyproject.toml"),
            "cat README.md pyproject.toml",
        ),
        ("open", {"path": ".", "reveal": True}, ("open", "-R", "."), "open -R ."),
        (
            "file",
            {"paths": ["README.md"], "brief": True},
            ("file", "-b", "README.md"),
            "file -b README.md",
        ),
        (
            "ps",
            {"all_processes": True, "full_format": True, "user": "root", "pid": None},
            ("ps", "-A", "-f", "-u", "root"),
            "ps -A -f -u root",
        ),
        (
            "pgrep",
            {"pattern": "python", "full_command": True, "list_names": True, "user": None},
            ("pgrep", "-f", "-l", "python"),
            "pgrep -f -l python",
        ),
        (
            "lsof",
            {
                "path": ".",
                "pid": None,
                "command_prefix": "python",
                "and_selectors": True,
                "no_dns": True,
                "no_port_names": True,
            },
            ("lsof", "-a", "-n", "-P", "-c", "python", "."),
            "lsof -a -n -P -c python .",
        ),
        (
            "wc",
            {"paths": ["README.md"], "lines": True, "words": False, "bytes": True},
            ("wc", "-l", "-c", "README.md"),
            "wc -l -c README.md",
        ),
        (
            "sort",
            {"path": "README.md", "numeric": False, "reverse": True, "unique": True},
            ("sort", "-r", "-u", "README.md"),
            "sort -r -u README.md",
        ),
        (
            "uniq",
            {"path": "README.md", "count": True, "repeated_only": False, "unique_only": False},
            ("uniq", "-c", "README.md"),
            "uniq -c README.md",
        ),
        ("git", {"operation": "status_short"}, ("git", "status", "--short"), "git status --short"),
        (
            "git",
            {"operation": "branch_current"},
            ("git", "branch", "--show-current"),
            "git branch --show-current",
        ),
        (
            "git",
            {"operation": "log_oneline", "count": 7},
            ("git", "log", "--oneline", "-n", "7"),
            "git log --oneline -n 7",
        ),
        ("git", {"operation": "diff_stat"}, ("git", "diff", "--stat"), "git diff --stat"),
        (
            "git",
            {"operation": "diff_name_only"},
            ("git", "diff", "--name-only"),
            "git diff --name-only",
        ),
        (
            "ping",
            {"host": "example.com", "count": 4},
            ("ping", "-c", "4", "example.com"),
            "ping -c 4 example.com",
        ),
        (
            "ping",
            {"host": "2001:db8::1"},
            ("ping", "-c", "4", "2001:db8::1"),
            "ping -c 4 2001:db8::1",
        ),
        (
            "curl",
            {"operation": "http_head", "url": "https://example.com"},
            ("curl", "-I", "https://example.com"),
            "curl -I https://example.com",
        ),
        ("dig", {"domain": "example.com"}, ("dig", "example.com"), "dig example.com"),
        (
            "nslookup",
            {"domain": "example.com"},
            ("nslookup", "example.com"),
            "nslookup example.com",
        ),
        (
            "tar",
            {"operation": "list", "archive_path": "archive.tar"},
            ("tar", "-tf", "archive.tar"),
            "tar -tf archive.tar",
        ),
        (
            "unzip",
            {"operation": "list", "archive_path": "archive.zip"},
            ("unzip", "-l", "archive.zip"),
            "unzip -l archive.zip",
        ),
        (
            "tar",
            {
                "operation": "create_tar_gz",
                "archive_path": "backup.tar.gz",
                "source_paths": ["src", "README.md"],
            },
            ("tar", "-czf", "backup.tar.gz", "src", "README.md"),
            "tar -czf backup.tar.gz src README.md",
        ),
        (
            "zip",
            {
                "operation": "create_zip",
                "archive_path": "backup.zip",
                "source_paths": ["src", "README.md"],
            },
            ("zip", "-r", "backup.zip", "src", "README.md"),
            "zip -r backup.zip src README.md",
        ),
    ],
)
def test_render_structured_command(
    command_family: str,
    arguments: dict[str, object],
    expected_argv: tuple[str, ...],
    expected_command: str,
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
            {
                "source": "src.txt",
                "destination": "dest.txt",
                "recursive": False,
                "preserve": True,
                "no_clobber": True,
            },
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
            "git status --short",
            "git",
            {"operation": "status_short", "count": 10},
        ),
        (
            "git log --oneline -n 3",
            "git",
            {"operation": "log_oneline", "count": 3},
        ),
        ("ping -c 4 example.com", "ping", {"host": "example.com", "count": 4}),
        (
            "curl -I https://example.com",
            "curl",
            {"operation": "http_head", "url": "https://example.com"},
        ),
        ("dig example.com", "dig", {"domain": "example.com"}),
        ("nslookup example.com", "nslookup", {"domain": "example.com"}),
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
        ("clear", "clear", {}),
        ("whoami", "whoami", {}),
        (
            "uname -sr",
            "uname",
            {
                "all": False,
                "kernel_name": True,
                "node_name": False,
                "kernel_release": True,
                "kernel_version": False,
                "machine": False,
            },
        ),
        ("which -a python3", "which", {"commands": ["python3"], "all_matches": True}),
        ("env PATH", "env", {"variable": "PATH"}),
        ("df -h .", "df", {"path": ".", "human_readable": True}),
        ("df", "df", {"path": None, "human_readable": False}),
        (
            "ps -Af -u root",
            "ps",
            {"all_processes": True, "full_format": True, "user": "root", "pid": None},
        ),
        (
            "pgrep -fl python",
            "pgrep",
            {"pattern": "python", "full_command": True, "list_names": True, "user": None},
        ),
        (
            "lsof -anP -c python .",
            "lsof",
            {
                "path": ".",
                "pid": None,
                "command_prefix": "python",
                "and_selectors": True,
                "no_dns": True,
                "no_port_names": True,
            },
        ),
        (
            "wc -lc README.md",
            "wc",
            {"paths": ["README.md"], "lines": True, "words": False, "bytes": True},
        ),
        (
            "sort -ru README.md",
            "sort",
            {"path": "README.md", "numeric": False, "reverse": True, "unique": True},
        ),
        (
            "uniq -c README.md",
            "uniq",
            {"path": "README.md", "count": True, "repeated_only": False, "unique_only": False},
        ),
        (
            "tar -tf archive.tar",
            "tar",
            {"operation": "list", "archive_path": "archive.tar"},
        ),
        (
            "tar -czf backup.tar.gz src README.md",
            "tar",
            {
                "operation": "create_tar_gz",
                "archive_path": "backup.tar.gz",
                "source_paths": ["src", "README.md"],
            },
        ),
        (
            "unzip -l backup.zip",
            "unzip",
            {"operation": "list", "archive_path": "backup.zip"},
        ),
        (
            "zip -r backup.zip src README.md",
            "zip",
            {
                "operation": "create_zip",
                "archive_path": "backup.zip",
                "source_paths": ["src", "README.md"],
            },
        ),
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


def test_render_structured_command_rejects_missing_archive_path() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("tar", {"operation": "list"})


def test_render_structured_archive_creation_rejects_missing_source_paths() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "tar", {"operation": "create_tar_gz", "archive_path": "backup.tar.gz"}
        )


def test_render_structured_archive_creation_rejects_empty_source_paths() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "zip",
            {
                "operation": "create_zip",
                "archive_path": "backup.zip",
                "source_paths": [],
            },
        )


def test_render_structured_command_rejects_unsafe_archive_path() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "unzip", {"operation": "list", "archive_path": "backup.zip; rm -rf tmp"}
        )


@pytest.mark.parametrize(
    ("command_family", "arguments"),
    [
        ("ping", {"host": "https://example.com", "count": 4}),
        ("ping", {"host": "example.com;rm", "count": 4}),
        ("ping", {"host": "example.com", "count": 11}),
        ("curl", {"operation": "http_head", "url": "file:///tmp/data"}),
        ("curl", {"operation": "http_head", "url": "https://user:token@example.com"}),
        ("curl", {"operation": "post", "url": "https://example.com"}),
        ("dig", {"domain": "https://example.com"}),
        ("dig", {"domain": "example.com/path"}),
        ("nslookup", {"domain": "example.com;rm"}),
    ],
)
def test_render_structured_network_rejects_invalid_arguments(
    command_family: str, arguments: dict[str, object]
) -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(command_family, arguments)


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


def test_render_structured_command_rejects_conflicting_uniq_flags() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "uniq",
            {"path": "README.md", "count": False, "repeated_only": True, "unique_only": True},
        )


def test_parse_raw_command_as_structured_returns_none_for_unsupported_stat_format_variant() -> None:
    assert parse_raw_command_as_structured("stat -f '%z' README.md") is None


def test_render_structured_tar_extraction_exact_argv() -> None:
    rendered = render_structured_command(
        "tar",
        {
            "operation": "extract_tar",
            "archive_path": "archive.tar",
            "destination_path": "out",
        },
    )

    assert rendered.argv == ("tar", "-xf", "archive.tar", "-C", "out")
    assert rendered.command == "tar -xf archive.tar -C out"


def test_render_structured_zip_extraction_exact_argv() -> None:
    rendered = render_structured_command(
        "unzip",
        {
            "operation": "extract_zip",
            "archive_path": "archive.zip",
            "destination_path": "restore",
        },
    )

    assert rendered.argv == ("unzip", "archive.zip", "-d", "restore")
    assert rendered.command == "unzip archive.zip -d restore"


def test_structured_archive_extraction_requires_destination() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "tar",
            {"operation": "extract_tar", "archive_path": "archive.tar"},
        )


def test_structured_archive_extraction_rejects_root_destination() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "unzip",
            {
                "operation": "extract_zip",
                "archive_path": "archive.zip",
                "destination_path": "/",
            },
        )


def test_structured_archive_extraction_rejects_shell_tokens_in_destination() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "tar",
            {
                "operation": "extract_tar",
                "archive_path": "archive.tar",
                "destination_path": "out; rm -rf /",
            },
        )


@pytest.mark.parametrize("source_path", ["/", ".", "~", "*", "src/*.py", "src; rm -rf tmp"])
def test_structured_archive_creation_rejects_unsafe_source_paths(source_path: str) -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command(
            "zip",
            {
                "operation": "create_zip",
                "archive_path": "backup.zip",
                "source_paths": [source_path],
            },
        )


@pytest.mark.parametrize(
    "command",
    [
        "cp src.txt",
        "clear now",
        "mv -z old.txt new.txt",
        "du -d nope .",
        "stat",
        "head -n 3",
        "tail -n 1",
        "grep -n TODO",
        "cat -n README.md",
        "open -Z .",
        "file",
        "which",
        "env",
        "env PATH HOME",
        "df . /tmp",
        "ps -z",
        "pgrep -z python",
        "lsof -x",
        "wc -z README.md",
        "sort",
        "tar --extract -f archive.tar",
        "unzip -o archive.zip",
        "zip backup.zip file.txt",
        "zip -e backup.zip file.txt",
    ],
)
def test_parse_raw_command_as_structured_rejects_invalid_variants(command: str) -> None:
    assert parse_raw_command_as_structured(command) is None


def test_parse_raw_command_as_structured_accepts_guarded_archive_extraction() -> None:
    assert parse_raw_command_as_structured("tar -xf archive.tar -C out") == (
        "tar",
        {
            "operation": "extract_tar",
            "archive_path": "archive.tar",
            "destination_path": "out",
        },
    )
    assert parse_raw_command_as_structured("unzip archive.zip -d restore") == (
        "unzip",
        {
            "operation": "extract_zip",
            "archive_path": "archive.zip",
            "destination_path": "restore",
        },
    )


def test_parse_raw_command_as_structured_raises_for_disallowed_open_url_target() -> None:
    with pytest.raises(StructuredCommandError):
        parse_raw_command_as_structured("open https://example.com")


def test_parse_raw_command_as_structured_raises_for_conflicting_uniq_flags() -> None:
    with pytest.raises(StructuredCommandError):
        parse_raw_command_as_structured("uniq -du README.md")


def test_project_health_schema_accepts_curated_operation_but_renderer_is_not_implemented() -> None:
    with pytest.raises(StructuredCommandError, match="Structured proposals are not supported"):
        render_structured_command("project_health", {"operation": "run_tests"})


def test_project_health_schema_does_not_validate_operations_before_renderer() -> None:
    with pytest.raises(StructuredCommandError, match="Structured proposals are not supported"):
        render_structured_command("project_health", {"operation": "poetry_run_anything"})

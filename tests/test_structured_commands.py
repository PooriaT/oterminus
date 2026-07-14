import shlex

import pytest

from oterminus.path_utils import expand_user_path
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
        "tree",
        "pwd",
        "clear",
        "whoami",
        "uname",
        "which",
        "env",
        "man",
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
        "project_health",
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
        ("tree", {}, ("tree", "."), "tree ."),
        (
            "tree",
            {"path": "src", "max_depth": 3, "show_hidden": True, "directories_only": True},
            ("tree", "-a", "-d", "-L", "3", "src"),
            "tree -a -d -L 3 src",
        ),
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
        ("man", {"topic": "ls"}, ("man", "ls"), "man ls"),
        ("man", {"section": "1", "topic": "ls"}, ("man", "1", "ls"), "man 1 ls"),
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
        (
            "project_health",
            {"operation": "run_tests"},
            ("poetry", "run", "pytest"),
            "poetry run pytest",
        ),
        (
            "project_health",
            {"operation": "lint_check"},
            ("poetry", "run", "ruff", "check", "."),
            "poetry run ruff check .",
        ),
        (
            "project_health",
            {"operation": "format_check"},
            ("poetry", "run", "ruff", "format", "--check", "."),
            "poetry run ruff format --check .",
        ),
        (
            "project_health",
            {"operation": "build_docs"},
            ("npm", "--prefix", "website", "run", "build"),
            "npm --prefix website run build",
        ),
        (
            "project_health",
            {"operation": "run_evals"},
            ("poetry", "run", "oterminus-evals"),
            "poetry run oterminus-evals",
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


def test_expand_user_path_only_expands_current_user_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert expand_user_path("~") == str(tmp_path)
    assert expand_user_path("~/Downloads") == str(tmp_path / "Downloads")
    assert expand_user_path("~//etc/passwd") == f"{tmp_path}//etc/passwd"
    assert expand_user_path(".") == "."
    assert expand_user_path("src") == "src"
    assert expand_user_path("/tmp") == "/tmp"
    assert expand_user_path("~otheruser") == "~otheruser"
    assert expand_user_path("$HOME/file") == "$HOME/file"
    assert expand_user_path("${HOME}/file") == "${HOME}/file"
    assert expand_user_path("*") == "*"


def test_render_ls_expands_current_user_home_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    rendered = render_structured_command("ls", {"path": "~/Downloads", "all": True})

    expected_path = str(tmp_path / "Downloads")
    assert rendered.argv == ("ls", "-a", expected_path)
    assert rendered.command == f"ls -a {shlex.quote(expected_path)}"


@pytest.mark.parametrize(
    ("command_family", "arguments", "expected_argv"),
    [
        ("du", {"path": "~", "human_readable": True}, ("du", "-h", "{home}")),
        ("cat", {"paths": ["~/file.txt"]}, ("cat", "{home}/file.txt")),
        ("grep", {"pattern": "TODO", "paths": ["~/project"]}, ("grep", "TODO", "{home}/project")),
        (
            "tar",
            {
                "operation": "extract_tar",
                "archive_path": "~/archive.tar",
                "destination_path": "~/out",
            },
            ("tar", "-xf", "{home}/archive.tar", "-C", "{home}/out"),
        ),
    ],
)
def test_render_structured_command_expands_path_fields(
    monkeypatch,
    tmp_path,
    command_family: str,
    arguments: dict[str, object],
    expected_argv: tuple[str, ...],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    rendered = render_structured_command(command_family, arguments)

    assert rendered.argv == tuple(arg.replace("{home}", str(tmp_path)) for arg in expected_argv)


@pytest.mark.parametrize(
    ("command_family", "arguments", "expected_argv"),
    [
        ("ls", {"path": "~/Downloads"}, ("ls", "{home}/Downloads")),
        ("mkdir", {"path": "~/new-dir"}, ("mkdir", "{home}/new-dir")),
        ("chmod", {"path": "~/run.sh", "mode": "755"}, ("chmod", "755", "{home}/run.sh")),
        ("find", {"path": "~/src", "name": "*.py"}, ("find", "{home}/src", "-name", "*.py")),
        (
            "cp",
            {"source": "~/in.txt", "destination": "~/out.txt"},
            ("cp", "{home}/in.txt", "{home}/out.txt"),
        ),
        (
            "mv",
            {"source": "~/old.txt", "destination": "~/new.txt"},
            ("mv", "{home}/old.txt", "{home}/new.txt"),
        ),
        ("du", {"path": "~"}, ("du", "{home}")),
        ("df", {"path": "~/Downloads"}, ("df", "{home}/Downloads")),
        ("stat", {"path": "~/README.md"}, ("stat", "{home}/README.md")),
        ("head", {"paths": ["~/a.txt", "~/b.txt"]}, ("head", "{home}/a.txt", "{home}/b.txt")),
        ("tail", {"paths": ["~/a.txt", "~/b.txt"]}, ("tail", "{home}/a.txt", "{home}/b.txt")),
        ("grep", {"pattern": "~", "paths": ["~/project"]}, ("grep", "~", "{home}/project")),
        ("cat", {"paths": ["~/file.txt"]}, ("cat", "{home}/file.txt")),
        ("open", {"path": "~/Downloads"}, ("open", "{home}/Downloads")),
        ("file", {"paths": ["~/file.txt"]}, ("file", "{home}/file.txt")),
        ("lsof", {"path": "~/socket"}, ("lsof", "{home}/socket")),
        ("wc", {"paths": ["~/file.txt"]}, ("wc", "{home}/file.txt")),
        ("sort", {"path": "~/names.txt"}, ("sort", "{home}/names.txt")),
        ("uniq", {"path": "~/names.txt"}, ("uniq", "{home}/names.txt")),
        (
            "tar",
            {"operation": "list", "archive_path": "~/archive.tar"},
            ("tar", "-tf", "{home}/archive.tar"),
        ),
        (
            "unzip",
            {
                "operation": "extract_zip",
                "archive_path": "~/archive.zip",
                "destination_path": "~/restore",
            },
            ("unzip", "{home}/archive.zip", "-d", "{home}/restore"),
        ),
        (
            "zip",
            {
                "operation": "create_zip",
                "archive_path": "~/backup.zip",
                "source_paths": ["src"],
            },
            ("zip", "-r", "{home}/backup.zip", "src"),
        ),
    ],
)
def test_render_structured_command_expands_all_supported_local_path_fields(
    monkeypatch,
    tmp_path,
    command_family: str,
    arguments: dict[str, object],
    expected_argv: tuple[str, ...],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    rendered = render_structured_command(command_family, arguments)

    assert rendered.argv == tuple(arg.replace("{home}", str(tmp_path)) for arg in expected_argv)


@pytest.mark.parametrize(
    ("command_family", "arguments", "literal_value"),
    [
        ("ls", {"path": "~otheruser/file"}, "~otheruser/file"),
        ("cat", {"paths": ["$HOME/file"]}, "$HOME/file"),
        ("cat", {"paths": ["${HOME}/file"]}, "${HOME}/file"),
        ("grep", {"pattern": "~", "paths": ["src"]}, "~"),
    ],
)
def test_render_structured_command_does_not_expand_other_shell_syntax(
    monkeypatch,
    tmp_path,
    command_family: str,
    arguments: dict[str, object],
    literal_value: str,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    rendered = render_structured_command(command_family, arguments)

    assert literal_value in rendered.argv


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
        ("man grep", "man", {"topic": "grep", "section": None}),
        ("man 5 crontab", "man", {"topic": "crontab", "section": "5"}),
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


def test_structured_ls_rendering_stays_typed_and_deterministic() -> None:
    rendered = render_structured_command(
        "ls",
        {"path": ".", "long": True, "human_readable": True, "all": True, "recursive": False},
    )

    assert rendered.argv == ("ls", "-l", "-h", "-a", ".")
    assert rendered.command == "ls -l -h -a ."


def test_structured_ls_rejects_arbitrary_flags() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("ls", {"arbitrary_flags": ["--color=auto"]})


def test_parse_passthrough_only_ls_flags_is_not_structured() -> None:
    assert parse_raw_command_as_structured("ls -ltrh") is None
    assert parse_raw_command_as_structured("ls --color=auto") is None


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"operation": "poetry_run_pytest"},
        {"operation": "run_tests", "command": "poetry run pytest tests"},
        {"operation": "format_write"},
    ],
)
def test_render_structured_project_health_rejects_invalid_arguments(arguments: dict) -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("project_health", arguments)


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


@pytest.mark.parametrize(
    "source_path", ["/", ".", "~", "~/src", "*", "src/*.py", "src; rm -rf tmp"]
)
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
        "man",
        "man --help",
        "man -k ls",
        "man -P cat ls",
        "man --pager=cat ls",
        "man 99 ls",
        "man abc ls",
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


@pytest.mark.parametrize(
    "arguments",
    [
        {"topic": ""},
        {"topic": "-help"},
        {"topic": "./script.sh"},
        {"topic": "/bin/ls"},
        {"topic": "docs/file.md"},
        {"topic": "https://example.com"},
        {"topic": "$(whoami)"},
        {"topic": "ls;whoami"},
        {"topic": "ls", "section": "abc"},
        {"topic": "ls", "section": "99"},
        {"topic": "ls", "section": "-1"},
        {"topic": "ls", "section": "1;whoami"},
        {"topic": "ls", "pager": "cat"},
    ],
)
def test_render_structured_man_rejects_unsafe_arguments(arguments: dict[str, object]) -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("man", arguments)


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


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("run_tests", ("poetry", "run", "pytest")),
        ("lint_check", ("poetry", "run", "ruff", "check", ".")),
        ("format_check", ("poetry", "run", "ruff", "format", "--check", ".")),
        ("build_docs", ("npm", "--prefix", "website", "run", "build")),
        ("run_evals", ("poetry", "run", "oterminus-evals")),
    ],
)
def test_project_health_renders_curated_operations_exactly(
    operation: str, expected: tuple[str, ...]
) -> None:
    rendered = render_structured_command("project_health", {"operation": operation})
    assert rendered.argv == expected


def test_project_health_schema_rejects_unsupported_operations() -> None:
    with pytest.raises(StructuredCommandError, match="operation must be one of"):
        render_structured_command("project_health", {"operation": "poetry_run_anything"})


def test_project_health_schema_rejects_missing_operation() -> None:
    with pytest.raises(StructuredCommandError, match="Field required"):
        render_structured_command("project_health", {})


def test_project_health_schema_rejects_extra_arguments() -> None:
    with pytest.raises(StructuredCommandError, match="Extra inputs are not permitted"):
        render_structured_command(
            "project_health", {"operation": "run_tests", "raw_command": "poetry run pytest"}
        )


def test_structured_tree_expands_home_in_rendering() -> None:
    rendered = render_structured_command(
        "tree",
        {"path": "~/Downloads", "max_depth": 3, "show_hidden": True, "directories_only": False},
    )

    assert rendered.argv == ("tree", "-a", "-L", "3", expand_user_path("~/Downloads"))
    assert rendered.command == shlex.join(rendered.argv)


@pytest.mark.parametrize(
    ("command", "expected_arguments"),
    [
        (
            "tree",
            {"path": ".", "max_depth": None, "show_hidden": False, "directories_only": False},
        ),
        (
            "tree .",
            {"path": ".", "max_depth": None, "show_hidden": False, "directories_only": False},
        ),
        (
            "tree -a .",
            {"path": ".", "max_depth": None, "show_hidden": True, "directories_only": False},
        ),
        (
            "tree -d ~/Downloads",
            {
                "path": "~/Downloads",
                "max_depth": None,
                "show_hidden": False,
                "directories_only": True,
            },
        ),
        (
            "tree -a -d -L 3 .",
            {"path": ".", "max_depth": 3, "show_hidden": True, "directories_only": True},
        ),
        (
            "tree -ad -L 2 src",
            {"path": "src", "max_depth": 2, "show_hidden": True, "directories_only": True},
        ),
    ],
)
def test_parse_raw_command_as_structured_accepts_tree(
    command: str, expected_arguments: dict[str, object]
) -> None:
    assert parse_raw_command_as_structured(command) == ("tree", expected_arguments)


@pytest.mark.parametrize(
    "command",
    [
        "tree path1 path2",
        "tree -L",
        "tree -L 0",
        "tree -L -1",
        "tree -L 999999",
        "tree --help",
        "tree --version",
        "tree -C",
        "tree -H .",
        "tree -I pattern .",
        "tree -o out.txt .",
        "tree https://example.com",
        "tree file:///tmp/x",
        "tree . | less",
        "tree . > tree.txt",
        "tree $(pwd)",
        "tree `pwd`",
        "tree -L3 .",
    ],
)
def test_parse_raw_command_as_structured_rejects_tree_variants(command: str) -> None:
    assert parse_raw_command_as_structured(command) is None


@pytest.mark.parametrize(
    "arguments",
    [
        {"path": "https://example.com"},
        {"path": "$HOME/Downloads"},
        {"path": "~otheruser"},
        {"path": "src", "max_depth": 0},
        {"path": "src", "max_depth": 21},
        {"path": "src", "ignore_pattern": "*.py"},
    ],
)
def test_render_structured_tree_rejects_invalid_arguments(arguments: dict[str, object]) -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("tree", arguments)


def test_touch_is_supported_structured_family() -> None:
    assert supports_structured_family("touch") is True


@pytest.mark.parametrize(
    ("arguments", "expected_argv"),
    [
        ({"path": "notes.txt"}, ("touch", "notes.txt")),
        ({"path": "./notes.txt"}, ("touch", "./notes.txt")),
        ({"path": "~/Documents/notes.txt"}, ("touch", expand_user_path("~/Documents/notes.txt"))),
    ],
)
def test_render_structured_touch(arguments: dict[str, str], expected_argv: tuple[str, ...]) -> None:
    rendered = render_structured_command("touch", arguments)
    assert rendered.argv == expected_argv
    assert shlex.split(rendered.command) == list(expected_argv)


@pytest.mark.parametrize(
    ("command", "expected_arguments"),
    [
        ("touch notes.txt", {"path": "notes.txt"}),
        ("touch ./notes.txt", {"path": "./notes.txt"}),
        ("touch ~/Documents/notes.txt", {"path": "~/Documents/notes.txt"}),
    ],
)
def test_parse_raw_command_as_structured_accepts_touch(
    command: str, expected_arguments: dict[str, str]
) -> None:
    assert parse_raw_command_as_structured(command) == ("touch", expected_arguments)


@pytest.mark.parametrize(
    "command",
    [
        "touch",
        "touch file1 file2",
        "touch -c notes.txt",
        "touch -a notes.txt",
        "touch -m notes.txt",
        "touch -t 202601010000 notes.txt",
        "touch -r source.txt target.txt",
        "touch -- notes.txt",
        "touch /",
        "touch ~",
        "touch .",
        "touch ..",
        "touch /bin",
        "touch /dev",
        "touch /etc",
        "touch /lib",
        "touch /private",
        "touch /sbin",
        "touch /usr",
        "touch /var",
        "touch https://example.com/file",
        "touch file:///tmp/file",
        "touch '$HOME/file'",
        "touch '${HOME}/file'",
        "touch '~otheruser/file'",
        "touch '*.txt'",
        "touch '$(pwd)'",
        "touch '`pwd`'",
        "touch 'notes.txt && echo done'",
        "touch 'bad\nname'",
    ],
)
def test_parse_raw_command_as_structured_rejects_touch_variants(command: str) -> None:
    assert parse_raw_command_as_structured(command) is None


def test_touch_structured_rejects_missing_path_and_extra_fields() -> None:
    with pytest.raises(StructuredCommandError):
        render_structured_command("touch", {})
    with pytest.raises(StructuredCommandError):
        render_structured_command("touch", {"path": "notes.txt", "parents": False})

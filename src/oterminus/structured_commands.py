from __future__ import annotations

import ipaddress
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class StructuredCommandError(ValueError):
    pass


class _StructuredArgumentsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


def _looks_like_url_target(value: str) -> bool:
    lowered = value.lower()
    return "://" in lowered or lowered.startswith(("mailto:",))


def _validate_path(value: str, *, allow_url_targets: bool = False) -> str:
    if value.startswith("-"):
        raise ValueError("path cannot start with '-'.")
    if not allow_url_targets and _looks_like_url_target(value):
        raise ValueError("path must refer to a local filesystem target.")
    return value


def _validate_archive_path(value: str) -> str:
    value = _validate_path(value, allow_url_targets=False)
    blocked_fragments = ("$(", "`", "\n", "\r", "\x00")
    if any(fragment in value for fragment in blocked_fragments):
        raise ValueError("archive_path cannot contain command substitution or control characters.")
    blocked_operator_fragments = ("&&", "||", ";", "|", "<", ">", "&")
    if any(fragment in value for fragment in blocked_operator_fragments):
        raise ValueError("archive_path cannot contain shell operators.")
    if "*" in value or "?" in value:
        raise ValueError("archive_path cannot contain wildcard characters.")
    return value


def _validate_archive_destination_path(value: str) -> str:
    value = _validate_path(value, allow_url_targets=False)
    blocked_fragments = ("$(", "`", "\n", "\r", "\x00")
    if any(fragment in value for fragment in blocked_fragments):
        raise ValueError(
            "destination_path cannot contain command substitution or control characters."
        )
    blocked_operator_fragments = ("&&", "||", ";", "|", "<", ">", "&")
    if any(fragment in value for fragment in blocked_operator_fragments):
        raise ValueError("destination_path cannot contain shell operators.")
    if value == "/":
        raise ValueError("destination_path cannot be '/'.")
    if value in {"/bin", "/dev", "/etc", "/lib", "/private", "/sbin", "/usr", "/var"}:
        raise ValueError("destination_path cannot be a system root.")
    return value


def _validate_archive_source_path(value: str) -> str:
    value = _validate_path(value, allow_url_targets=False)
    blocked_fragments = ("$(", "`", "\n", "\r", "\x00")
    if any(fragment in value for fragment in blocked_fragments):
        raise ValueError("source_paths cannot contain command substitution or control characters.")
    blocked_operator_fragments = ("&&", "||", ";", "|", "<", ">", "&")
    if any(fragment in value for fragment in blocked_operator_fragments):
        raise ValueError("source_paths cannot contain shell operators.")
    blocked_wildcard_fragments = ("*", "?", "[", "]", "{", "}")
    if any(fragment in value for fragment in blocked_wildcard_fragments):
        raise ValueError("source_paths cannot contain wildcard characters.")
    if value in {
        ".",
        "..",
        "/",
        "~",
        "$HOME",
        "${HOME}",
        "/bin",
        "/dev",
        "/etc",
        "/home",
        "/lib",
        "/private",
        "/root",
        "/sbin",
        "/Users",
        "/usr",
        "/var",
    }:
        raise ValueError("source_paths cannot include broad or unsafe roots.")
    if value.rstrip("/") == str(Path.home()).rstrip("/"):
        raise ValueError("source_paths cannot include broad home directory targets.")
    if value.startswith("~/") or value.startswith("$HOME/") or value.startswith("${HOME}/"):
        raise ValueError("source_paths cannot include broad home directory targets.")
    return value


def _validate_archive_source_paths(values: list[str] | None) -> list[str] | None:
    if values is None:
        return values
    return [_validate_archive_source_path(value) for value in values]


def _validate_paths(values: list[str], *, allow_url_targets: bool = False) -> list[str]:
    return [_validate_path(value, allow_url_targets=allow_url_targets) for value in values]


_BLOCKED_ARGUMENT_FRAGMENTS = ("$(", "`", "\n", "\r", "\x00")
_BLOCKED_SHELL_OPERATOR_FRAGMENTS = ("&&", "||", ";", "|", "<", ">")
_HOSTNAME_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _has_blocked_network_fragment(value: str) -> bool:
    return any(fragment in value for fragment in _BLOCKED_ARGUMENT_FRAGMENTS) or any(
        fragment in value for fragment in _BLOCKED_SHELL_OPERATOR_FRAGMENTS
    )


def _is_valid_hostname(value: str) -> bool:
    if not value or len(value) > 253:
        return False
    if value.endswith("."):
        value = value[:-1]
    labels = value.split(".")
    return all(_HOSTNAME_LABEL_RE.fullmatch(label) is not None for label in labels)


def is_valid_network_host(value: str) -> bool:
    if not value or value.startswith("-") or _has_blocked_network_fragment(value):
        return False
    if any(char.isspace() for char in value):
        return False
    if "://" in value or "/" in value:
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return _is_valid_hostname(value)
    return True


def is_valid_network_domain(value: str) -> bool:
    if not value or value.startswith("-") or _has_blocked_network_fragment(value):
        return False
    if any(char.isspace() for char in value):
        return False
    if "://" in value or "/" in value or ":" in value:
        return False
    return _is_valid_hostname(value)


def is_valid_http_head_url(value: str) -> bool:
    if not value or _has_blocked_network_fragment(value):
        return False
    if any(char.isspace() for char in value):
        return False
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    return is_valid_network_host(parsed.hostname)


def _validate_network_host(value: str) -> str:
    if not is_valid_network_host(value):
        raise ValueError("host must be a hostname, domain, IPv4 address, or IPv6 address.")
    return value


def _validate_network_domain(value: str) -> str:
    if not is_valid_network_domain(value):
        raise ValueError("domain must be a conservative hostname or domain.")
    return value


def _validate_http_head_url(value: str) -> str:
    if not is_valid_http_head_url(value):
        raise ValueError("url must be an http:// or https:// URL without credentials.")
    return value


class LsArguments(_StructuredArgumentsModel):
    path: str = Field(default=".", min_length=1)
    long: bool = False
    human_readable: bool = False
    all: bool = False
    recursive: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)

    @field_validator("human_readable")
    @classmethod
    def validate_human_readable(cls, value: bool, info: Any) -> bool:
        if value and not info.data.get("long", False):
            raise ValueError("human_readable requires long=true.")
        return value


class PwdArguments(_StructuredArgumentsModel):
    pass


class ClearArguments(_StructuredArgumentsModel):
    pass


class WhoamiArguments(_StructuredArgumentsModel):
    pass


class UnameArguments(_StructuredArgumentsModel):
    all: bool = False
    kernel_name: bool = False
    node_name: bool = False
    kernel_release: bool = False
    kernel_version: bool = False
    machine: bool = False

    @model_validator(mode="after")
    def validate_shape(self) -> UnameArguments:
        if self.all and any(
            (
                self.kernel_name,
                self.node_name,
                self.kernel_release,
                self.kernel_version,
                self.machine,
            )
        ):
            raise ValueError("all=true cannot be combined with specific uname fields.")
        return self


class WhichArguments(_StructuredArgumentsModel):
    commands: list[str] = Field(min_length=1)
    all_matches: bool = False

    @field_validator("commands")
    @classmethod
    def validate_commands(cls, value: list[str]) -> list[str]:
        if any(command.startswith("-") for command in value):
            raise ValueError("commands cannot start with '-'.")
        return value


class EnvArguments(_StructuredArgumentsModel):
    variable: str = Field(min_length=1)

    @field_validator("variable")
    @classmethod
    def validate_variable(cls, value: str) -> str:
        if value.startswith("-"):
            raise ValueError("variable cannot start with '-'.")
        return value


class MkdirArguments(_StructuredArgumentsModel):
    path: str = Field(min_length=1)
    parents: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)


class ChmodArguments(_StructuredArgumentsModel):
    path: str = Field(min_length=1)
    mode: str = Field(min_length=3, max_length=4, pattern=r"^[0-7]{3,4}$")

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)


class FindArguments(_StructuredArgumentsModel):
    path: str = Field(default=".", min_length=1)
    name: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)


class CpArguments(_StructuredArgumentsModel):
    source: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    recursive: bool = False
    preserve: bool = False
    no_clobber: bool = False

    @field_validator("source", "destination")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)


class MvArguments(_StructuredArgumentsModel):
    source: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    no_clobber: bool = False

    @field_validator("source", "destination")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)


class DuArguments(_StructuredArgumentsModel):
    path: str = Field(default=".", min_length=1)
    human_readable: bool = False
    summarize: bool = False
    max_depth: int | None = Field(default=None, ge=0)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)

    @model_validator(mode="after")
    def validate_shape(self) -> DuArguments:
        if self.summarize and self.max_depth is not None:
            raise ValueError("max_depth cannot be combined with summarize=true.")
        return self


class DfArguments(_StructuredArgumentsModel):
    path: str | None = None
    human_readable: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_path(value)


class StatArguments(_StructuredArgumentsModel):
    path: str = Field(min_length=1)
    dereference: bool = False
    verbose: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)


class HeadArguments(_StructuredArgumentsModel):
    paths: list[str] = Field(min_length=1)
    lines: int | None = Field(default=None, ge=0)
    bytes: int | None = Field(default=None, ge=0)

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, value: list[str]) -> list[str]:
        return _validate_paths(value)

    @model_validator(mode="after")
    def validate_shape(self) -> HeadArguments:
        if self.lines is not None and self.bytes is not None:
            raise ValueError("lines and bytes are mutually exclusive.")
        return self


class TailArguments(_StructuredArgumentsModel):
    paths: list[str] = Field(min_length=1)
    lines: int | None = Field(default=None, ge=0)
    bytes: int | None = Field(default=None, ge=0)

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, value: list[str]) -> list[str]:
        return _validate_paths(value)

    @model_validator(mode="after")
    def validate_shape(self) -> TailArguments:
        if self.lines is not None and self.bytes is not None:
            raise ValueError("lines and bytes are mutually exclusive.")
        return self


class GrepArguments(_StructuredArgumentsModel):
    pattern: str = Field(min_length=1)
    paths: list[str] = Field(min_length=1)
    ignore_case: bool = False
    line_number: bool = False
    fixed_strings: bool = False
    recursive: bool = False
    files_with_matches: bool = False
    max_count: int | None = Field(default=None, ge=1)

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, value: list[str]) -> list[str]:
        return _validate_paths(value)

    @model_validator(mode="after")
    def validate_shape(self) -> GrepArguments:
        if self.line_number and self.files_with_matches:
            raise ValueError("line_number and files_with_matches cannot both be true.")
        return self


class CatArguments(_StructuredArgumentsModel):
    paths: list[str] = Field(min_length=1)

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, value: list[str]) -> list[str]:
        return _validate_paths(value)


class OpenArguments(_StructuredArgumentsModel):
    path: str = Field(min_length=1)
    reveal: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value, allow_url_targets=False)


class FileArguments(_StructuredArgumentsModel):
    paths: list[str] = Field(min_length=1)
    brief: bool = False

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, value: list[str]) -> list[str]:
        return _validate_paths(value)


class PsArguments(_StructuredArgumentsModel):
    all_processes: bool = False
    full_format: bool = False
    user: str | None = None
    pid: int | None = Field(default=None, ge=1)

    @field_validator("user")
    @classmethod
    def validate_user(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.startswith("-"):
            raise ValueError("user cannot start with '-'.")
        return value


class PgrepArguments(_StructuredArgumentsModel):
    pattern: str = Field(min_length=1)
    full_command: bool = False
    list_names: bool = False
    user: str | None = None

    @field_validator("user")
    @classmethod
    def validate_user(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.startswith("-"):
            raise ValueError("user cannot start with '-'.")
        return value


class LsofArguments(_StructuredArgumentsModel):
    path: str | None = None
    pid: int | None = Field(default=None, ge=1)
    command_prefix: str | None = None
    and_selectors: bool = False
    no_dns: bool = False
    no_port_names: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_path(value)

    @field_validator("command_prefix")
    @classmethod
    def validate_command_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.startswith("-"):
            raise ValueError("command_prefix cannot start with '-'.")
        return value


class WcArguments(_StructuredArgumentsModel):
    paths: list[str] = Field(min_length=1)
    lines: bool = False
    words: bool = False
    bytes: bool = False

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, value: list[str]) -> list[str]:
        return _validate_paths(value)


class SortArguments(_StructuredArgumentsModel):
    path: str = Field(min_length=1)
    numeric: bool = False
    reverse: bool = False
    unique: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)


class GitArguments(_StructuredArgumentsModel):
    operation: str = Field(min_length=1)
    count: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def validate_shape(self) -> GitArguments:
        allowed = {"status_short", "branch_current", "log_oneline", "diff_stat", "diff_name_only"}
        if self.operation not in allowed:
            raise ValueError(
                "operation must be one of: status_short, branch_current, log_oneline, diff_stat, diff_name_only."
            )
        if self.operation != "log_oneline" and self.count != 10:
            raise ValueError("count is only allowed when operation=log_oneline.")
        return self


class PingArguments(_StructuredArgumentsModel):
    host: str = Field(min_length=1)
    count: int = Field(default=4, ge=1, le=10)

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        return _validate_network_host(value)


class CurlArguments(_StructuredArgumentsModel):
    operation: str = Field(default="http_head")
    url: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _validate_http_head_url(value)

    @model_validator(mode="after")
    def validate_shape(self) -> CurlArguments:
        if self.operation != "http_head":
            raise ValueError("operation must be http_head.")
        return self


class DigArguments(_StructuredArgumentsModel):
    domain: str = Field(min_length=1)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return _validate_network_domain(value)


class NslookupArguments(_StructuredArgumentsModel):
    domain: str = Field(min_length=1)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return _validate_network_domain(value)


class TarArguments(_StructuredArgumentsModel):
    operation: str = Field(min_length=1)
    archive_path: str = Field(min_length=1)
    destination_path: str | None = Field(default=None, min_length=1)
    source_paths: list[str] | None = Field(default=None, min_length=1)

    @field_validator("archive_path")
    @classmethod
    def validate_archive_path(cls, value: str) -> str:
        return _validate_archive_path(value)

    @field_validator("destination_path")
    @classmethod
    def validate_destination_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_archive_destination_path(value)

    @field_validator("source_paths")
    @classmethod
    def validate_source_paths(cls, value: list[str] | None) -> list[str] | None:
        return _validate_archive_source_paths(value)

    @model_validator(mode="after")
    def validate_shape(self) -> TarArguments:
        if self.operation == "list":
            if self.destination_path is not None:
                raise ValueError("destination_path is only allowed when operation=extract_tar.")
            if self.source_paths is not None:
                raise ValueError("source_paths is only allowed when operation=create_tar_gz.")
            return self
        if self.operation == "extract_tar":
            if self.destination_path is None:
                raise ValueError("destination_path is required when operation=extract_tar.")
            if self.source_paths is not None:
                raise ValueError("source_paths is only allowed when operation=create_tar_gz.")
            return self
        if self.operation == "create_tar_gz":
            if self.destination_path is not None:
                raise ValueError("destination_path is not allowed when operation=create_tar_gz.")
            if self.source_paths is None:
                raise ValueError("source_paths is required when operation=create_tar_gz.")
            return self
        raise ValueError("operation must be one of: list, extract_tar, create_tar_gz.")
        return self


class UnzipArguments(_StructuredArgumentsModel):
    operation: str = Field(min_length=1)
    archive_path: str = Field(min_length=1)
    destination_path: str | None = Field(default=None, min_length=1)

    @field_validator("archive_path")
    @classmethod
    def validate_archive_path(cls, value: str) -> str:
        return _validate_archive_path(value)

    @field_validator("destination_path")
    @classmethod
    def validate_destination_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_archive_destination_path(value)

    @model_validator(mode="after")
    def validate_shape(self) -> UnzipArguments:
        if self.operation == "list":
            if self.destination_path is not None:
                raise ValueError("destination_path is only allowed when operation=extract_zip.")
            return self
        if self.operation == "extract_zip":
            if self.destination_path is None:
                raise ValueError("destination_path is required when operation=extract_zip.")
            return self
        raise ValueError("operation must be one of: list, extract_zip.")
        return self


class ZipArguments(_StructuredArgumentsModel):
    operation: str = Field(min_length=1)
    archive_path: str = Field(min_length=1)
    source_paths: list[str] = Field(min_length=1)

    @field_validator("archive_path")
    @classmethod
    def validate_archive_path(cls, value: str) -> str:
        return _validate_archive_path(value)

    @field_validator("source_paths")
    @classmethod
    def validate_source_paths(cls, value: list[str]) -> list[str]:
        validated = _validate_archive_source_paths(value)
        assert validated is not None
        return validated

    @model_validator(mode="after")
    def validate_shape(self) -> ZipArguments:
        if self.operation == "create_zip":
            return self
        raise ValueError("operation must be one of: create_zip.")


class ProjectHealthArguments(_StructuredArgumentsModel):
    operation: str = Field(min_length=1)

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, value: str) -> str:
        allowed = {"run_tests", "lint_check", "format_check", "build_docs", "run_evals"}
        if value not in allowed:
            supported = ", ".join(sorted(allowed))
            raise ValueError(f"operation must be one of: {supported}.")
        return value


class UniqArguments(_StructuredArgumentsModel):
    path: str = Field(min_length=1)
    count: bool = False
    repeated_only: bool = False
    unique_only: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_path(value)

    @model_validator(mode="after")
    def validate_shape(self) -> UniqArguments:
        if self.repeated_only and self.unique_only:
            raise ValueError("repeated_only and unique_only are mutually exclusive.")
        return self


STRUCTURED_ARGUMENT_MODELS: dict[str, type[_StructuredArgumentsModel]] = {
    "ls": LsArguments,
    "pwd": PwdArguments,
    "clear": ClearArguments,
    "whoami": WhoamiArguments,
    "uname": UnameArguments,
    "which": WhichArguments,
    "env": EnvArguments,
    "mkdir": MkdirArguments,
    "chmod": ChmodArguments,
    "find": FindArguments,
    "cp": CpArguments,
    "mv": MvArguments,
    "du": DuArguments,
    "df": DfArguments,
    "stat": StatArguments,
    "head": HeadArguments,
    "tail": TailArguments,
    "grep": GrepArguments,
    "cat": CatArguments,
    "open": OpenArguments,
    "file": FileArguments,
    "ps": PsArguments,
    "pgrep": PgrepArguments,
    "lsof": LsofArguments,
    "wc": WcArguments,
    "sort": SortArguments,
    "uniq": UniqArguments,
    "git": GitArguments,
    "ping": PingArguments,
    "curl": CurlArguments,
    "dig": DigArguments,
    "nslookup": NslookupArguments,
    "tar": TarArguments,
    "unzip": UnzipArguments,
    "zip": ZipArguments,
}


@dataclass(frozen=True, slots=True)
class RenderedCommand:
    argv: tuple[str, ...]

    @property
    def command(self) -> str:
        return shlex.join(self.argv)


def supports_structured_family(command_family: str) -> bool:
    return command_family in STRUCTURED_ARGUMENT_MODELS


def parse_raw_command_as_structured(command: str) -> tuple[str, dict[str, Any]] | None:
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    return parse_argv_as_structured(argv)


def parse_argv_as_structured(argv: Sequence[str]) -> tuple[str, dict[str, Any]] | None:
    if not argv:
        return None

    command_family = argv[0]
    operands = list(argv[1:])

    parser = {
        "ls": _parse_ls_argv,
        "pwd": _parse_pwd_argv,
        "clear": _parse_clear_argv,
        "whoami": _parse_whoami_argv,
        "uname": _parse_uname_argv,
        "which": _parse_which_argv,
        "env": _parse_env_argv,
        "mkdir": _parse_mkdir_argv,
        "chmod": _parse_chmod_argv,
        "find": _parse_find_argv,
        "cp": _parse_cp_argv,
        "mv": _parse_mv_argv,
        "du": _parse_du_argv,
        "df": _parse_df_argv,
        "stat": _parse_stat_argv,
        "head": _parse_head_argv,
        "tail": _parse_tail_argv,
        "grep": _parse_grep_argv,
        "cat": _parse_cat_argv,
        "open": _parse_open_argv,
        "file": _parse_file_argv,
        "ps": _parse_ps_argv,
        "pgrep": _parse_pgrep_argv,
        "lsof": _parse_lsof_argv,
        "wc": _parse_wc_argv,
        "sort": _parse_sort_argv,
        "uniq": _parse_uniq_argv,
        "git": _parse_git_argv,
        "ping": _parse_ping_argv,
        "curl": _parse_curl_argv,
        "dig": _parse_dig_argv,
        "nslookup": _parse_nslookup_argv,
        "tar": _parse_tar_argv,
        "unzip": _parse_unzip_argv,
        "zip": _parse_zip_argv,
    }.get(command_family)
    if parser is None:
        return None

    arguments = parser(operands)
    if arguments is None:
        return None

    validated = validate_structured_arguments(command_family, arguments)
    dumped = validated.model_dump()
    if command_family in {"tar", "unzip"} and dumped.get("destination_path") is None:
        dumped.pop("destination_path", None)
    if command_family == "tar" and dumped.get("source_paths") is None:
        dumped.pop("source_paths", None)
    return command_family, dumped


def validate_structured_arguments(
    command_family: str,
    arguments: dict[str, Any] | None,
) -> _StructuredArgumentsModel:
    model = STRUCTURED_ARGUMENT_MODELS.get(command_family)
    if model is None:
        raise StructuredCommandError(
            f"Structured proposals are not supported for command family '{command_family}'."
        )

    try:
        return model.model_validate(arguments or {})
    except ValidationError as exc:
        raise StructuredCommandError(
            f"Invalid structured arguments for '{command_family}': {exc}"
        ) from exc


def render_structured_command(
    command_family: str, arguments: dict[str, Any] | None
) -> RenderedCommand:
    validated = validate_structured_arguments(command_family, arguments)

    if command_family == "ls":
        argv = ["ls"]
        if validated.long:
            argv.append("-l")
        if validated.human_readable:
            argv.append("-h")
        if validated.all:
            argv.append("-a")
        if validated.recursive:
            argv.append("-R")
        argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family == "pwd":
        return RenderedCommand(("pwd",))

    if command_family == "clear":
        return RenderedCommand(("clear",))

    if command_family == "whoami":
        return RenderedCommand(("whoami",))

    if command_family == "uname":
        argv = ["uname"]
        if validated.all:
            argv.append("-a")
        else:
            if validated.kernel_name:
                argv.append("-s")
            if validated.node_name:
                argv.append("-n")
            if validated.kernel_release:
                argv.append("-r")
            if validated.kernel_version:
                argv.append("-v")
            if validated.machine:
                argv.append("-m")
        return RenderedCommand(tuple(argv))

    if command_family == "which":
        argv = ["which"]
        if validated.all_matches:
            argv.append("-a")
        argv.extend(validated.commands)
        return RenderedCommand(tuple(argv))

    if command_family == "env":
        return RenderedCommand(("env", validated.variable))

    if command_family == "mkdir":
        argv = ["mkdir"]
        if validated.parents:
            argv.append("-p")
        argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family == "chmod":
        return RenderedCommand(("chmod", validated.mode, validated.path))

    if command_family == "find":
        return RenderedCommand(("find", validated.path, "-name", validated.name))

    if command_family == "cp":
        argv = ["cp"]
        if validated.recursive:
            argv.append("-R")
        if validated.preserve:
            argv.append("-p")
        if validated.no_clobber:
            argv.append("-n")
        argv.extend((validated.source, validated.destination))
        return RenderedCommand(tuple(argv))

    if command_family == "mv":
        argv = ["mv"]
        if validated.no_clobber:
            argv.append("-n")
        argv.extend((validated.source, validated.destination))
        return RenderedCommand(tuple(argv))

    if command_family == "du":
        argv = ["du"]
        if validated.human_readable:
            argv.append("-h")
        if validated.summarize:
            argv.append("-s")
        if validated.max_depth is not None:
            argv.extend(("-d", str(validated.max_depth)))
        argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family == "df":
        argv = ["df"]
        if validated.human_readable:
            argv.append("-h")
        if validated.path is not None:
            argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family == "stat":
        argv = ["stat"]
        if validated.dereference:
            argv.append("-L")
        if validated.verbose:
            argv.append("-x")
        argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family in {"head", "tail"}:
        argv = [command_family]
        if validated.lines is not None:
            argv.extend(("-n", str(validated.lines)))
        if validated.bytes is not None:
            argv.extend(("-c", str(validated.bytes)))
        argv.extend(validated.paths)
        return RenderedCommand(tuple(argv))

    if command_family == "grep":
        argv = ["grep"]
        if validated.fixed_strings:
            argv.append("-F")
        if validated.ignore_case:
            argv.append("-i")
        if validated.line_number:
            argv.append("-n")
        if validated.files_with_matches:
            argv.append("-l")
        if validated.recursive:
            argv.append("-r")
        if validated.max_count is not None:
            argv.extend(("-m", str(validated.max_count)))
        argv.append(validated.pattern)
        argv.extend(validated.paths)
        return RenderedCommand(tuple(argv))

    if command_family == "cat":
        return RenderedCommand(tuple(["cat", *validated.paths]))

    if command_family == "open":
        argv = ["open"]
        if validated.reveal:
            argv.append("-R")
        argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family == "file":
        argv = ["file"]
        if validated.brief:
            argv.append("-b")
        argv.extend(validated.paths)
        return RenderedCommand(tuple(argv))

    if command_family == "ps":
        argv = ["ps"]
        if validated.all_processes:
            argv.append("-A")
        if validated.full_format:
            argv.append("-f")
        if validated.user is not None:
            argv.extend(("-u", validated.user))
        if validated.pid is not None:
            argv.extend(("-p", str(validated.pid)))
        return RenderedCommand(tuple(argv))

    if command_family == "pgrep":
        argv = ["pgrep"]
        if validated.full_command:
            argv.append("-f")
        if validated.list_names:
            argv.append("-l")
        if validated.user is not None:
            argv.extend(("-u", validated.user))
        argv.append(validated.pattern)
        return RenderedCommand(tuple(argv))

    if command_family == "lsof":
        argv = ["lsof"]
        if validated.and_selectors:
            argv.append("-a")
        if validated.no_dns:
            argv.append("-n")
        if validated.no_port_names:
            argv.append("-P")
        if validated.pid is not None:
            argv.extend(("-p", str(validated.pid)))
        if validated.command_prefix is not None:
            argv.extend(("-c", validated.command_prefix))
        if validated.path is not None:
            argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family == "wc":
        argv = ["wc"]
        if validated.lines:
            argv.append("-l")
        if validated.words:
            argv.append("-w")
        if validated.bytes:
            argv.append("-c")
        argv.extend(validated.paths)
        return RenderedCommand(tuple(argv))

    if command_family == "sort":
        argv = ["sort"]
        if validated.numeric:
            argv.append("-n")
        if validated.reverse:
            argv.append("-r")
        if validated.unique:
            argv.append("-u")
        argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family == "uniq":
        argv = ["uniq"]
        if validated.count:
            argv.append("-c")
        if validated.repeated_only:
            argv.append("-d")
        if validated.unique_only:
            argv.append("-u")
        argv.append(validated.path)
        return RenderedCommand(tuple(argv))

    if command_family == "git":
        if validated.operation == "status_short":
            return RenderedCommand(("git", "status", "--short"))
        if validated.operation == "branch_current":
            return RenderedCommand(("git", "branch", "--show-current"))
        if validated.operation == "log_oneline":
            return RenderedCommand(("git", "log", "--oneline", "-n", str(validated.count)))
        if validated.operation == "diff_stat":
            return RenderedCommand(("git", "diff", "--stat"))
        if validated.operation == "diff_name_only":
            return RenderedCommand(("git", "diff", "--name-only"))

    if command_family == "ping":
        return RenderedCommand(("ping", "-c", str(validated.count), validated.host))

    if command_family == "curl":
        if validated.operation == "http_head":
            return RenderedCommand(("curl", "-I", validated.url))

    if command_family == "dig":
        return RenderedCommand(("dig", validated.domain))

    if command_family == "nslookup":
        return RenderedCommand(("nslookup", validated.domain))

    if command_family == "tar":
        if validated.operation == "list":
            return RenderedCommand(("tar", "-tf", validated.archive_path))
        if validated.operation == "extract_tar":
            return RenderedCommand(
                ("tar", "-xf", validated.archive_path, "-C", validated.destination_path)
            )
        if validated.operation == "create_tar_gz":
            return RenderedCommand(
                tuple(["tar", "-czf", validated.archive_path, *validated.source_paths])
            )

    if command_family == "unzip":
        if validated.operation == "list":
            return RenderedCommand(("unzip", "-l", validated.archive_path))
        if validated.operation == "extract_zip":
            return RenderedCommand(
                ("unzip", validated.archive_path, "-d", validated.destination_path)
            )

    if command_family == "zip":
        if validated.operation == "create_zip":
            return RenderedCommand(
                tuple(["zip", "-r", validated.archive_path, *validated.source_paths])
            )

    raise StructuredCommandError(
        f"Structured proposals are not supported for command family '{command_family}'."
    )


def _parse_ls_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {
        "path": ".",
        "long": False,
        "human_readable": False,
        "all": False,
        "recursive": False,
    }
    path: str | None = None

    for operand in operands:
        if operand.startswith("-") and operand != "-":
            flags = _expand_short_flag_cluster(operand, {"l", "h", "a", "R"})
            if flags is None:
                return None
            for flag in flags:
                if flag == "-l":
                    arguments["long"] = True
                elif flag == "-h":
                    arguments["human_readable"] = True
                elif flag == "-a":
                    arguments["all"] = True
                elif flag == "-R":
                    arguments["recursive"] = True
            continue

        if path is not None:
            return None
        path = operand

    if path is not None:
        arguments["path"] = path
    return arguments


def _parse_pwd_argv(operands: list[str]) -> dict[str, Any] | None:
    return {} if not operands else None


def _parse_clear_argv(operands: list[str]) -> dict[str, Any] | None:
    return {} if not operands else None


def _parse_whoami_argv(operands: list[str]) -> dict[str, Any] | None:
    return {} if not operands else None


def _parse_uname_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {
        "all": False,
        "kernel_name": False,
        "node_name": False,
        "kernel_release": False,
        "kernel_version": False,
        "machine": False,
    }
    for operand in operands:
        if operand.startswith("-") and operand != "-":
            flags = _expand_short_flag_cluster(operand, {"a", "s", "n", "r", "v", "m"})
            if flags is None:
                return None
            for flag in flags:
                if flag == "-a":
                    arguments["all"] = True
                elif flag == "-s":
                    arguments["kernel_name"] = True
                elif flag == "-n":
                    arguments["node_name"] = True
                elif flag == "-r":
                    arguments["kernel_release"] = True
                elif flag == "-v":
                    arguments["kernel_version"] = True
                elif flag == "-m":
                    arguments["machine"] = True
            continue
        return None
    return arguments


def _parse_which_argv(operands: list[str]) -> dict[str, Any] | None:
    all_matches = False
    commands: list[str] = []
    for operand in operands:
        if operand == "-a":
            all_matches = True
            continue
        if operand.startswith("-"):
            return None
        commands.append(operand)
    if not commands:
        return None
    return {"commands": commands, "all_matches": all_matches}


def _parse_env_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) != 1:
        return None
    if operands[0].startswith("-"):
        return None
    return {"variable": operands[0]}


def _parse_mkdir_argv(operands: list[str]) -> dict[str, Any] | None:
    parents = False
    path: str | None = None

    for operand in operands:
        if operand == "-p":
            parents = True
            continue
        if operand.startswith("-"):
            return None
        if path is not None:
            return None
        path = operand

    if path is None:
        return None
    return {"path": path, "parents": parents}


def _parse_chmod_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) != 2:
        return None
    mode, path = operands
    if not mode.isdigit():
        return None
    return {"path": path, "mode": mode}


def _parse_find_argv(operands: list[str]) -> dict[str, Any] | None:
    if not operands:
        return None

    path = "."
    remaining = operands
    if operands[0] != "-name":
        path = operands[0]
        remaining = operands[1:]

    if len(remaining) != 2 or remaining[0] != "-name":
        return None
    return {"path": path, "name": remaining[1]}


def _parse_cp_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {
        "recursive": False,
        "preserve": False,
        "no_clobber": False,
    }
    paths: list[str] = []

    for operand in operands:
        flags = (
            _expand_short_flag_cluster(operand, {"R", "p", "n"})
            if operand.startswith("-")
            else None
        )
        if flags is not None:
            for flag in flags:
                if flag == "-R":
                    arguments["recursive"] = True
                elif flag == "-p":
                    arguments["preserve"] = True
                elif flag == "-n":
                    arguments["no_clobber"] = True
            continue
        if operand.startswith("-"):
            return None
        paths.append(operand)

    if len(paths) != 2:
        return None
    arguments["source"] = paths[0]
    arguments["destination"] = paths[1]
    return arguments


def _parse_mv_argv(operands: list[str]) -> dict[str, Any] | None:
    no_clobber = False
    paths: list[str] = []

    for operand in operands:
        if operand == "-n":
            no_clobber = True
            continue
        if operand.startswith("-"):
            return None
        paths.append(operand)

    if len(paths) != 2:
        return None
    return {"source": paths[0], "destination": paths[1], "no_clobber": no_clobber}


def _parse_du_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {
        "path": ".",
        "human_readable": False,
        "summarize": False,
        "max_depth": None,
    }
    path: str | None = None
    index = 0

    while index < len(operands):
        operand = operands[index]
        if operand.startswith("-") and operand != "-":
            if operand in {"-d"}:
                if index + 1 >= len(operands):
                    return None
                try:
                    arguments["max_depth"] = int(operands[index + 1])
                except ValueError:
                    return None
                index += 2
                continue

            flags = _expand_short_flag_cluster(operand, {"h", "s"})
            if flags is None:
                return None
            for flag in flags:
                if flag == "-h":
                    arguments["human_readable"] = True
                elif flag == "-s":
                    arguments["summarize"] = True
            index += 1
            continue

        if path is not None:
            return None
        path = operand
        index += 1

    if path is not None:
        arguments["path"] = path
    return arguments


def _parse_df_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {"path": None, "human_readable": False}
    path: str | None = None
    for operand in operands:
        if operand == "-h":
            arguments["human_readable"] = True
            continue
        if operand.startswith("-"):
            return None
        if path is not None:
            return None
        path = operand
    arguments["path"] = path
    return arguments


def _parse_stat_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {"dereference": False, "verbose": False}
    path: str | None = None

    for operand in operands:
        if operand.startswith("-") and operand != "-":
            flags = _expand_short_flag_cluster(operand, {"L", "x"})
            if flags is None:
                return None
            for flag in flags:
                if flag == "-L":
                    arguments["dereference"] = True
                elif flag == "-x":
                    arguments["verbose"] = True
            continue

        if path is not None:
            return None
        path = operand

    if path is None:
        return None
    arguments["path"] = path
    return arguments


def _parse_head_argv(operands: list[str]) -> dict[str, Any] | None:
    return _parse_head_tail_argv(operands)


def _parse_tail_argv(operands: list[str]) -> dict[str, Any] | None:
    return _parse_head_tail_argv(operands)


def _parse_head_tail_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {"lines": None, "bytes": None}
    paths: list[str] = []
    index = 0

    while index < len(operands):
        operand = operands[index]
        if operand == "-n" or operand == "-c":
            if index + 1 >= len(operands):
                return None
            try:
                value = int(operands[index + 1])
            except ValueError:
                return None
            key = "lines" if operand == "-n" else "bytes"
            if arguments[key] is not None:
                return None
            arguments[key] = value
            index += 2
            continue

        inline = _parse_inline_numeric_flag(operand, {"-n": "lines", "-c": "bytes"})
        if inline is not None:
            key, value = inline
            if arguments[key] is not None:
                return None
            arguments[key] = value
            index += 1
            continue

        if operand.startswith("-"):
            return None

        paths.append(operand)
        index += 1

    if not paths:
        return None
    arguments["paths"] = paths
    return arguments


def _parse_grep_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {
        "ignore_case": False,
        "line_number": False,
        "fixed_strings": False,
        "recursive": False,
        "files_with_matches": False,
        "max_count": None,
    }
    pattern: str | None = None
    paths: list[str] = []
    index = 0

    while index < len(operands):
        operand = operands[index]
        if pattern is None and operand.startswith("-") and operand != "-":
            if operand == "-m":
                if index + 1 >= len(operands):
                    return None
                try:
                    arguments["max_count"] = int(operands[index + 1])
                except ValueError:
                    return None
                index += 2
                continue

            inline = _parse_inline_numeric_flag(operand, {"-m": "max_count"})
            if inline is not None:
                key, value = inline
                arguments[key] = value
                index += 1
                continue

            flags = _expand_short_flag_cluster(operand, {"F", "i", "n", "r", "R", "l"})
            if flags is None:
                return None
            for flag in flags:
                if flag == "-F":
                    arguments["fixed_strings"] = True
                elif flag == "-i":
                    arguments["ignore_case"] = True
                elif flag == "-n":
                    arguments["line_number"] = True
                elif flag in {"-r", "-R"}:
                    arguments["recursive"] = True
                elif flag == "-l":
                    arguments["files_with_matches"] = True
            index += 1
            continue

        if pattern is None:
            pattern = operand
        else:
            paths.append(operand)
        index += 1

    if pattern is None or not paths:
        return None
    arguments["pattern"] = pattern
    arguments["paths"] = paths
    return arguments


def _parse_cat_argv(operands: list[str]) -> dict[str, Any] | None:
    if not operands or any(operand.startswith("-") for operand in operands):
        return None
    return {"paths": operands}


def _parse_open_argv(operands: list[str]) -> dict[str, Any] | None:
    reveal = False
    path: str | None = None

    for operand in operands:
        if operand == "-R":
            reveal = True
            continue
        if operand.startswith("-"):
            return None
        if path is not None:
            return None
        path = operand

    if path is None:
        return None
    return {"path": path, "reveal": reveal}


def _parse_file_argv(operands: list[str]) -> dict[str, Any] | None:
    brief = False
    paths: list[str] = []

    for operand in operands:
        if operand == "-b":
            brief = True
            continue
        if operand.startswith("-"):
            return None
        paths.append(operand)

    if not paths:
        return None
    return {"paths": paths, "brief": brief}


def _parse_ps_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {
        "all_processes": False,
        "full_format": False,
        "user": None,
        "pid": None,
    }
    index = 0
    while index < len(operands):
        operand = operands[index]
        if operand in {"-u", "-p"}:
            if index + 1 >= len(operands):
                return None
            if operand == "-u":
                arguments["user"] = operands[index + 1]
            else:
                try:
                    arguments["pid"] = int(operands[index + 1])
                except ValueError:
                    return None
            index += 2
            continue
        flags = _expand_short_flag_cluster(operand, {"A", "e", "f"})
        if flags is not None:
            for flag in flags:
                if flag in {"-A", "-e"}:
                    arguments["all_processes"] = True
                elif flag == "-f":
                    arguments["full_format"] = True
            index += 1
            continue
        return None
    return arguments


def _parse_pgrep_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {"full_command": False, "list_names": False, "user": None}
    pattern: str | None = None
    index = 0
    while index < len(operands):
        operand = operands[index]
        if pattern is None and operand == "-u":
            if index + 1 >= len(operands):
                return None
            arguments["user"] = operands[index + 1]
            index += 2
            continue
        if pattern is None:
            flags = (
                _expand_short_flag_cluster(operand, {"f", "l"}) if operand.startswith("-") else None
            )
            if flags is not None:
                for flag in flags:
                    if flag == "-f":
                        arguments["full_command"] = True
                    elif flag == "-l":
                        arguments["list_names"] = True
                index += 1
                continue
        if operand.startswith("-"):
            return None
        if pattern is not None:
            return None
        pattern = operand
        index += 1
    if pattern is None:
        return None
    arguments["pattern"] = pattern
    return arguments


def _parse_lsof_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {
        "path": None,
        "pid": None,
        "command_prefix": None,
        "and_selectors": False,
        "no_dns": False,
        "no_port_names": False,
    }
    index = 0
    while index < len(operands):
        operand = operands[index]
        if operand in {"-p", "-c"}:
            if index + 1 >= len(operands):
                return None
            value = operands[index + 1]
            if operand == "-p":
                try:
                    arguments["pid"] = int(value)
                except ValueError:
                    return None
            else:
                arguments["command_prefix"] = value
            index += 2
            continue
        flags = (
            _expand_short_flag_cluster(operand, {"a", "n", "P"})
            if operand.startswith("-")
            else None
        )
        if flags is not None:
            for flag in flags:
                if flag == "-a":
                    arguments["and_selectors"] = True
                elif flag == "-n":
                    arguments["no_dns"] = True
                elif flag == "-P":
                    arguments["no_port_names"] = True
            index += 1
            continue
        if operand.startswith("-"):
            return None
        if arguments["path"] is not None:
            return None
        arguments["path"] = operand
        index += 1
    return arguments


def _parse_wc_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {"lines": False, "words": False, "bytes": False}
    paths: list[str] = []
    for operand in operands:
        flags = (
            _expand_short_flag_cluster(operand, {"l", "w", "c"})
            if operand.startswith("-")
            else None
        )
        if flags is not None:
            for flag in flags:
                if flag == "-l":
                    arguments["lines"] = True
                elif flag == "-w":
                    arguments["words"] = True
                elif flag == "-c":
                    arguments["bytes"] = True
            continue
        if operand.startswith("-"):
            return None
        paths.append(operand)
    if not paths:
        return None
    arguments["paths"] = paths
    return arguments


def _parse_sort_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {"numeric": False, "reverse": False, "unique": False}
    path: str | None = None
    for operand in operands:
        flags = (
            _expand_short_flag_cluster(operand, {"n", "r", "u"})
            if operand.startswith("-")
            else None
        )
        if flags is not None:
            for flag in flags:
                if flag == "-n":
                    arguments["numeric"] = True
                elif flag == "-r":
                    arguments["reverse"] = True
                elif flag == "-u":
                    arguments["unique"] = True
            continue
        if operand.startswith("-"):
            return None
        if path is not None:
            return None
        path = operand
    if path is None:
        return None
    arguments["path"] = path
    return arguments


def _parse_git_argv(operands: list[str]) -> dict[str, Any] | None:
    if operands == ["status", "--short"]:
        return {"operation": "status_short"}
    if operands == ["branch", "--show-current"]:
        return {"operation": "branch_current"}
    if operands == ["diff", "--stat"]:
        return {"operation": "diff_stat"}
    if operands == ["diff", "--name-only"]:
        return {"operation": "diff_name_only"}
    if len(operands) == 4 and operands[:3] == ["log", "--oneline", "-n"]:
        try:
            count = int(operands[3])
        except ValueError:
            return None
        return {"operation": "log_oneline", "count": count}
    return None


def _parse_ping_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) != 3 or operands[0] != "-c":
        return None
    try:
        count = int(operands[1])
    except ValueError:
        return None
    return {"count": count, "host": operands[2]}


def _parse_curl_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) != 2 or operands[0] != "-I":
        return None
    return {"operation": "http_head", "url": operands[1]}


def _parse_dig_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) != 1:
        return None
    return {"domain": operands[0]}


def _parse_nslookup_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) != 1:
        return None
    return {"domain": operands[0]}


def _parse_tar_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) == 2 and operands[0] == "-tf":
        return {"operation": "list", "archive_path": operands[1]}
    if len(operands) == 4 and operands[0] == "-xf" and operands[2] == "-C":
        return {
            "operation": "extract_tar",
            "archive_path": operands[1],
            "destination_path": operands[3],
        }
    if len(operands) >= 3 and operands[0] == "-czf":
        return {
            "operation": "create_tar_gz",
            "archive_path": operands[1],
            "source_paths": operands[2:],
        }
    return None


def _parse_unzip_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) == 2 and operands[0] == "-l":
        return {"operation": "list", "archive_path": operands[1]}
    if len(operands) == 3 and operands[1] == "-d":
        return {
            "operation": "extract_zip",
            "archive_path": operands[0],
            "destination_path": operands[2],
        }
    return None


def _parse_zip_argv(operands: list[str]) -> dict[str, Any] | None:
    if len(operands) >= 3 and operands[0] == "-r":
        return {
            "operation": "create_zip",
            "archive_path": operands[1],
            "source_paths": operands[2:],
        }
    return None


def _parse_uniq_argv(operands: list[str]) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {"count": False, "repeated_only": False, "unique_only": False}
    path: str | None = None
    for operand in operands:
        flags = (
            _expand_short_flag_cluster(operand, {"c", "d", "u"})
            if operand.startswith("-")
            else None
        )
        if flags is not None:
            for flag in flags:
                if flag == "-c":
                    arguments["count"] = True
                elif flag == "-d":
                    arguments["repeated_only"] = True
                elif flag == "-u":
                    arguments["unique_only"] = True
            continue
        if operand.startswith("-"):
            return None
        if path is not None:
            return None
        path = operand
    if path is None:
        return None
    arguments["path"] = path
    return arguments


def _expand_short_flag_cluster(token: str, allowed_flags: set[str]) -> list[str] | None:
    if not token.startswith("-") or token.startswith("--") or len(token) < 2:
        return None
    flags = token[1:]
    if not flags:
        return None
    expanded: list[str] = []
    for flag in flags:
        if flag not in allowed_flags:
            return None
        expanded.append(f"-{flag}")
    return expanded


def _parse_inline_numeric_flag(token: str, mapping: dict[str, str]) -> tuple[str, int] | None:
    for flag, target in mapping.items():
        if token.startswith(flag) and len(token) > len(flag):
            raw_value = token[len(flag) :]
            try:
                return target, int(raw_value)
            except ValueError:
                return None
    return None

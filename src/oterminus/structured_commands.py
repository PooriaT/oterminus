from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any, Sequence

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


def _validate_paths(values: list[str], *, allow_url_targets: bool = False) -> list[str]:
    return [_validate_path(value, allow_url_targets=allow_url_targets) for value in values]


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


STRUCTURED_ARGUMENT_MODELS: dict[str, type[_StructuredArgumentsModel]] = {
    "ls": LsArguments,
    "pwd": PwdArguments,
    "mkdir": MkdirArguments,
    "chmod": ChmodArguments,
    "find": FindArguments,
    "cp": CpArguments,
    "mv": MvArguments,
    "du": DuArguments,
    "stat": StatArguments,
    "head": HeadArguments,
    "tail": TailArguments,
    "grep": GrepArguments,
    "cat": CatArguments,
    "open": OpenArguments,
    "file": FileArguments,
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
        "mkdir": _parse_mkdir_argv,
        "chmod": _parse_chmod_argv,
        "find": _parse_find_argv,
        "cp": _parse_cp_argv,
        "mv": _parse_mv_argv,
        "du": _parse_du_argv,
        "stat": _parse_stat_argv,
        "head": _parse_head_argv,
        "tail": _parse_tail_argv,
        "grep": _parse_grep_argv,
        "cat": _parse_cat_argv,
        "open": _parse_open_argv,
        "file": _parse_file_argv,
    }.get(command_family)
    if parser is None:
        return None

    arguments = parser(operands)
    if arguments is None:
        return None

    validated = validate_structured_arguments(command_family, arguments)
    return command_family, validated.model_dump()


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


def render_structured_command(command_family: str, arguments: dict[str, Any] | None) -> RenderedCommand:
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
        flags = _expand_short_flag_cluster(operand, {"R", "p", "n"}) if operand.startswith("-") else None
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

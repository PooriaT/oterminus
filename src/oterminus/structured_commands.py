from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class StructuredCommandError(ValueError):
    pass


class _StructuredArgumentsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class LsArguments(_StructuredArgumentsModel):
    path: str = Field(default=".", min_length=1)
    long: bool = False
    human_readable: bool = False
    all: bool = False
    recursive: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if value.startswith("-"):
            raise ValueError("path cannot start with '-'.")
        return value

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
        if value.startswith("-"):
            raise ValueError("path cannot start with '-'.")
        return value


class ChmodArguments(_StructuredArgumentsModel):
    path: str = Field(min_length=1)
    mode: str = Field(min_length=3, max_length=4, pattern=r"^[0-7]{3,4}$")

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if value.startswith("-"):
            raise ValueError("path cannot start with '-'.")
        return value


class FindArguments(_StructuredArgumentsModel):
    path: str = Field(default=".", min_length=1)
    name: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if value.startswith("-"):
            raise ValueError("path cannot start with '-'.")
        return value


STRUCTURED_ARGUMENT_MODELS: dict[str, type[_StructuredArgumentsModel]] = {
    "ls": LsArguments,
    "pwd": PwdArguments,
    "mkdir": MkdirArguments,
    "chmod": ChmodArguments,
    "find": FindArguments,
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
            if operand.startswith("--"):
                return None
            for flag in operand[1:]:
                if flag == "l":
                    arguments["long"] = True
                elif flag == "h":
                    arguments["human_readable"] = True
                elif flag == "a":
                    arguments["all"] = True
                elif flag == "R":
                    arguments["recursive"] = True
                else:
                    return None
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

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from oterminus.models import RiskLevel


class DirectDetectionMode(str, Enum):
    MIN_OPERANDS = "min_operands"
    ZERO_OPERANDS = "zero_operands"
    CD = "cd"
    FIND = "find"
    GREP = "grep"


class PathOperandMode(str, Enum):
    DEFAULT = "default"
    CD = "cd"
    FIND = "find"


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    category: str
    risk_level: RiskLevel
    direct_supported: bool = True
    min_operands: int = 0
    direct_detection_mode: DirectDetectionMode = DirectDetectionMode.MIN_OPERANDS
    path_operand_mode: PathOperandMode = PathOperandMode.DEFAULT
    allowed_flags: frozenset[str] = field(default_factory=frozenset)
    flags_with_values: frozenset[str] = field(default_factory=frozenset)
    leading_flags: frozenset[str] = field(default_factory=frozenset)
    leading_flags_with_values: frozenset[str] = field(default_factory=frozenset)
    leading_flags_with_inline_values: frozenset[str] = field(default_factory=frozenset)
    dangerous_flags: frozenset[str] = field(default_factory=frozenset)
    dangerous_target_literals: frozenset[str] = field(default_factory=frozenset)
    notes: tuple[str, ...] = ()


def _frozenset(values: Iterable[str] = ()) -> frozenset[str]:
    return frozenset(values)


def _command(
    *,
    name: str,
    category: str,
    risk_level: RiskLevel,
    direct_supported: bool = True,
    min_operands: int = 0,
    direct_detection_mode: DirectDetectionMode = DirectDetectionMode.MIN_OPERANDS,
    path_operand_mode: PathOperandMode = PathOperandMode.DEFAULT,
    allowed_flags: Iterable[str] = (),
    flags_with_values: Iterable[str] = (),
    leading_flags: Iterable[str] = (),
    leading_flags_with_values: Iterable[str] = (),
    leading_flags_with_inline_values: Iterable[str] = (),
    dangerous_flags: Iterable[str] = (),
    dangerous_target_literals: Iterable[str] = (),
    notes: Iterable[str] = (),
) -> CommandSpec:
    return CommandSpec(
        name=name,
        category=category,
        risk_level=risk_level,
        direct_supported=direct_supported,
        min_operands=min_operands,
        direct_detection_mode=direct_detection_mode,
        path_operand_mode=path_operand_mode,
        allowed_flags=_frozenset(allowed_flags),
        flags_with_values=_frozenset(flags_with_values),
        leading_flags=_frozenset(leading_flags),
        leading_flags_with_values=_frozenset(leading_flags_with_values),
        leading_flags_with_inline_values=_frozenset(leading_flags_with_inline_values),
        dangerous_flags=_frozenset(dangerous_flags),
        dangerous_target_literals=_frozenset(dangerous_target_literals),
        notes=tuple(notes),
    )


# This registry is the shared source of truth for the v1 curated command set.
# Metadata such as risk, direct support, and parsing hints live here so the
# validator and direct-command path do not drift apart over time.
COMMAND_REGISTRY: dict[str, CommandSpec] = {
    "cd": _command(
        name="cd",
        category="navigation",
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.CD,
        path_operand_mode=PathOperandMode.CD,
        notes=("Changes the oterminus working directory for the current REPL session.",),
    ),
    "ls": _command(
        name="ls",
        category="inspection",
        risk_level=RiskLevel.SAFE,
        allowed_flags=("-a", "-h", "-l", "-lh", "-la", "-al"),
    ),
    "pwd": _command(
        name="pwd",
        category="navigation",
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.ZERO_OPERANDS,
    ),
    "cat": _command(name="cat", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1),
    "head": _command(
        name="head",
        category="inspection",
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        flags_with_values=("-n", "-c"),
    ),
    "tail": _command(
        name="tail",
        category="inspection",
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        flags_with_values=("-n", "-c"),
    ),
    "grep": _command(
        name="grep",
        category="search",
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        direct_detection_mode=DirectDetectionMode.GREP,
        flags_with_values=("-e", "-f", "-m"),
        allowed_flags=("-E", "-F", "-H", "-h", "-i", "-l", "-n", "-r", "-R"),
    ),
    "find": _command(
        name="find",
        category="search",
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.FIND,
        path_operand_mode=PathOperandMode.FIND,
        leading_flags=("-H", "-L", "-P"),
        leading_flags_with_values=("-D", "-O"),
        leading_flags_with_inline_values=("-O",),
        allowed_flags=("-name", "-path", "-type", "-maxdepth", "-mindepth", "-print"),
    ),
    "du": _command(name="du", category="inspection", risk_level=RiskLevel.SAFE),
    "stat": _command(name="stat", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1),
    "mkdir": _command(
        name="mkdir",
        category="filesystem_write",
        risk_level=RiskLevel.WRITE,
        min_operands=1,
        allowed_flags=("-p",),
    ),
    "cp": _command(name="cp", category="filesystem_write", risk_level=RiskLevel.WRITE, min_operands=2),
    "mv": _command(name="mv", category="filesystem_write", risk_level=RiskLevel.WRITE, min_operands=2),
    "chmod": _command(
        name="chmod",
        category="permissions",
        risk_level=RiskLevel.WRITE,
        min_operands=2,
        flags_with_values=("--context", "--reference"),
        dangerous_target_literals=("/", "/*"),
    ),
    "touch": _command(name="touch", category="filesystem_write", risk_level=RiskLevel.WRITE, min_operands=1),
    "rm": _command(
        name="rm",
        category="destructive",
        risk_level=RiskLevel.DANGEROUS,
        min_operands=1,
        dangerous_flags=("-r", "-rf", "-fr"),
        allowed_flags=("-f", "-i", "-r", "-rf", "-fr"),
    ),
    "chown": _command(
        name="chown",
        category="permissions",
        risk_level=RiskLevel.DANGEROUS,
        min_operands=2,
        dangerous_target_literals=("/", "/*"),
    ),
    "sudo": _command(name="sudo", category="privileged", risk_level=RiskLevel.DANGEROUS, min_operands=1),
}


def get_command_spec(name: str) -> CommandSpec | None:
    return COMMAND_REGISTRY.get(name)


def supported_base_commands() -> frozenset[str]:
    return frozenset(COMMAND_REGISTRY)


def supported_categories() -> frozenset[str]:
    return frozenset(spec.category for spec in COMMAND_REGISTRY.values())


def direct_supported_base_commands() -> frozenset[str]:
    return frozenset(name for name, spec in COMMAND_REGISTRY.items() if spec.direct_supported)


def looks_like_direct_invocation(base: str, operands: list[str]) -> bool:
    spec = get_command_spec(base)
    if spec is None or not spec.direct_supported:
        return False

    if spec.direct_detection_mode == DirectDetectionMode.ZERO_OPERANDS:
        return len(operands) == 0

    if spec.direct_detection_mode == DirectDetectionMode.CD:
        return len(operands) <= 1

    if spec.direct_detection_mode == DirectDetectionMode.FIND:
        if not operands:
            return True
        first = operands[0]
        return first in {".", "..", "/"} or first.startswith(("/", "~/", "./", "../")) or any(
            operand.startswith("-") for operand in operands
        )

    if spec.direct_detection_mode == DirectDetectionMode.GREP:
        return any(operand.startswith("-") for operand in operands) or any(
            _looks_like_path(operand) for operand in operands
        )

    return len(operands) >= spec.min_operands


def _looks_like_path(value: str) -> bool:
    return (
        value in {".", "..", "~"}
        or value.startswith(("/", "~/", "./", "../"))
        or "/" in value
        or "." in value
    )

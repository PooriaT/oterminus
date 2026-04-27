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
    path_valued_flags: frozenset[str] = field(default_factory=frozenset)
    leading_flags: frozenset[str] = field(default_factory=frozenset)
    leading_flags_with_values: frozenset[str] = field(default_factory=frozenset)
    leading_flags_with_inline_values: frozenset[str] = field(default_factory=frozenset)
    dangerous_flags: frozenset[str] = field(default_factory=frozenset)
    dangerous_target_literals: frozenset[str] = field(default_factory=frozenset)
    forbidden_operand_prefixes: frozenset[str] = field(default_factory=frozenset)
    notes: tuple[str, ...] = ()


def _frozenset(values: Iterable[str] = ()) -> frozenset[str]:
    return frozenset(values)


def command(
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
    path_valued_flags: Iterable[str] = (),
    leading_flags: Iterable[str] = (),
    leading_flags_with_values: Iterable[str] = (),
    leading_flags_with_inline_values: Iterable[str] = (),
    dangerous_flags: Iterable[str] = (),
    dangerous_target_literals: Iterable[str] = (),
    forbidden_operand_prefixes: Iterable[str] = (),
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
        path_valued_flags=_frozenset(path_valued_flags),
        leading_flags=_frozenset(leading_flags),
        leading_flags_with_values=_frozenset(leading_flags_with_values),
        leading_flags_with_inline_values=_frozenset(leading_flags_with_inline_values),
        dangerous_flags=_frozenset(dangerous_flags),
        dangerous_target_literals=_frozenset(dangerous_target_literals),
        forbidden_operand_prefixes=_frozenset(forbidden_operand_prefixes),
        notes=tuple(notes),
    )

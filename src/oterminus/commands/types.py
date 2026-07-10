from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from oterminus.models import RiskLevel

NETWORK_TOUCHING_WARNING = (
    "This command contacts external hosts and may reveal your IP address, DNS query, "
    "target host, or network metadata."
)


class DirectDetectionMode(str, Enum):
    MIN_OPERANDS = "min_operands"
    ZERO_OPERANDS = "zero_operands"
    CD = "cd"
    FIND = "find"
    GREP = "grep"


class DirectFlagPolicy(str, Enum):
    EXPLICIT = "explicit"
    SAFE_INSPECTION_PASSTHROUGH = "safe_inspection_passthrough"


# Passthrough is a reviewed capability, not a classification inferred from risk alone. A command
# must be added here deliberately after its complete behavior has been checked against the policy
# documented in website/docs/architecture/validation-and-policy.md.
SAFE_INSPECTION_PASSTHROUGH_COMMANDS = frozenset({"ls"})


class PathOperandMode(str, Enum):
    DEFAULT = "default"
    CD = "cd"
    FIND = "find"
    NONE = "none"


class MaturityLevel(str, Enum):
    STRUCTURED = "structured"
    DIRECT_ONLY = "direct_only"
    EXPERIMENTAL_ONLY = "experimental_only"
    BLOCKED = "blocked"


def maturity_status_label(maturity_level: MaturityLevel, *, direct_supported: bool) -> str:
    if maturity_level == MaturityLevel.STRUCTURED:
        return "structured (normal executable support)"
    if maturity_level == MaturityLevel.DIRECT_ONLY:
        return "direct-only (direct executable support only)"
    if maturity_level == MaturityLevel.EXPERIMENTAL_ONLY:
        if direct_supported:
            return "experimental-only (constrained executable fallback)"
        return "experimental/planned (metadata only; not normal executable support)"
    if maturity_level == MaturityLevel.BLOCKED:
        return "blocked (unavailable)"
    return maturity_level.value


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    category: str
    capability_id: str
    capability_label: str
    capability_description: str
    risk_level: RiskLevel
    maturity_level: MaturityLevel
    direct_supported: bool = True
    min_operands: int = 0
    max_operands: int | None = None
    direct_detection_mode: DirectDetectionMode = DirectDetectionMode.MIN_OPERANDS
    direct_flag_policy: DirectFlagPolicy = DirectFlagPolicy.EXPLICIT
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
    examples: tuple[str, ...] = ()
    natural_language_aliases: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    supported_platforms: frozenset[str] | None = None
    network_touching: bool = False


def _frozenset(values: Iterable[str] = ()) -> frozenset[str]:
    return frozenset(values)


def command(
    *,
    name: str,
    category: str,
    capability_id: str,
    capability_label: str,
    capability_description: str,
    risk_level: RiskLevel,
    maturity_level: MaturityLevel = MaturityLevel.STRUCTURED,
    direct_supported: bool = True,
    min_operands: int = 0,
    max_operands: int | None = None,
    direct_detection_mode: DirectDetectionMode = DirectDetectionMode.MIN_OPERANDS,
    direct_flag_policy: DirectFlagPolicy = DirectFlagPolicy.EXPLICIT,
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
    examples: Iterable[str] = (),
    natural_language_aliases: Iterable[str] = (),
    notes: Iterable[str] = (),
    supported_platforms: Iterable[str] | None = None,
    network_touching: bool = False,
) -> CommandSpec:
    return CommandSpec(
        name=name,
        category=category,
        capability_id=capability_id,
        capability_label=capability_label,
        capability_description=capability_description,
        risk_level=risk_level,
        maturity_level=maturity_level,
        direct_supported=direct_supported,
        min_operands=min_operands,
        max_operands=max_operands,
        direct_detection_mode=direct_detection_mode,
        direct_flag_policy=direct_flag_policy,
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
        examples=tuple(examples),
        natural_language_aliases=tuple(natural_language_aliases),
        notes=tuple(notes),
        supported_platforms=(
            _frozenset(supported_platforms) if supported_platforms is not None else None
        ),
        network_touching=network_touching,
    )


def safe_inspection_passthrough_eligibility_reasons(spec: CommandSpec) -> tuple[str, ...]:
    """Return fail-closed reasons why a passthrough opt-in is not policy eligible."""
    if spec.direct_flag_policy != DirectFlagPolicy.SAFE_INSPECTION_PASSTHROUGH:
        return ()

    reasons: list[str] = []
    if spec.name not in SAFE_INSPECTION_PASSTHROUGH_COMMANDS:
        reviewed = ", ".join(sorted(SAFE_INSPECTION_PASSTHROUGH_COMMANDS))
        reasons.append(f"only explicitly reviewed commands may opt in (currently: {reviewed})")
    if spec.risk_level != RiskLevel.SAFE:
        reasons.append("risk must be safe")
    if spec.capability_id != "filesystem_inspection" or spec.category != "inspection":
        reasons.append("command must be local-filesystem inspection only")
    if spec.network_touching:
        reasons.append("command must not be network-touching")
    if not spec.direct_supported:
        reasons.append("command must support trusted local direct detection")
    if spec.maturity_level != MaturityLevel.STRUCTURED:
        reasons.append("command must retain structured rendering for normal planning")
    if spec.path_operand_mode != PathOperandMode.DEFAULT:
        reasons.append("operands must use local-filesystem path handling")
    if spec.dangerous_flags or spec.dangerous_target_literals:
        reasons.append("command must not expose dangerous flags or targets")
    return tuple(reasons)

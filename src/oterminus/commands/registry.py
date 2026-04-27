from __future__ import annotations

from collections.abc import Iterable, Sequence

from .dangerous import COMMAND_PACK as DANGEROUS_COMMANDS
from .filesystem import COMMAND_PACK as FILESYSTEM_COMMANDS
from .macos import COMMAND_PACK as MACOS_COMMANDS
from .process import COMMAND_PACK as PROCESS_COMMANDS
from .system import COMMAND_PACK as SYSTEM_COMMANDS
from .text import COMMAND_PACK as TEXT_COMMANDS
from .types import CommandSpec, DirectDetectionMode


COMMAND_PACKS: tuple[tuple[CommandSpec, ...], ...] = (
    FILESYSTEM_COMMANDS,
    TEXT_COMMANDS,
    PROCESS_COMMANDS,
    SYSTEM_COMMANDS,
    MACOS_COMMANDS,
    DANGEROUS_COMMANDS,
)


def merge_command_packs(command_packs: Sequence[Iterable[CommandSpec]]) -> dict[str, CommandSpec]:
    merged: dict[str, CommandSpec] = {}
    for pack in command_packs:
        for spec in pack:
            if spec.name in merged:
                msg = f"Duplicate command spec for '{spec.name}' detected while building command registry."
                raise ValueError(msg)
            merged[spec.name] = spec
    return merged


# Shared source of truth for curated command metadata.
COMMAND_REGISTRY: dict[str, CommandSpec] = merge_command_packs(COMMAND_PACKS)


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
    return value in {".", "..", "~"} or value.startswith(("/", "~/", "./", "../")) or "/" in value or "." in value

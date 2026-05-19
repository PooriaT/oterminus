from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Sequence

from .dangerous import COMMAND_PACK as DANGEROUS_COMMANDS
from .filesystem import COMMAND_PACK as FILESYSTEM_COMMANDS
from .macos import COMMAND_PACK as MACOS_COMMANDS
from .process import COMMAND_PACK as PROCESS_COMMANDS
from .system import COMMAND_PACK as SYSTEM_COMMANDS
from .text import COMMAND_PACK as TEXT_COMMANDS
from .types import CommandSpec, DirectDetectionMode


@dataclass(frozen=True, slots=True)
class CapabilitySummary:
    capability_id: str
    capability_label: str
    capability_description: str
    maturity_levels: tuple[str, ...]
    commands: tuple[str, ...]
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommandPack:
    pack_id: str
    label: str
    description: str
    commands: tuple[CommandSpec, ...]

    def __iter__(self):
        return iter(self.commands)


COMMAND_PACKS: tuple[CommandPack, ...] = (
    CommandPack(
        "filesystem",
        "Filesystem",
        "File and directory inspection/mutation commands.",
        FILESYSTEM_COMMANDS,
    ),
    CommandPack("text", "Text", "Text and content inspection commands.", TEXT_COMMANDS),
    CommandPack("process", "Process", "Process inspection commands.", PROCESS_COMMANDS),
    CommandPack("system", "System", "System information commands.", SYSTEM_COMMANDS),
    CommandPack("macos", "macOS", "macOS-specific desktop commands.", MACOS_COMMANDS),
    CommandPack("dangerous", "Dangerous", "High-risk command families.", DANGEROUS_COMMANDS),
)


def merge_command_packs(command_packs: Sequence[Iterable[CommandSpec]]) -> dict[str, CommandSpec]:
    merged: dict[str, CommandSpec] = {}
    for pack in command_packs:
        for spec in pack:
            if spec.name in merged:
                msg = f"Duplicate command spec for '{spec.name}' detected while building command registry."
                raise ValueError(msg)
            if not spec.capability_id.strip():
                msg = f"Command spec '{spec.name}' must define a non-empty capability_id."
                raise ValueError(msg)
            merged[spec.name] = spec
    return merged


# Shared source of truth for curated command metadata.
COMMAND_REGISTRY: dict[str, CommandSpec] = merge_command_packs(
    tuple(pack.commands for pack in COMMAND_PACKS)
)
_COMMAND_TO_PACK_ID: dict[str, str] = {
    spec.name: pack.pack_id for pack in COMMAND_PACKS for spec in pack.commands
}


def available_pack_ids() -> tuple[str, ...]:
    return tuple(pack.pack_id for pack in COMMAND_PACKS)


def get_pack_for_command(command_name: str) -> str | None:
    return _COMMAND_TO_PACK_ID.get(command_name)


def get_enabled_command_registry(
    disabled_pack_ids: frozenset[str] | None = None,
) -> dict[str, CommandSpec]:
    disabled = disabled_pack_ids or frozenset()
    return {
        name: spec
        for name, spec in COMMAND_REGISTRY.items()
        if get_pack_for_command(name) not in disabled
    }


def get_command_spec(name: str) -> CommandSpec | None:
    return COMMAND_REGISTRY.get(name)


def get_enabled_command_spec(
    name: str, disabled_pack_ids: frozenset[str] | None = None
) -> CommandSpec | None:
    spec = COMMAND_REGISTRY.get(name)
    if spec is None:
        return None
    disabled = disabled_pack_ids if isinstance(disabled_pack_ids, frozenset) else frozenset()
    if get_pack_for_command(name) in disabled:
        return None
    return spec


def supported_base_commands(disabled_pack_ids: frozenset[str] | None = None) -> tuple[str, ...]:
    return tuple(sorted(get_enabled_command_registry(disabled_pack_ids)))


def supported_categories() -> tuple[str, ...]:
    return tuple(sorted({spec.category for spec in COMMAND_REGISTRY.values()}))


def get_commands_by_capability(capability_id: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            spec.name for spec in COMMAND_REGISTRY.values() if spec.capability_id == capability_id
        )
    )


def supported_capabilities(
    disabled_pack_ids: frozenset[str] | None = None,
) -> tuple[CapabilitySummary, ...]:
    registry = get_enabled_command_registry(disabled_pack_ids)
    capability_ids = sorted({spec.capability_id for spec in registry.values()})
    summaries: list[CapabilitySummary] = []
    for capability_id in capability_ids:
        specs = [spec for spec in registry.values() if spec.capability_id == capability_id]
        first = specs[0]
        aliases = sorted({alias for spec in specs for alias in spec.natural_language_aliases})
        maturity_levels = sorted({spec.maturity_level.value for spec in specs})
        commands = tuple(sorted(spec.name for spec in specs))
        summaries.append(
            CapabilitySummary(
                capability_id=capability_id,
                capability_label=first.capability_label,
                capability_description=first.capability_description,
                maturity_levels=tuple(maturity_levels),
                commands=commands,
                aliases=tuple(aliases),
            )
        )
    return tuple(summaries)


def command_examples_for_prompt(
    max_examples: int = 8, *, disabled_pack_ids: frozenset[str] | None = None
) -> str:
    rows: list[str] = []
    registry = get_enabled_command_registry(disabled_pack_ids)
    for capability in supported_capabilities(disabled_pack_ids):
        if not capability.commands:
            continue
        examples = []
        for command_name in capability.commands:
            spec = registry[command_name]
            if spec.examples:
                examples.append(spec.examples[0])
            if len(examples) >= 2:
                break
        if examples:
            rows.append(
                f"- {capability.capability_id}: "
                + " | ".join(f"`{example}`" for example in examples)
            )
        if len(rows) >= max_examples:
            break
    return "\n".join(rows)


def capability_summary_for_prompt(
    *,
    max_capabilities: int = 7,
    max_commands_per_capability: int = 4,
    max_aliases_per_capability: int = 2,
    disabled_pack_ids: frozenset[str] | None = None,
) -> str:
    lines: list[str] = []
    for capability in supported_capabilities(disabled_pack_ids)[:max_capabilities]:
        command_sample = ", ".join(capability.commands[:max_commands_per_capability])
        alias_sample = (
            ", ".join(capability.aliases[:max_aliases_per_capability])
            if capability.aliases
            else "none"
        )
        lines.append(
            f"- {capability.capability_id}: {capability.capability_description} "
            f"(commands: {command_sample}; aliases: {alias_sample})"
        )
    return "\n".join(lines)


def command_examples_for_readme() -> str:
    lines: list[str] = []
    for capability in supported_capabilities():
        lines.append(f"- `{capability.capability_id}`: {capability.capability_description}")
        lines.append(f"  - Commands: {', '.join(f'`{name}`' for name in capability.commands)}")
        if capability.aliases:
            lines.append(
                f"  - NL aliases: {', '.join(f'`{alias}`' for alias in capability.aliases[:4])}"
            )
        first_command = capability.commands[0] if capability.commands else None
        if first_command:
            example = COMMAND_REGISTRY[first_command].examples
            if example:
                lines.append(f"  - Example: `{example[0]}`")
    return "\n".join(lines)


def direct_supported_base_commands(
    disabled_pack_ids: frozenset[str] | None = None,
) -> frozenset[str]:
    return frozenset(
        name
        for name, spec in get_enabled_command_registry(disabled_pack_ids).items()
        if spec.direct_supported
    )


def looks_like_direct_invocation(
    base: str, operands: list[str], disabled_pack_ids: frozenset[str] | None = None
) -> bool:
    spec = get_enabled_command_spec(base, disabled_pack_ids)
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
        return (
            first in {".", "..", "/"}
            or first.startswith(("/", "~/", "./", "../"))
            or any(operand.startswith("-") for operand in operands)
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

from __future__ import annotations

from oterminus.commands import get_command_spec, supported_base_commands, supported_capabilities


def render_help() -> str:
    return (
        "Enter either a natural-language terminal request or a direct shell command.\n"
        "Examples: 'find all .py files', 'ls -lh', 'cd src'\n"
        "Built-ins: help, capabilities, commands, examples, history, history <n>, "
        "explain <request>, explain <history_id>, rerun <history_id>, "
        "dry-run <request>, audit status, exit, quit\n"
        "Try: help capabilities | help <capability_id> | help <command_family>"
    )


def render_capabilities() -> str:
    lines = ["Supported capabilities:"]
    for capability in supported_capabilities():
        lines.append(f"- {capability.capability_id}: {capability.capability_description}")
    return "\n".join(lines)


def render_commands() -> str:
    lines = ["Supported command families by capability:"]
    for capability in supported_capabilities():
        lines.append(f"{capability.capability_id}:")
        lines.extend(f"  - {command_name}" for command_name in capability.commands)
    return "\n".join(lines)


def render_examples() -> str:
    lines = ["Example requests by capability:"]
    for capability in supported_capabilities():
        lines.append(f"{capability.capability_id}:")
        has_any = False
        for command_name in capability.commands:
            spec = get_command_spec(command_name)
            if spec is None or not spec.examples:
                continue
            lines.append(f"  - {spec.examples[0]}")
            has_any = True
        if not has_any:
            lines.append("  - (no registry examples available)")
    return "\n".join(lines)


def render_help_capabilities() -> str:
    return (
        "capability-first model:\n"
        "- OTerminus supports curated workflows, not every shell command.\n"
        "- Capabilities group related command families.\n"
        "- Structured mode is preferred when a capability is supported.\n"
        "- Experimental mode is a constrained fallback for select workflows.\n"
        "- Direct commands still pass validation and confirmation policy gates."
    )


def render_capability_help(capability_id: str) -> str:
    capability = next(
        (item for item in supported_capabilities() if item.capability_id == capability_id),
        None,
    )
    if capability is None:
        return f"Unknown capability: {capability_id}\nTry: capabilities"

    lines = [
        f"Capability: {capability.capability_id}",
        f"Label: {capability.capability_label}",
        f"Description: {capability.capability_description}",
        f"Maturity in registry: {', '.join(capability.maturity_levels)}",
        "Supported command families:",
    ]
    lines.extend(f"- {command_name}" for command_name in capability.commands)
    lines.append("Examples:")
    for command_name in capability.commands:
        spec = get_command_spec(command_name)
        if spec is not None and spec.examples:
            lines.append(f"- {spec.examples[0]}")
    notes = {
        note
        for command_name in capability.commands
        for note in (get_command_spec(command_name).notes if get_command_spec(command_name) else ())
    }
    if notes:
        lines.append("Notes / warnings:")
        lines.extend(f"- {note}" for note in sorted(notes))
    return "\n".join(lines)


def render_command_help(command_family: str) -> str:
    spec = get_command_spec(command_family)
    if spec is None:
        return f"Unknown command family: {command_family}\nTry: commands"

    lines = [
        f"Command family: {spec.name}",
        f"Capability: {spec.capability_id} ({spec.capability_label})",
        f"Category: {spec.category}",
        f"Risk level: {spec.risk_level.value}",
        f"Maturity: {spec.maturity_level.value}",
        f"Direct support: {'yes' if spec.direct_supported else 'no'}",
    ]
    if spec.examples:
        lines.append("Examples:")
        lines.extend(f"- {example}" for example in spec.examples)
    if spec.notes:
        lines.append("Notes / warnings:")
        lines.extend(f"- {note}" for note in spec.notes)
    return "\n".join(lines)


def render_unknown_help_target(target: str) -> str:
    return (
        f"Unknown help target: {target}\n"
        "Try one of: help capabilities | help <capability_id> | help <command_family> | "
        "capabilities | commands | examples"
    )


def discovery_help_targets() -> tuple[str, ...]:
    return (
        "capabilities",
        *tuple(c.capability_id for c in supported_capabilities()),
        *supported_base_commands(),
    )

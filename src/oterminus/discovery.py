from __future__ import annotations

from oterminus.commands import (
    NETWORK_TOUCHING_WARNING,
    command_maturity_status,
    get_command_spec,
    get_enabled_command_spec,
    is_normal_executable_spec,
    supported_base_commands,
    supported_capabilities,
)
from oterminus.terminal_style import StyleToken, TerminalStyle


def render_help(*, style: TerminalStyle | None = None) -> str:
    return (
        f"{_style(style, StyleToken.HEADING, 'OTerminus help')}\n"
        "Enter either a natural-language terminal request or a direct shell command.\n"
        f"{_style(style, StyleToken.HEADING, 'Examples')}: "
        "'find all .py files', 'ls -lh', 'cd src'\n"
        f"{_style(style, StyleToken.HEADING, 'Built-ins')}: "
        "help, capabilities, commands, examples, history, history <n>, "
        "explain <request>, explain <history_id>, rerun <history_id>, "
        "dry-run <request>, audit status, exit, quit\n"
        f"{_style(style, StyleToken.HEADING, 'Try')}: "
        "help capabilities | help <capability_id> | help <command_family>"
    )


def render_capabilities(
    *,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
    style: TerminalStyle | None = None,
) -> str:
    lines = [_style(style, StyleToken.HEADING, "Capabilities:")]
    for capability in supported_capabilities(disabled_pack_ids, platform_id):
        suffix = (
            _style(style, StyleToken.WARNING, " [network-touching]")
            if capability.network_touching
            else ""
        )
        status = _style(
            style,
            StyleToken.SUCCESS if capability.normal_executable else StyleToken.MUTED,
            "normal executable" if capability.normal_executable else "metadata only",
        )
        maturity = ", ".join(
            _style(style, StyleToken.DETAIL, maturity) for maturity in capability.maturity_levels
        )
        lines.append(
            f"- {_style(style, StyleToken.COMMAND, capability.capability_id)}: "
            f"{capability.capability_description}{suffix} "
            f"[status: {status}; maturity: {maturity}]"
        )
    return "\n".join(lines)


def render_commands(
    *,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
    style: TerminalStyle | None = None,
) -> str:
    lines = [_style(style, StyleToken.HEADING, "Normal executable command families by capability:")]
    for capability in supported_capabilities(disabled_pack_ids, platform_id):
        lines.append(f"{_style(style, StyleToken.COMMAND, capability.capability_id)}:")
        has_any = False
        for command_name in capability.commands:
            spec = get_command_spec(command_name)
            if spec is None or not is_normal_executable_spec(spec):
                continue
            suffix = (
                _style(style, StyleToken.WARNING, " (network-touching)")
                if spec is not None and spec.network_touching
                else ""
            )
            lines.append(f"  - {_style(style, StyleToken.COMMAND, command_name)}{suffix}")
            has_any = True
        if not has_any:
            lines.append(
                "  - "
                + _style(style, StyleToken.MUTED, "(metadata only; not normal executable support)")
            )
    return "\n".join(lines)


def render_examples(
    *,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
    style: TerminalStyle | None = None,
) -> str:
    lines = [_style(style, StyleToken.HEADING, "Example requests by normal executable capability:")]
    for capability in supported_capabilities(disabled_pack_ids, platform_id):
        lines.append(f"{_style(style, StyleToken.COMMAND, capability.capability_id)}:")
        has_any = False
        for command_name in capability.commands:
            spec = get_command_spec(command_name)
            if spec is None or not spec.examples or not is_normal_executable_spec(spec):
                continue
            lines.append(f"  - {_style(style, StyleToken.DETAIL, spec.examples[0])}")
            has_any = True
        if not has_any:
            lines.append(
                "  - "
                + _style(style, StyleToken.MUTED, "(no normal executable examples available)")
            )
    return "\n".join(lines)


def render_examples_for_capability(
    capability_id: str,
    *,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
    style: TerminalStyle | None = None,
) -> str:
    capability = next(
        (
            item
            for item in supported_capabilities(disabled_pack_ids, platform_id)
            if item.capability_id == capability_id
        ),
        None,
    )
    if capability is None:
        return (
            _style(style, StyleToken.ERROR, f"Unknown capability: {capability_id}")
            + "\nTry: capabilities"
        )

    lines = ["Examples for " + _style(style, StyleToken.COMMAND, capability.capability_id) + ":"]
    has_any = False
    for command_name in capability.commands:
        spec = get_command_spec(command_name)
        if spec is None or not spec.examples or not is_normal_executable_spec(spec):
            continue
        lines.append(f"- {_style(style, StyleToken.DETAIL, spec.examples[0])}")
        has_any = True
    if not has_any:
        lines.append(
            "- " + _style(style, StyleToken.MUTED, "(no normal executable examples available)")
        )
    return "\n".join(lines)


def render_help_capabilities(*, style: TerminalStyle | None = None) -> str:
    return (
        f"{_style(style, StyleToken.HEADING, 'capability-first model:')}\n"
        "- OTerminus supports curated workflows, not every shell command.\n"
        "- Capabilities group related command families.\n"
        "- Structured mode is preferred when a capability is supported.\n"
        "- Experimental mode is a constrained fallback for select workflows.\n"
        "- Experimental/planned metadata-only capabilities are visible in detailed help and "
        "generated references, but are not advertised as normal executable workflows.\n"
        "- Direct commands still pass validation and confirmation policy gates."
    )


def render_capability_help(
    capability_id: str,
    *,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
    style: TerminalStyle | None = None,
) -> str:
    capability = next(
        (
            item
            for item in supported_capabilities(disabled_pack_ids, platform_id)
            if item.capability_id == capability_id
        ),
        None,
    )
    if capability is None:
        return (
            _style(style, StyleToken.ERROR, f"Unknown capability: {capability_id}")
            + "\nTry: capabilities"
        )

    lines = [
        f"Capability: {_style(style, StyleToken.COMMAND, capability.capability_id)}",
        f"Label: {capability.capability_label}",
        f"Description: {capability.capability_description}",
        "Maturity in registry: "
        + ", ".join(
            _style(style, StyleToken.DETAIL, maturity) for maturity in capability.maturity_levels
        ),
        f"Normal executable support: {_style_bool(style, capability.normal_executable)}",
        f"Network-touching: {_style_bool(style, capability.network_touching, warning_when_true=True)}",
        _style(style, StyleToken.HEADING, "Command families:"),
    ]
    for command_name in capability.commands:
        spec = get_command_spec(command_name)
        if spec is None:
            continue
        lines.append(
            f"- {_style(style, StyleToken.COMMAND, command_name)} "
            f"[{_style(style, StyleToken.DETAIL, command_maturity_status(spec))}]"
        )
    lines.append(_style(style, StyleToken.HEADING, "Examples:"))
    has_examples = False
    for command_name in capability.commands:
        spec = get_command_spec(command_name)
        if spec is not None and spec.examples and is_normal_executable_spec(spec):
            lines.append(f"- {_style(style, StyleToken.DETAIL, spec.examples[0])}")
            has_examples = True
    if not has_examples:
        lines.append(
            "- " + _style(style, StyleToken.MUTED, "(no normal executable examples available)")
        )
    notes = {
        note
        for command_name in capability.commands
        for note in (get_command_spec(command_name).notes if get_command_spec(command_name) else ())
    }
    if notes:
        lines.append(_style(style, StyleToken.HEADING, "Notes / warnings:"))
        lines.extend(f"- {_style(style, StyleToken.WARNING, note)}" for note in sorted(notes))
    if capability.network_touching and NETWORK_TOUCHING_WARNING not in notes:
        if not notes:
            lines.append(_style(style, StyleToken.HEADING, "Notes / warnings:"))
        lines.append(f"- {_style(style, StyleToken.WARNING, NETWORK_TOUCHING_WARNING)}")
    return "\n".join(lines)


def render_command_help(
    command_family: str,
    *,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
    style: TerminalStyle | None = None,
) -> str:
    spec = get_enabled_command_spec(command_family, disabled_pack_ids, platform_id)
    if spec is None:
        return (
            _style(style, StyleToken.ERROR, f"Unknown command family: {command_family}")
            + "\nTry: commands"
        )

    lines = [
        f"Command family: {_style(style, StyleToken.COMMAND, spec.name)}",
        f"Capability: {_style(style, StyleToken.COMMAND, spec.capability_id)} ({spec.capability_label})",
        f"Category: {spec.category}",
        f"Risk level: {spec.risk_level.value}",
        f"Maturity: {_style(style, StyleToken.DETAIL, spec.maturity_level.value)}",
        f"Status: {_style(style, StyleToken.DETAIL, command_maturity_status(spec))}",
        f"Direct support: {_style_bool(style, spec.direct_supported)}",
        f"Normal executable support: {_style_bool(style, is_normal_executable_spec(spec))}",
        f"Network-touching: {_style_bool(style, spec.network_touching, warning_when_true=True)}",
    ]
    if spec.examples:
        lines.append(_style(style, StyleToken.HEADING, "Examples:"))
        lines.extend(f"- {_style(style, StyleToken.DETAIL, example)}" for example in spec.examples)
    if spec.notes:
        lines.append(_style(style, StyleToken.HEADING, "Notes / warnings:"))
        lines.extend(f"- {_style(style, StyleToken.WARNING, note)}" for note in spec.notes)
    if spec.network_touching and NETWORK_TOUCHING_WARNING not in spec.notes:
        if not spec.notes:
            lines.append(_style(style, StyleToken.HEADING, "Notes / warnings:"))
        lines.append(f"- {_style(style, StyleToken.WARNING, NETWORK_TOUCHING_WARNING)}")
    return "\n".join(lines)


def render_unknown_help_target(target: str, *, style: TerminalStyle | None = None) -> str:
    return (
        _style(style, StyleToken.ERROR, f"Unknown help target: {target}") + "\n"
        "Try one of: help capabilities | help <capability_id> | help <command_family> | "
        "capabilities | commands | examples"
    )


def _style(style: TerminalStyle | None, token: StyleToken, text: str) -> str:
    if style is None:
        return text
    return style.apply(token, text)


def _style_bool(
    style: TerminalStyle | None, value: bool, *, warning_when_true: bool = False
) -> str:
    if value:
        token = StyleToken.WARNING if warning_when_true else StyleToken.SUCCESS
        return _style(style, token, "yes")
    return _style(style, StyleToken.MUTED, "no")


def discovery_help_targets(
    *,
    disabled_pack_ids: frozenset[str] | None = None,
    platform_id: str | None = None,
) -> tuple[str, ...]:
    return (
        "capabilities",
        *tuple(
            c.capability_id
            for c in supported_capabilities(
                disabled_pack_ids=disabled_pack_ids, platform_id=platform_id
            )
        ),
        *supported_base_commands(disabled_pack_ids=disabled_pack_ids, platform_id=platform_id),
    )

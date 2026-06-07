import re

from oterminus.commands import NETWORK_TOUCHING_WARNING
from oterminus.discovery import (
    render_capabilities,
    render_capability_help,
    render_command_help,
    render_commands,
    render_examples,
    render_help,
)
from oterminus.terminal_style import TerminalStyle


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def test_command_help_exposes_network_touching_warning() -> None:
    output = render_command_help("ping")

    assert "Network-touching: yes" in output
    assert NETWORK_TOUCHING_WARNING in output


def test_network_diagnostics_help_exposes_warning_and_supported_commands() -> None:
    output = render_capability_help("network_diagnostics")

    assert "Network-touching: yes" in output
    assert "- curl" in output
    assert "- dig" in output
    assert "- nslookup" in output
    assert "- ping" in output
    assert NETWORK_TOUCHING_WARNING in output


def test_project_health_help_exposes_supported_operations_and_warning() -> None:
    output = render_capability_help("project_health")
    assert "Capability: project_health" in output
    assert "Normal executable support: yes" in output
    assert "structured" in output
    assert "may execute local project code or tooling" in output
    assert "run_tests, lint_check, format_check, build_docs, run_evals" in output


def test_project_health_listed_as_normal_executable_command_and_example() -> None:
    commands = render_commands()
    examples = render_examples()
    command_help = render_command_help("project_health")

    assert "project_health:\n  - project_health" in commands
    assert "run tests" in examples
    assert "Status: structured (normal executable support)" in command_help
    assert "Direct support: no" in command_help
    assert "Normal executable support: yes" in command_help
    assert "Arbitrary 'poetry run ...'" in command_help


def test_discovery_hides_profile_disabled_capabilities_and_commands() -> None:
    disabled = frozenset({"dangerous", "network"})

    capabilities = render_capabilities(disabled_pack_ids=disabled)
    commands = render_commands(disabled_pack_ids=disabled)
    examples = render_examples(disabled_pack_ids=disabled)

    assert "network_diagnostics" not in capabilities
    assert "network_diagnostics" not in commands
    assert "network_diagnostics" not in examples
    assert "ping" not in commands
    assert "destructive_operations" not in capabilities
    assert "\n  - rm" not in commands
    assert "git_inspection" in capabilities


def test_discovery_help_for_disabled_targets_returns_unknown() -> None:
    disabled = frozenset({"dangerous", "network"})

    assert "Unknown capability" in render_capability_help(
        "network_diagnostics", disabled_pack_ids=disabled
    )
    assert "Unknown command family" in render_command_help("ping", disabled_pack_ids=disabled)


def test_discovery_outputs_style_owned_labels_when_enabled() -> None:
    style = TerminalStyle(color_enabled=True)

    outputs = [
        render_help(style=style),
        render_capabilities(style=style),
        render_commands(style=style),
        render_examples(style=style),
        render_capability_help("filesystem_inspection", style=style),
        render_command_help("ls", style=style),
    ]

    for output in outputs:
        assert ANSI_RE.search(output)
    assert "Capabilities:" in outputs[1]
    assert "filesystem_inspection" in outputs[1]
    assert "Command family:" in outputs[5]
    assert "Risk level:" in outputs[5]


def test_discovery_disabled_style_outputs_plain_text() -> None:
    style = TerminalStyle(color_enabled=False)

    output = render_capabilities(style=style)

    assert not ANSI_RE.search(output)
    assert "Capabilities:" in output
    assert "filesystem_inspection" in output

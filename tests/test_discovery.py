from oterminus.commands import NETWORK_TOUCHING_WARNING, command
from oterminus.discovery import render_capability_help, render_command_help
from oterminus.models import RiskLevel


def test_command_help_exposes_network_touching_warning(monkeypatch) -> None:
    spec = command(
        name="netcheck",
        category="network_inspection",
        capability_id="synthetic_network",
        capability_label="Synthetic network",
        capability_description="Synthetic read-only network diagnostics.",
        risk_level=RiskLevel.SAFE,
        network_touching=True,
    )
    monkeypatch.setattr("oterminus.discovery.get_command_spec", lambda name: spec)

    output = render_command_help("netcheck")

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

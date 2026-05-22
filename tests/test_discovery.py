from oterminus.commands import NETWORK_TOUCHING_WARNING, command
from oterminus.discovery import render_command_help
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

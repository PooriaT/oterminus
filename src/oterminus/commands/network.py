from oterminus.models import RiskLevel

from .types import CommandSpec, NETWORK_TOUCHING_WARNING, command

NETWORK_DIAGNOSTICS = {
    "capability_id": "network_diagnostics",
    "capability_label": "Network diagnostics",
    "capability_description": "Run constrained read-only diagnostics that contact external hosts.",
}

NETWORK_NOTES = (
    NETWORK_TOUCHING_WARNING,
    "Only ping with a fixed count, HTTP HEAD requests, dig lookups, and nslookup lookups are supported.",
    "POST/PUT/PATCH/DELETE, request bodies, arbitrary or secret-bearing headers, authorization, cookies, downloads, redirects that write files, scanning, traceroute, SSH/SCP, netcat, nmap, wget, sudo network commands, and arbitrary network shell commands are not supported.",
)

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="ping",
        category="network_inspection",
        **NETWORK_DIAGNOSTICS,
        risk_level=RiskLevel.SAFE,
        min_operands=2,
        max_operands=2,
        flags_with_values=("-c",),
        examples=("ping -c 4 example.com",),
        natural_language_aliases=("ping host", "check host responds"),
        notes=NETWORK_NOTES,
        network_touching=True,
    ),
    command(
        name="curl",
        category="network_inspection",
        **NETWORK_DIAGNOSTICS,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        max_operands=1,
        allowed_flags=("-I",),
        examples=("curl -I https://example.com",),
        natural_language_aliases=("show HTTP headers", "http head request"),
        notes=NETWORK_NOTES,
        network_touching=True,
    ),
    command(
        name="dig",
        category="network_inspection",
        **NETWORK_DIAGNOSTICS,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        max_operands=1,
        examples=("dig example.com",),
        natural_language_aliases=("dns lookup", "get dns records"),
        notes=NETWORK_NOTES,
        network_touching=True,
    ),
    command(
        name="nslookup",
        category="network_inspection",
        **NETWORK_DIAGNOSTICS,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        max_operands=1,
        examples=("nslookup example.com",),
        natural_language_aliases=("nslookup", "dns lookup alternative"),
        notes=NETWORK_NOTES,
        network_touching=True,
    ),
)

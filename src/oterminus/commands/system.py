from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, command

SYSTEM_INSPECTION = {
    "capability_id": "system_inspection",
    "capability_label": "System inspection",
    "capability_description": "Inspect local environment, identity, and system properties.",
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="whoami",
        category="system_inspection",
        **SYSTEM_INSPECTION,
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.ZERO_OPERANDS,
        examples=("whoami",),
        natural_language_aliases=("current user",),
    ),
    command(
        name="uname",
        category="system_inspection",
        **SYSTEM_INSPECTION,
        risk_level=RiskLevel.SAFE,
        allowed_flags=("-a", "-m", "-n", "-r", "-s", "-v"),
        examples=("uname -a",),
        natural_language_aliases=("system name", "kernel info"),
    ),
    command(
        name="which",
        category="system_inspection",
        **SYSTEM_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        allowed_flags=("-a",),
        examples=("which python3",),
        natural_language_aliases=("find executable",),
    ),
    command(
        name="env",
        category="system_inspection",
        **SYSTEM_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=0,
        examples=("env PATH",),
        natural_language_aliases=("environment variable",),
        notes=("Printing the full environment may include sensitive values; prefer querying specific variable names.",),
    ),
    command(
        name="df",
        category="inspection",
        **SYSTEM_INSPECTION,
        risk_level=RiskLevel.SAFE,
        allowed_flags=("-h",),
        examples=("df -h",),
        natural_language_aliases=("disk space",),
    ),
)

from oterminus.models import RiskLevel

from .types import CommandSpec, MaturityLevel, command

DESTRUCTIVE_OPERATIONS = {
    "capability_id": "destructive_operations",
    "capability_label": "Destructive operations",
    "capability_description": "High-risk operations that can remove data or escalate privileges.",
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="rm",
        category="destructive",
        **DESTRUCTIVE_OPERATIONS,
        risk_level=RiskLevel.DANGEROUS,
        maturity_level=MaturityLevel.EXPERIMENTAL_ONLY,
        min_operands=1,
        dangerous_flags=("-r", "-rf", "-fr"),
        allowed_flags=("-f", "-i"),
        examples=("rm -i old.log",),
        natural_language_aliases=("remove file", "delete file"),
    ),
    command(
        name="sudo",
        category="privileged",
        **DESTRUCTIVE_OPERATIONS,
        risk_level=RiskLevel.DANGEROUS,
        maturity_level=MaturityLevel.BLOCKED,
        min_operands=1,
        direct_supported=False,
        examples=("sudo ls /var/root",),
        natural_language_aliases=("run as root", "elevated command"),
    ),
)

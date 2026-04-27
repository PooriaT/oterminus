from oterminus.models import RiskLevel

from .types import CommandSpec, command

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(name="rm", category="destructive", risk_level=RiskLevel.DANGEROUS, min_operands=1, dangerous_flags=("-r", "-rf", "-fr"), allowed_flags=("-f", "-i", "-r", "-rf", "-fr")),
    command(name="sudo", category="privileged", risk_level=RiskLevel.DANGEROUS, min_operands=1),
)

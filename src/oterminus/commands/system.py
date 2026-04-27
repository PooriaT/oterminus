from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, command

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(name="whoami", category="system_inspection", risk_level=RiskLevel.SAFE, direct_detection_mode=DirectDetectionMode.ZERO_OPERANDS),
    command(name="uname", category="system_inspection", risk_level=RiskLevel.SAFE, allowed_flags=("-a", "-m", "-n", "-r", "-s", "-v")),
    command(name="which", category="system_inspection", risk_level=RiskLevel.SAFE, min_operands=1, allowed_flags=("-a",)),
    command(name="env", category="system_inspection", risk_level=RiskLevel.SAFE, min_operands=0, notes=("Printing the full environment may include sensitive values; prefer querying specific variable names.",)),
    command(name="df", category="inspection", risk_level=RiskLevel.SAFE, allowed_flags=("-h",)),
)

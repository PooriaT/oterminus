from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, command

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(name="cat", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1),
    command(name="head", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1, flags_with_values=("-n", "-c")),
    command(name="tail", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1, flags_with_values=("-n", "-c")),
    command(name="grep", category="search", risk_level=RiskLevel.SAFE, min_operands=1, direct_detection_mode=DirectDetectionMode.GREP, flags_with_values=("-e", "-f", "-m"), path_valued_flags=("-f",), allowed_flags=("-E", "-F", "-H", "-h", "-i", "-l", "-n", "-r", "-R")),
    command(name="wc", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1, allowed_flags=("-c", "-l", "-w")),
    command(name="sort", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1, allowed_flags=("-n", "-r", "-u")),
    command(name="uniq", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1, allowed_flags=("-c", "-d", "-u")),
)

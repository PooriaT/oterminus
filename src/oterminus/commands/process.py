from oterminus.models import RiskLevel

from .types import CommandSpec, command

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(name="ps", category="process_inspection", risk_level=RiskLevel.SAFE, allowed_flags=("-A", "-e", "-f"), flags_with_values=("-p", "-u")),
    command(name="pgrep", category="process_inspection", risk_level=RiskLevel.SAFE, min_operands=1, allowed_flags=("-f", "-l"), flags_with_values=("-u",)),
    command(name="lsof", category="process_inspection", risk_level=RiskLevel.SAFE, allowed_flags=("-a", "-n", "-P"), flags_with_values=("-c", "-p"), notes=("Lists open files and sockets; output can expose sensitive process or path information.",)),
)

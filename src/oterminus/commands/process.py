from oterminus.models import RiskLevel

from .types import CommandSpec, command

PROCESS_INSPECTION = {
    "capability_id": "process_inspection",
    "capability_label": "Process inspection",
    "capability_description": "Inspect running processes and open files.",
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="ps",
        category="process_inspection",
        **PROCESS_INSPECTION,
        risk_level=RiskLevel.SAFE,
        allowed_flags=("-A", "-e", "-f"),
        flags_with_values=("-p", "-u"),
        examples=("ps -A",),
        natural_language_aliases=("show running processes",),
    ),
    command(
        name="pgrep",
        category="process_inspection",
        **PROCESS_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        allowed_flags=("-f", "-l"),
        flags_with_values=("-u",),
        examples=("pgrep -f python",),
        natural_language_aliases=("find process by name",),
    ),
    command(
        name="lsof",
        category="process_inspection",
        **PROCESS_INSPECTION,
        risk_level=RiskLevel.SAFE,
        allowed_flags=("-a", "-n", "-P"),
        flags_with_values=("-c", "-p"),
        examples=("lsof -p 1234",),
        natural_language_aliases=("open files for process",),
        notes=("Lists open files and sockets; output can expose sensitive process or path information.",),
    ),
)

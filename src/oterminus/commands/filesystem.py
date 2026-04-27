from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, PathOperandMode, command

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="cd",
        category="navigation",
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.CD,
        path_operand_mode=PathOperandMode.CD,
        notes=("Changes the oterminus working directory for the current REPL session.",),
    ),
    command(name="ls", category="inspection", risk_level=RiskLevel.SAFE, allowed_flags=("-a", "-h", "-l", "-R")),
    command(name="pwd", category="navigation", risk_level=RiskLevel.SAFE, direct_detection_mode=DirectDetectionMode.ZERO_OPERANDS),
    command(
        name="find",
        category="search",
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.FIND,
        path_operand_mode=PathOperandMode.FIND,
        leading_flags=("-H", "-L", "-P"),
        leading_flags_with_values=("-D", "-O"),
        leading_flags_with_inline_values=("-O",),
        allowed_flags=("-name", "-path", "-type", "-maxdepth", "-mindepth", "-print"),
    ),
    command(
        name="du",
        category="inspection",
        risk_level=RiskLevel.SAFE,
        allowed_flags=("-a", "-c", "-h", "-k", "-s", "-x"),
        flags_with_values=("-d",),
    ),
    command(
        name="stat",
        category="inspection",
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        allowed_flags=("-L", "-x"),
        flags_with_values=("-f",),
    ),
    command(name="mkdir", category="filesystem_write", risk_level=RiskLevel.WRITE, min_operands=1, allowed_flags=("-p",)),
    command(name="cp", category="filesystem_write", risk_level=RiskLevel.WRITE, min_operands=2, allowed_flags=("-R", "-n", "-p")),
    command(name="mv", category="filesystem_write", risk_level=RiskLevel.WRITE, min_operands=2, allowed_flags=("-n",)),
    command(
        name="chmod",
        category="permissions",
        risk_level=RiskLevel.WRITE,
        min_operands=2,
        flags_with_values=("--context", "--reference"),
        path_valued_flags=("--reference",),
        dangerous_target_literals=("/", "/*"),
    ),
    command(name="touch", category="filesystem_write", risk_level=RiskLevel.WRITE, min_operands=1),
    command(
        name="chown",
        category="permissions",
        risk_level=RiskLevel.DANGEROUS,
        min_operands=2,
        dangerous_target_literals=("/", "/*"),
    ),
    command(name="file", category="inspection", risk_level=RiskLevel.SAFE, min_operands=1, allowed_flags=("-b",)),
)

from oterminus.models import RiskLevel

from .types import CommandSpec, command

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(name="open", category="macos_integration", risk_level=RiskLevel.SAFE, min_operands=1, allowed_flags=("-R",), forbidden_operand_prefixes=("http://", "https://", "ftp://", "mailto:"), notes=("Opens a local file or folder via macOS LaunchServices.",)),
)

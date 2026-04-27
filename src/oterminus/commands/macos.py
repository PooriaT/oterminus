from oterminus.models import RiskLevel

from .types import CommandSpec, command

MACOS_DESKTOP = {
    "capability_id": "macos_desktop",
    "capability_label": "macOS desktop integration",
    "capability_description": "Open local paths in Finder or default macOS apps.",
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="open",
        category="macos_integration",
        **MACOS_DESKTOP,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        allowed_flags=("-R",),
        forbidden_operand_prefixes=("http://", "https://", "ftp://", "mailto:"),
        examples=("open .",),
        natural_language_aliases=("open in finder", "reveal in finder"),
        notes=("Opens a local file or folder via macOS LaunchServices.",),
    ),
)

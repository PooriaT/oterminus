from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, command

ARCHIVE_INSPECTION = {
    "capability_id": "archive_inspection",
    "capability_label": "Archive inspection",
    "capability_description": "Inspect archive contents without extracting or modifying files.",
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="tar",
        category="archive_inspection",
        **ARCHIVE_INSPECTION,
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.MIN_OPERANDS,
        min_operands=1,
        max_operands=1,
        examples=("tar -tf archive.tar",),
        natural_language_aliases=(
            "list tar archive",
            "inspect tar archive",
            "show tar contents",
            "list archive contents",
        ),
        notes=(
            "Only read-only tar archive listing is supported in curated mode; extraction and creation are not supported.",
        ),
    ),
    command(
        name="unzip",
        category="archive_inspection",
        **ARCHIVE_INSPECTION,
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.MIN_OPERANDS,
        min_operands=1,
        max_operands=1,
        examples=("unzip -l archive.zip",),
        natural_language_aliases=(
            "list zip archive",
            "inspect zip archive",
            "show zip contents",
            "show what is inside zip",
        ),
        notes=(
            "Only read-only zip archive listing is supported in curated mode; extraction and creation are not supported.",
        ),
    ),
)

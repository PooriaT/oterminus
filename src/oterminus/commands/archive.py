from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, command

ARCHIVE_INSPECTION = {
    "capability_id": "archive_inspection",
    "capability_label": "Archive inspection",
    "capability_description": "Inspect archives and extract them only to explicit destinations.",
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="tar",
        category="archive_inspection",
        **ARCHIVE_INSPECTION,
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.MIN_OPERANDS,
        min_operands=1,
        max_operands=3,
        examples=("tar -tf archive.tar", "tar -xf archive.tar -C out"),
        natural_language_aliases=(
            "list tar archive",
            "inspect tar archive",
            "show tar contents",
            "list archive contents",
            "extract tar archive",
            "extract archive into destination",
        ),
        notes=(
            "Supports read-only tar archive listing and guarded extraction with an explicit destination.",
            "Tar extraction is write-risk and can write or overwrite files in the destination.",
            "Archive creation, compression flags, path transforms, extraction without -C, and arbitrary tar options are not supported.",
        ),
    ),
    command(
        name="unzip",
        category="archive_inspection",
        **ARCHIVE_INSPECTION,
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.MIN_OPERANDS,
        min_operands=1,
        max_operands=2,
        examples=("unzip -l archive.zip", "unzip archive.zip -d out"),
        natural_language_aliases=(
            "list zip archive",
            "inspect zip archive",
            "show zip contents",
            "show what is inside zip",
            "extract zip archive",
            "unzip archive into destination",
        ),
        notes=(
            "Supports read-only zip archive listing and guarded extraction with an explicit destination.",
            "Zip extraction is write-risk and can write or overwrite files in the destination.",
            "Extraction without -d, overwrite flags, password handling, and arbitrary unzip options are not supported.",
        ),
    ),
)

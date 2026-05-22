from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, command

ARCHIVE_INSPECTION = {
    "capability_id": "archive_inspection",
    "capability_label": "Archive operations",
    "capability_description": (
        "Inspect archives, extract them only to explicit destinations, and create tar.gz/zip "
        "archives only from explicit source paths."
    ),
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="tar",
        category="archive_inspection",
        **ARCHIVE_INSPECTION,
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.MIN_OPERANDS,
        min_operands=1,
        max_operands=None,
        examples=(
            "tar -tf archive.tar",
            "tar -xf archive.tar -C out",
            "tar -czf backup.tar.gz src",
        ),
        natural_language_aliases=(
            "list tar archive",
            "inspect tar archive",
            "show tar contents",
            "list archive contents",
            "extract tar archive",
            "extract archive into destination",
            "create tar gz archive",
            "create tar archive from explicit paths",
        ),
        notes=(
            "Supports read-only tar archive listing, guarded extraction with an explicit destination, and guarded tar.gz creation from explicit source paths.",
            "Tar extraction is write-risk and can write or overwrite files in the destination.",
            "Tar archive creation is write-risk and may overwrite an existing archive path depending on the underlying tar implementation.",
            "Only tar -czf <archive_path> <source_paths...> is supported for tar.gz creation; broad roots, home roots, wildcards, path transforms, extraction without -C, and arbitrary tar options are not supported.",
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
    command(
        name="zip",
        category="archive_inspection",
        **ARCHIVE_INSPECTION,
        risk_level=RiskLevel.WRITE,
        direct_detection_mode=DirectDetectionMode.MIN_OPERANDS,
        min_operands=3,
        max_operands=None,
        examples=("zip -r backup.zip src",),
        natural_language_aliases=(
            "create zip archive",
            "zip folder into archive",
            "create zip archive from explicit paths",
        ),
        notes=(
            "Supports guarded zip archive creation from explicit source paths.",
            "Zip archive creation is write-risk and may overwrite or update an existing archive path depending on the underlying zip implementation.",
            "Only zip -r <archive_path> <source_paths...> is supported; broad roots, home roots, wildcards, encryption, passwords, split archives, append/update flags, deleting sources, network destinations, and arbitrary zip options are not supported.",
        ),
    ),
)

from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, command

TEXT_INSPECTION = {
    "capability_id": "text_inspection",
    "capability_label": "Text inspection",
    "capability_description": "Inspect, filter, and transform file text content.",
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="cat",
        category="inspection",
        **TEXT_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        examples=("cat README.md",),
        natural_language_aliases=("show file contents", "print file"),
    ),
    command(
        name="head",
        category="inspection",
        **TEXT_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        flags_with_values=("-n", "-c"),
        examples=("head -n 20 README.md",),
        natural_language_aliases=("first lines",),
    ),
    command(
        name="tail",
        category="inspection",
        **TEXT_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        flags_with_values=("-n", "-c"),
        examples=("tail -n 50 app.log",),
        natural_language_aliases=("last lines",),
    ),
    command(
        name="grep",
        category="search",
        **TEXT_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        direct_detection_mode=DirectDetectionMode.GREP,
        flags_with_values=("-e", "-f", "-m"),
        path_valued_flags=("-f",),
        allowed_flags=("-E", "-F", "-H", "-h", "-i", "-l", "-n", "-r", "-R"),
        examples=("grep -n TODO src/main.py",),
        natural_language_aliases=("search text", "find matching lines"),
    ),
    command(
        name="wc",
        category="inspection",
        **TEXT_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        allowed_flags=("-c", "-l", "-w"),
        examples=("wc -l README.md",),
        natural_language_aliases=("count lines", "count words"),
    ),
    command(
        name="sort",
        category="inspection",
        **TEXT_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        allowed_flags=("-n", "-r", "-u"),
        examples=("sort -u names.txt",),
        natural_language_aliases=("sort lines",),
    ),
    command(
        name="uniq",
        category="inspection",
        **TEXT_INSPECTION,
        risk_level=RiskLevel.SAFE,
        min_operands=1,
        allowed_flags=("-c", "-d", "-u"),
        examples=("uniq -c names.txt",),
        natural_language_aliases=("dedupe lines", "unique lines"),
    ),
)

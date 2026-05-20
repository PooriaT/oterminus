from oterminus.models import RiskLevel

from .types import CommandSpec, DirectDetectionMode, command

GIT_INSPECTION = {
    "capability_id": "git_inspection",
    "capability_label": "Git inspection",
    "capability_description": "Read-only inspection of local Git repository state.",
}

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="git",
        category="git_inspection",
        **GIT_INSPECTION,
        risk_level=RiskLevel.SAFE,
        direct_detection_mode=DirectDetectionMode.MIN_OPERANDS,
        min_operands=2,
        max_operands=4,
        examples=(
            "git status --short",
            "git branch --show-current",
            "git log --oneline -n 5",
            "git diff --stat",
            "git diff --name-only",
        ),
        natural_language_aliases=(
            "git status",
            "short git status",
            "what branch am i on",
            "show current git branch",
            "show recent git commits",
            "show git diff summary",
            "show changed files",
            "inspect git repo",
        ),
        notes=("Only read-only Git inspection operations are supported in curated mode.",),
    ),
)

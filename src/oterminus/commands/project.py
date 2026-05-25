from oterminus.models import RiskLevel

from .types import CommandSpec, MaturityLevel, command

PROJECT_HEALTH = {
    "capability_id": "project_health",
    "capability_label": "Project health",
    "capability_description": (
        "Curated project maintenance checks (tests, lint, format check, docs build, evals) "
        "modeled for explicit preview and confirmation."
    ),
}

PROJECT_HEALTH_WARNING = (
    "Project health operations may execute local project code or tooling (for example via test suites, "
    "docs builds, and eval workflows).",
    "Always preview and require explicit user confirmation before execution.",
    "Only curated operations are in scope: run_tests, lint_check, format_check, build_docs, run_evals.",
    "Arbitrary 'poetry run ...' and arbitrary shell execution are not supported.",
)

COMMAND_PACK: tuple[CommandSpec, ...] = (
    command(
        name="project_health",
        category="developer_workflow",
        **PROJECT_HEALTH,
        risk_level=RiskLevel.WRITE,
        maturity_level=MaturityLevel.STRUCTURED,
        direct_supported=False,
        min_operands=0,
        max_operands=0,
        examples=(
            "project_health run_tests",
            "project_health lint_check",
            "project_health format_check",
            "project_health build_docs",
            "project_health run_evals",
        ),
        natural_language_aliases=(
            "run project tests",
            "check project formatting",
            "run project lint",
            "build project docs",
            "run project evals",
        ),
        notes=PROJECT_HEALTH_WARNING,
    ),
)

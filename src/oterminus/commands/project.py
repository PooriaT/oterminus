from oterminus.models import RiskLevel

from .types import CommandSpec, MaturityLevel, command

PROJECT_HEALTH = {
    "capability_id": "project_health",
    "capability_label": "Project health",
    "capability_description": (
        "Curated project maintenance checks for tests, lint, format checks, docs builds, and evals."
    ),
}

PROJECT_HEALTH_WARNING = (
    "Project health operations may execute local project code or tooling (for example via test suites, "
    "docs builds, and eval workflows).",
    "Always preview and require explicit user confirmation before execution.",
    "Only curated operations are in scope: run_tests, lint_check, format_check, build_docs, run_evals.",
    "Arbitrary 'poetry run ...', install/update/deploy/publish commands, write-formatting, and "
    "arbitrary shell execution are not supported.",
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
            "run tests",
            "check linting",
            "run format check",
            "build docs",
            "run evals",
        ),
        natural_language_aliases=(
            "run tests",
            "run the test suite",
            "run project tests",
            "check linting",
            "run ruff check",
            "check formatting",
            "run format check",
            "check project formatting",
            "run project lint",
            "build docs",
            "build project docs",
            "run evals",
            "run project evals",
        ),
        notes=PROJECT_HEALTH_WARNING,
    ),
)

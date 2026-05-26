from __future__ import annotations

from pathlib import Path

import tomllib

from oterminus.evals import default_fixtures_dir


def test_console_scripts_declared() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    scripts = pyproject["tool"]["poetry"]["scripts"]

    assert scripts["oterminus"] == "oterminus.cli:main"
    assert scripts["oterminus-evals"] == "oterminus.evals:main"


def test_default_eval_fixtures_dir_exists_and_has_cases() -> None:
    fixtures_dir = default_fixtures_dir()

    assert fixtures_dir.exists()
    assert any(fixtures_dir.glob("*.json"))

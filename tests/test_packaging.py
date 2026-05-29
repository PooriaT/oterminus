from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
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


def test_validate_package_install_checks_cli_version(monkeypatch, tmp_path: Path) -> None:
    import subprocess

    module_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_package_install.py"
    spec = spec_from_file_location("validate_package_install", module_path)
    assert spec and spec.loader
    validate_package_install = module_from_spec(spec)
    spec.loader.exec_module(validate_package_install)

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel = dist_dir / "oterminus-0.1.1-py3-none-any.whl"
    wheel.write_text("wheel")
    recorded: list[list[str]] = []

    def fake_run(cmd: list[str], *, cwd: Path | None = None, check: bool = True):
        del cwd, check
        recorded.append(cmd)
        if cmd[-1] == 'from importlib.metadata import version; print(version("oterminus"))':
            return subprocess.CompletedProcess(cmd, 0, stdout="0.1.1\n", stderr="")
        if cmd[-1] in {"--version", "version"}:
            return subprocess.CompletedProcess(cmd, 0, stdout="oterminus 0.1.1\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(validate_package_install, "DIST_DIR", dist_dir)
    monkeypatch.setattr(validate_package_install, "run", fake_run)

    assert validate_package_install.main() == 0
    assert any(cmd[-1] == "--version" for cmd in recorded)
    assert any(cmd[-1] == "version" for cmd in recorded)

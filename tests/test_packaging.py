from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
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
    command_envs: list[dict[str, str] | None] = []

    def fake_run(
        cmd: list[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
        env: dict[str, str] | None = None,
    ):
        del cwd, check
        recorded.append(cmd)
        command_envs.append(env)
        if cmd[-1] == 'from importlib.metadata import version; print(version("oterminus"))':
            return subprocess.CompletedProcess(cmd, 0, stdout="0.1.1\n", stderr="")
        if cmd[-1] in {"--version", "version"}:
            return subprocess.CompletedProcess(cmd, 0, stdout="oterminus 0.1.1\n", stderr="")
        if cmd[-2:] == ["config", "path"]:
            assert env is not None
            return subprocess.CompletedProcess(
                cmd, 0, stdout=f"{env['OTERMINUS_CONFIG_PATH']}\n", stderr=""
            )
        if cmd[-3:] == ["config", "init", "--defaults"]:
            assert env is not None
            Path(env["OTERMINUS_CONFIG_PATH"]).parent.mkdir(parents=True, exist_ok=True)
            Path(env["OTERMINUS_CONFIG_PATH"]).write_text('{"schema_version": 1}\n')
            return subprocess.CompletedProcess(cmd, 0, stdout="Created config\n", stderr="")
        if cmd[-3:] == ["config", "get", "color_mode"]:
            assert env is not None
            config_path = Path(env["OTERMINUS_CONFIG_PATH"])
            if config_path.exists() and "never" in config_path.read_text():
                return subprocess.CompletedProcess(cmd, 0, stdout="color_mode=never\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="color_mode=auto\n", stderr="")
        if cmd[-4:] == ["config", "set", "color_mode", "never"]:
            assert env is not None
            config_path = Path(env["OTERMINUS_CONFIG_PATH"])
            config_path.write_text('{"schema_version": 1, "color_mode": "never"}\n')
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Updated color_mode=never\n", stderr=""
            )
        if cmd[-3:] == ["config", "reset", "color_mode"]:
            assert env is not None
            config_path = Path(env["OTERMINUS_CONFIG_PATH"])
            config_path.write_text('{"schema_version": 1}\n')
            return subprocess.CompletedProcess(cmd, 0, stdout="Reset color_mode\n", stderr="")
        if cmd[-4:] == ["config", "set", "audit_enabled", "false"]:
            assert env is not None
            config_path = Path(env["OTERMINUS_CONFIG_PATH"])
            config_path.write_text('{"schema_version": 1, "audit_enabled": false}\n')
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Updated audit_enabled=false\n", stderr=""
            )
        if cmd[-3:] == ["config", "reset", "--all-safe"]:
            assert env is not None
            config_path = Path(env["OTERMINUS_CONFIG_PATH"])
            config_path.write_text('{"schema_version": 1}\n')
            return subprocess.CompletedProcess(cmd, 0, stdout="Reset safe config keys\n", stderr="")
        if cmd[-2:] == ["config", "validate"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Status: valid\n", stderr="")
        if cmd[-2:] == ["config", "show"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="Active config path: /tmp/config.json\nSettings:\n", stderr=""
            )
        if cmd[-2:] == ["completion", "zsh"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="#compdef oterminus\n", stderr="")
        if cmd[-2:] == ["completion", "bash"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="complete -F _oterminus_completion oterminus\n", stderr=""
            )
        if cmd[-2:] == ["completion", "fish"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="complete -c oterminus\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(validate_package_install, "DIST_DIR", dist_dir)
    monkeypatch.setattr(validate_package_install, "clean_dist", lambda: None)
    monkeypatch.setattr(validate_package_install, "run", fake_run)

    assert validate_package_install.main() == 0
    assert any(cmd[-1] == "--version" for cmd in recorded)
    assert any(cmd[-1] == "version" for cmd in recorded)
    assert any(cmd[-2:] == ["config", "path"] for cmd in recorded)
    assert any(cmd[-3:] == ["config", "init", "--defaults"] for cmd in recorded)
    assert any(cmd[-3:] == ["config", "get", "color_mode"] for cmd in recorded)
    assert any(cmd[-4:] == ["config", "set", "color_mode", "never"] for cmd in recorded)
    assert any(cmd[-3:] == ["config", "reset", "color_mode"] for cmd in recorded)
    assert any(cmd[-4:] == ["config", "set", "audit_enabled", "false"] for cmd in recorded)
    assert any(cmd[-3:] == ["config", "reset", "--all-safe"] for cmd in recorded)
    assert any(cmd[-2:] == ["config", "validate"] for cmd in recorded)
    assert any(cmd[-2:] == ["config", "show"] for cmd in recorded)
    assert any(cmd[-2:] == ["completion", "zsh"] for cmd in recorded)
    assert any(cmd[-2:] == ["completion", "bash"] for cmd in recorded)
    assert any(cmd[-2:] == ["completion", "fish"] for cmd in recorded)
    assert any(env and "OTERMINUS_CONFIG_PATH" in env for env in command_envs)


@pytest.mark.parametrize(
    ("shell", "stdout"),
    (
        ("zsh", "#compdef oterminus\n"),
        ("bash", "complete -F _oterminus_completion oterminus\n"),
        ("fish", "complete -c oterminus\n"),
    ),
)
def test_validate_package_install_accepts_completion_output(shell: str, stdout: str) -> None:
    import subprocess

    module_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_package_install.py"
    spec = spec_from_file_location("validate_package_install", module_path)
    assert spec and spec.loader
    validate_package_install = module_from_spec(spec)
    spec.loader.exec_module(validate_package_install)

    proc = subprocess.CompletedProcess(
        ["oterminus", "completion", shell], 0, stdout=stdout, stderr=""
    )

    validate_package_install.validate_completion_output(shell, proc)


def test_validate_package_install_rejects_empty_completion_output() -> None:
    import subprocess

    module_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_package_install.py"
    spec = spec_from_file_location("validate_package_install", module_path)
    assert spec and spec.loader
    validate_package_install = module_from_spec(spec)
    spec.loader.exec_module(validate_package_install)

    proc = subprocess.CompletedProcess(["oterminus", "completion", "zsh"], 0, stdout="", stderr="")

    with pytest.raises(SystemExit):
        validate_package_install.validate_completion_output("zsh", proc)


def test_package_validation_smoke_env_uses_temp_paths(monkeypatch, tmp_path: Path) -> None:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_package_install.py"
    spec = spec_from_file_location("validate_package_install", module_path)
    assert spec and spec.loader
    validate_package_install = module_from_spec(spec)
    spec.loader.exec_module(validate_package_install)

    monkeypatch.setenv("OTERMINUS_COLOR", "auto")

    env = validate_package_install.smoke_env(tmp_path)

    assert env["OTERMINUS_CONFIG_PATH"] == str(tmp_path / "config" / "config.json")
    assert env["OTERMINUS_AUDIT_LOG_PATH"] == str(tmp_path / "audit" / "audit.jsonl")
    assert env["OTERMINUS_HISTORY_PATH"] == str(tmp_path / "history" / "history.jsonl")
    assert env["OTERMINUS_HISTORY_ENABLED"] == "false"
    assert "OTERMINUS_COLOR" not in env


def test_package_validation_cleans_dist_before_build(monkeypatch, tmp_path: Path) -> None:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_package_install.py"
    spec = spec_from_file_location("validate_package_install", module_path)
    assert spec and spec.loader
    validate_package_install = module_from_spec(spec)
    spec.loader.exec_module(validate_package_install)

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "stale.whl").write_text("stale")
    monkeypatch.setattr(validate_package_install, "DIST_DIR", dist_dir)

    validate_package_install.clean_dist()

    assert not dist_dir.exists()

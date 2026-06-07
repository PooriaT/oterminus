from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"


def section(title: str) -> None:
    print(f"\n==> {title}")


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=cwd or ROOT, text=True, capture_output=True, env=env)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip())
    if check and proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc


def validate_version_output(proc: subprocess.CompletedProcess[str]) -> str:
    output = proc.stdout.strip()
    match = re.fullmatch(r"oterminus\s+(\S+)", output)
    if match is None:
        print(f"Unexpected version output: {output!r}", file=sys.stderr)
        raise SystemExit(1)
    return match.group(1)


def validate_completion_output(shell: str, proc: subprocess.CompletedProcess[str]) -> None:
    output = proc.stdout.strip()
    expected_markers = {
        "zsh": "#compdef oterminus",
        "bash": "complete -F _oterminus_completion oterminus",
        "fish": "complete -c oterminus",
    }
    expected_marker = expected_markers[shell]
    if not output or expected_marker not in output:
        print(
            f"Unexpected {shell} completion output: {output!r}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def validate_config_smoke(
    oterminus: Path, temp_dir: Path, env: dict[str, str]
) -> None:
    config_path = temp_dir / "config" / "config.json"
    path_proc = run([str(oterminus), "config", "path"], env=env)
    if path_proc.stdout.strip() != str(config_path):
        print(
            "Unexpected config path output: "
            f"expected={str(config_path)!r} actual={path_proc.stdout.strip()!r}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if config_path.exists():
        print("config path unexpectedly created a file.", file=sys.stderr)
        raise SystemExit(1)

    run([str(oterminus), "config", "init", "--defaults"], env=env)
    if not config_path.exists() or not config_path.is_file():
        print(f"config init did not create {config_path}", file=sys.stderr)
        raise SystemExit(1)
    if temp_dir not in config_path.parents:
        print(f"config init wrote outside the smoke temp directory: {config_path}", file=sys.stderr)
        raise SystemExit(1)

    validate_proc = run([str(oterminus), "config", "validate"], env=env)
    if "Status: valid" not in validate_proc.stdout:
        print(f"Unexpected config validate output: {validate_proc.stdout!r}", file=sys.stderr)
        raise SystemExit(1)

    show_proc = run([str(oterminus), "config", "show"], env=env)
    if "Active config path:" not in show_proc.stdout or "Settings:" not in show_proc.stdout:
        print(f"Unexpected config show output: {show_proc.stdout!r}", file=sys.stderr)
        raise SystemExit(1)


def script_path(bin_dir: Path, name: str) -> Path:
    if sys.platform == "win32":
        return bin_dir / f"{name}.exe"
    return bin_dir / name


def smoke_env(td: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["OTERMINUS_CONFIG_PATH"] = str(td / "config" / "config.json")
    env["OTERMINUS_AUDIT_LOG_PATH"] = str(td / "audit" / "audit.jsonl")
    env["OTERMINUS_HISTORY_PATH"] = str(td / "history" / "history.jsonl")
    env["OTERMINUS_HISTORY_ENABLED"] = "false"
    return env


def clean_dist() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)


def main() -> int:
    section("Build package distributions")
    clean_dist()
    run(["poetry", "build"])

    wheels = sorted(DIST_DIR.glob("oterminus-*.whl"))
    if not wheels:
        print("No wheel found in dist/.", file=sys.stderr)
        return 1
    wheel = wheels[-1]

    with tempfile.TemporaryDirectory(prefix="oterminus-wheel-") as td:
        temp_dir = Path(td)
        venv_dir = temp_dir / "venv"
        env = smoke_env(temp_dir)

        section("Create clean virtual environment")
        run([sys.executable, "-m", "venv", str(venv_dir)])

        bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
        py = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
        pip = bin_dir / ("pip.exe" if sys.platform == "win32" else "pip")

        section(f"Install built wheel: {wheel.name}")
        run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        run([str(pip), "install", str(wheel)])

        section("Validate installed package import and metadata")
        run([str(py), "-c", "import oterminus"])
        installed_version = run(
            [
                str(py),
                "-c",
                'from importlib.metadata import version; print(version("oterminus"))',
            ]
        ).stdout.strip()
        oterminus = script_path(bin_dir, "oterminus")
        oterminus_evals = script_path(bin_dir, "oterminus-evals")

        section("Run installed CLI smoke checks")
        run([str(oterminus), "--help"], env=env)
        cli_version = validate_version_output(run([str(oterminus), "--version"], env=env))
        command_version = validate_version_output(run([str(oterminus), "version"], env=env))
        if cli_version != installed_version or command_version != installed_version:
            print(
                "Version command output does not match installed package metadata: "
                f"metadata={installed_version!r} --version={cli_version!r} "
                f"version={command_version!r}",
                file=sys.stderr,
            )
            return 1
        print("oterminus doctor may exit non-zero when Ollama is unavailable; continuing.")
        run([str(oterminus), "doctor"], check=False, env=env)

        section("Run installed config command smoke checks")
        validate_config_smoke(oterminus, temp_dir, env)

        section("Run installed shell completion smoke checks")
        for shell in ("zsh", "bash", "fish"):
            validate_completion_output(
                shell,
                run([str(oterminus), "completion", shell], env=env),
            )

        run([str(oterminus_evals)], env=env)

    section("Installed package smoke validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

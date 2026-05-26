from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"


def run(
    cmd: list[str], *, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd or ROOT, text=True, capture_output=True)
    print(f"$ {' '.join(cmd)}")
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip())
    if check and proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc


def script_path(bin_dir: Path, name: str) -> Path:
    if sys.platform == "win32":
        return bin_dir / f"{name}.exe"
    return bin_dir / name


def main() -> int:
    run(["poetry", "build"])

    wheels = sorted(DIST_DIR.glob("oterminus-*.whl"))
    if not wheels:
        print("No wheel found in dist/.", file=sys.stderr)
        return 1
    wheel = wheels[-1]

    with tempfile.TemporaryDirectory(prefix="oterminus-wheel-") as td:
        venv_dir = Path(td) / "venv"
        run([sys.executable, "-m", "venv", str(venv_dir)])

        bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
        py = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
        pip = bin_dir / ("pip.exe" if sys.platform == "win32" else "pip")

        run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        run([str(pip), "install", str(wheel)])
        run([str(py), "-c", "import oterminus"])
        oterminus = script_path(bin_dir, "oterminus")
        oterminus_evals = script_path(bin_dir, "oterminus-evals")

        run([str(oterminus), "--help"])
        run([str(oterminus), "doctor"], check=False)
        run([str(oterminus_evals)])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

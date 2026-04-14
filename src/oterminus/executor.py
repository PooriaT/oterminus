from __future__ import annotations

import shlex
import subprocess

from oterminus.models import ExecutionResult


class Executor:
    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds

    def run(self, command: str) -> ExecutionResult:
        args = shlex.split(command)
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return ExecutionResult(
            command=command,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

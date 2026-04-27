from __future__ import annotations

import os
import shlex
import subprocess

from oterminus.models import ExecutionResult


class Executor:
    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds
        self.previous_cwd: str | None = None

    def run(self, command: str | list[str], *, display_command: str | None = None) -> ExecutionResult:
        if isinstance(command, str):
            args = shlex.split(command)
            rendered_command = command
        else:
            args = list(command)
            rendered_command = display_command or shlex.join(args)

        if args and args[0] == "cd":
            return self._run_cd(args, rendered_command)
        if args and args[0] == "clear":
            return self._run_clear(rendered_command)

        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return ExecutionResult(
            command=rendered_command,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def _run_cd(self, args: list[str], rendered_command: str) -> ExecutionResult:
        old_cwd = os.getcwd()
        destination = args[1] if len(args) > 1 else "~"
        if destination == "-":
            if self.previous_cwd is None:
                raise OSError("No previous working directory is available.")
            target = self.previous_cwd
        else:
            target = os.path.expanduser(destination)

        os.chdir(target)
        self.previous_cwd = old_cwd
        new_cwd = os.getcwd()
        os.environ["OLDPWD"] = old_cwd
        os.environ["PWD"] = new_cwd

        return ExecutionResult(
            command=rendered_command,
            returncode=0,
            stdout=f"{new_cwd}\n",
            stderr="",
        )

    def _run_clear(self, rendered_command: str) -> ExecutionResult:
        # ANSI clear-screen + cursor-home sequence.
        return ExecutionResult(
            command=rendered_command,
            returncode=0,
            stdout="\033[2J\033[H",
            stderr="",
        )

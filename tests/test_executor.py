import os
import subprocess

from oterminus.executor import Executor


def test_executor_runs_command() -> None:
    executor = Executor(timeout_seconds=2)
    result = executor.run("pwd")

    assert result.returncode == 0
    assert result.stdout.strip()


def test_executor_cd_changes_working_directory(tmp_path) -> None:
    executor = Executor(timeout_seconds=2)
    original_cwd = os.getcwd()

    try:
        result = executor.run(f"cd {tmp_path}")
        assert result.returncode == 0
        assert os.getcwd() == str(tmp_path)
        assert result.stdout.strip() == str(tmp_path)
    finally:
        os.chdir(original_cwd)


def test_executor_runs_argv_command() -> None:
    executor = Executor(timeout_seconds=2)
    result = executor.run(["pwd"], display_command="pwd")

    assert result.returncode == 0
    assert result.command == "pwd"
    assert result.stdout.strip()


def test_executor_clear_uses_internal_terminal_sequence(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called for clear")

    monkeypatch.setattr(subprocess, "run", fail_if_called)
    executor = Executor(timeout_seconds=2)
    result = executor.run("clear")

    assert result.returncode == 0
    assert result.stdout == "\033[2J\033[H"
    assert result.stderr == ""

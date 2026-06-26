import os
import subprocess
from types import SimpleNamespace

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


def test_executor_pins_man_pager_environment(monkeypatch) -> None:
    monkeypatch.setenv("MANPAGER", "sh -c 'echo unsafe'")
    monkeypatch.setenv("PAGER", "sh -c 'echo unsafe'")
    monkeypatch.setenv("MANOPT", "-P sh")
    captured_env = {}

    def fake_run(*args, **kwargs):
        captured_env.update(kwargs["env"])
        return SimpleNamespace(returncode=0, stdout="manual text", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = Executor(timeout_seconds=2).run(["man", "ls"], display_command="man ls")

    assert result.returncode == 0
    assert captured_env["MANPAGER"] == "cat"
    assert captured_env["PAGER"] == "cat"
    assert captured_env["MANOPT"] == ""


def test_executor_truncates_stdout_and_stderr(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=7, stdout="a" * 10, stderr="b" * 9)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = Executor(timeout_seconds=2, max_output_chars=5).run("echo test")
    assert result.returncode == 7
    assert result.stdout == "a" * 5
    assert result.stderr == "b" * 5
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    assert result.stdout_original_chars == 10
    assert result.stderr_original_chars == 9


def test_executor_keeps_output_below_limit(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = Executor(timeout_seconds=2, max_output_chars=5).run("echo test")
    assert result.stdout == "ok"
    assert result.stderr == ""
    assert result.stdout_truncated is False
    assert result.stderr_truncated is False

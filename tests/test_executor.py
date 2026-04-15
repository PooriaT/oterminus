import os

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

from oterminus.executor import Executor


def test_executor_runs_command() -> None:
    executor = Executor(timeout_seconds=2)
    result = executor.run("pwd")

    assert result.returncode == 0
    assert result.stdout.strip()

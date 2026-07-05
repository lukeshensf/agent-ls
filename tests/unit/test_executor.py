
import pytest

from agent_ls.integrations.computer_use.executor import CommandExecutor


@pytest.mark.asyncio
async def test_simple_command():
    executor = CommandExecutor()
    result = await executor.execute("echo hello")
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_failing_command():
    executor = CommandExecutor()
    result = await executor.execute("false")
    assert result.exit_code != 0


@pytest.mark.asyncio
async def test_timeout():
    executor = CommandExecutor(timeout_seconds=1)
    result = await executor.execute("sleep 10")
    assert result.timed_out
    assert result.exit_code == -1


@pytest.mark.asyncio
async def test_stderr_capture():
    executor = CommandExecutor()
    result = await executor.execute("ls /nonexistent-path-xyz")
    assert result.exit_code != 0
    assert result.stderr != ""

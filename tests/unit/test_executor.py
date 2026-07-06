
import asyncio
from unittest.mock import patch

import pytest

from agent_ls.integrations.computer_use import executor as executor_mod
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
async def test_timeout_reaps_process(recwarn):
    """The timeout path must kill AND await the child, leaving no live/zombie proc.

    A short timeout on a long sleep drives the timeout branch. We assert the
    spawned process is actually finished (returncode set) after execute() returns,
    and that no unraised exception / warning (e.g. an unclosed-transport
    ResourceWarning from a never-awaited child) escaped.
    """
    executor = CommandExecutor(timeout_seconds=1)

    real_create = asyncio.create_subprocess_shell
    spawned = []

    async def _tracking_create(*args, **kwargs):
        proc = await real_create(*args, **kwargs)
        spawned.append(proc)
        return proc

    with patch.object(
        executor_mod.asyncio, "create_subprocess_shell", _tracking_create
    ):
        result = await executor.execute("sleep 10")

    assert result.timed_out
    assert result.exit_code == -1
    assert len(spawned) == 1
    # After execute() returns, the killed child has been awaited: returncode is set
    # (not None), so it is neither running nor an unreaped zombie.
    assert spawned[0].returncode is not None


@pytest.mark.asyncio
async def test_spawn_failure_does_not_nameerror():
    """If the subprocess never spawns, the timeout handler must not touch `proc`.

    Previously `proc` was assigned inside the try, so a spawn failure that
    coincided with the handler could raise NameError. The spawn error itself
    should propagate cleanly (as OSError), not be masked by a NameError.
    """
    executor = CommandExecutor(timeout_seconds=1)

    async def _boom(*args, **kwargs):
        raise OSError("cannot spawn")

    with patch.object(executor_mod.asyncio, "create_subprocess_shell", _boom):
        with pytest.raises(OSError, match="cannot spawn"):
            await executor.execute("echo hi")


@pytest.mark.asyncio
async def test_stderr_capture():
    executor = CommandExecutor()
    result = await executor.execute("ls /nonexistent-path-xyz")
    assert result.exit_code != 0
    assert result.stderr != ""

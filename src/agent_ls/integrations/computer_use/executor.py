from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


@dataclass
class StreamEvent:
    stream: str  # "stdout" or "stderr"
    data: str


class CommandExecutor:
    def __init__(self, timeout_seconds: int = 300):
        self._timeout = timeout_seconds

    async def execute(self, command: str, cwd: Optional[str] = None) -> CommandResult:
        """Execute a command and return the full result."""
        import time

        start = time.perf_counter()
        # Spawn OUTSIDE the try/except so a spawn failure (OSError) propagates
        # cleanly and can never leave `proc` unbound in the timeout handler below.
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            return CommandResult(
                command=command,
                exit_code=proc.returncode or 0,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            # Kill the child AND await it: kill() only sends the signal, so without
            # the wait the process is left unreaped (zombie) and its transport
            # unclosed (a ResourceWarning at GC). wait() reaps it and closes the pipes.
            proc.kill()
            await proc.wait()
            duration_ms = int((time.perf_counter() - start) * 1000)
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {self._timeout}s",
                duration_ms=duration_ms,
                timed_out=True,
            )

    async def execute_streaming(
        self, command: str, cwd: Optional[str] = None
    ) -> AsyncIterator[StreamEvent]:
        """Execute a command and yield output as it arrives.

        Uses an asyncio.Queue to merge stdout and stderr concurrently,
        yielding events in the order they are produced by either stream.
        """
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        queue: asyncio.Queue[Optional[StreamEvent]] = asyncio.Queue()

        async def reader(stream: Optional[asyncio.StreamReader], name: str) -> None:
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    break
                await queue.put(
                    StreamEvent(stream=name, data=line.decode(errors="replace"))
                )

        stdout_task = asyncio.create_task(reader(proc.stdout, "stdout"))
        stderr_task = asyncio.create_task(reader(proc.stderr, "stderr"))

        async def sentinel() -> None:
            """Wait for both readers to finish, then push a None sentinel."""
            await asyncio.gather(stdout_task, stderr_task)
            await queue.put(None)

        sentinel_task = asyncio.create_task(sentinel())

        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

        await proc.wait()
        await sentinel_task

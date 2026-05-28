from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
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
            proc.kill()
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
        """Execute a command and yield output as it arrives."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        async def read_stream(stream: asyncio.StreamReader, name: str):
            while True:
                line = await stream.readline()
                if not line:
                    break
                yield StreamEvent(stream=name, data=line.decode(errors="replace"))

        if proc.stdout:
            async for event in read_stream(proc.stdout, "stdout"):
                yield event
        if proc.stderr:
            async for event in read_stream(proc.stderr, "stderr"):
                yield event

        await proc.wait()

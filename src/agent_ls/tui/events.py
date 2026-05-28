from __future__ import annotations

import asyncio
from typing import Optional

from textual.message import Message

from agent_ls.graph.state import ExecutionResult, PlanStep


class GraphNodeStarted(Message):
    def __init__(self, node_name: str) -> None:
        super().__init__()
        self.node_name = node_name


class GraphNodeCompleted(Message):
    def __init__(self, node_name: str, duration_ms: int = 0) -> None:
        super().__init__()
        self.node_name = node_name
        self.duration_ms = duration_ms


class PlanGenerated(Message):
    def __init__(self, plan: list[PlanStep]) -> None:
        super().__init__()
        self.plan = plan


class StepStatusChanged(Message):
    def __init__(self, step_index: int, new_status: str, duration_ms: int = 0) -> None:
        super().__init__()
        self.step_index = step_index
        self.new_status = new_status
        self.duration_ms = duration_ms


class StreamOutput(Message):
    def __init__(self, stream: str, data: str) -> None:
        super().__init__()
        self.stream = stream
        self.data = data


class ApprovalRequired(Message):
    def __init__(
        self,
        command: str,
        risk: str = "unknown",
        reason: str = "",
        response_event: Optional[asyncio.Event] = None,
    ) -> None:
        super().__init__()
        self.command = command
        self.risk = risk
        self.reason = reason
        self.response_event = response_event


class ApprovalResponse(Message):
    def __init__(self, result: str) -> None:
        super().__init__()
        self.result = result


class ExecutionCompleted(Message):
    def __init__(self, result: ExecutionResult) -> None:
        super().__init__()
        self.result = result


class ErrorOccurred(Message):
    def __init__(self, error: str, recoverable: bool = False) -> None:
        super().__init__()
        self.error = error
        self.recoverable = recoverable


class SessionStateChanged(Message):
    def __init__(self, state: str) -> None:
        super().__init__()
        self.state = state

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


@dataclass
class PlanStep:
    description: str
    command: Optional[str] = None
    status: str = "pending"  # pending, running, done, failed, skipped
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None


@dataclass
class ExecutionResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class UserContext:
    team: Optional[str] = None
    role: Optional[str] = None
    tech_stack: list[str] = field(default_factory=list)


@dataclass
class SlackMessage:
    channel: str
    user: str
    text: str
    timestamp: str
    permalink: Optional[str] = None


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_context: UserContext
    intent: str
    plan: list[PlanStep]
    current_step: int
    execution_log: list[ExecutionResult]
    approval_pending: Optional[str]
    obsidian_docs: list[str]
    slack_results: list[SlackMessage]
    error: Optional[str]

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from textual.app import App

from agent_ls.config.settings import get_settings
from agent_ls.graph.builder import build_graph
from agent_ls.graph.checkpointer import open_checkpointer
from agent_ls.graph.state import ExecutionResult, PlanStep, UserContext
from agent_ls.tui.events import (
    ApprovalRequired,
    ErrorOccurred,
    ExecutionCompleted,
    PlanGenerated,
    SessionStateChanged,
    StepStatusChanged,
    StreamOutput,
)
from langchain_core.messages import HumanMessage


@asynccontextmanager
async def _null_async_cm():
    yield None


class GraphRunner:
    """Bridge between the LangGraph backend and the Textual TUI.

    Posts Textual messages at key points during graph execution so the
    UI can reflect progress in real time.
    """

    def __init__(self, app: App) -> None:
        self._app = app
        self._approval_event: Optional[asyncio.Event] = None
        self._approval_result: str = "deny"

    @property
    def approval_result(self) -> str:
        """The last approval result set by the UI layer."""
        return self._approval_result

    @approval_result.setter
    def approval_result(self, value: str) -> None:
        self._approval_result = value

    async def run(self, message: str) -> None:
        """Build and invoke the LangGraph agent, posting TUI events."""
        self._app.post_message(SessionStateChanged(state="running"))

        settings = get_settings()
        cm = open_checkpointer() if settings.checkpoint.enabled else _null_async_cm()

        initial_state = {
            "messages": [HumanMessage(content=message)],
            "user_context": UserContext(),
            "intent": "",
            "plan": [],
            "current_step": 0,
            "execution_log": [],
            "approval_pending": None,
            "obsidian_docs": [],
            "slack_results": [],
            "error": None,
            "processed_message_ids": [],
            "run_success": False,
        }

        try:
            async with cm as checkpointer:
                graph = build_graph(checkpointer=checkpointer)

                config = {}
                if checkpointer:
                    thread_id = f"agent-ls:{message[:50]}"
                    config = {"configurable": {"thread_id": thread_id}}

                result = await graph.ainvoke(initial_state, config=config)

            # Post plan if one was generated
            plan: list[PlanStep] = result.get("plan", [])
            if plan:
                self._app.post_message(PlanGenerated(plan=plan))

                # Post step statuses based on final state
                for idx, step in enumerate(plan):
                    self._app.post_message(
                        StepStatusChanged(
                            step_index=idx,
                            new_status=step.status,
                            duration_ms=step.duration_ms or 0,
                        )
                    )

            # Post execution results from the log
            execution_log: list[ExecutionResult] = result.get("execution_log", [])
            for exec_result in execution_log:
                if exec_result.stdout:
                    self._app.post_message(
                        StreamOutput(stream="stdout", data=exec_result.stdout)
                    )
                if exec_result.stderr:
                    self._app.post_message(
                        StreamOutput(stream="stderr", data=exec_result.stderr)
                    )
                self._app.post_message(ExecutionCompleted(result=exec_result))

            # Check if approval is pending (graph stopped at END due to approval)
            approval_pending = result.get("approval_pending")
            if approval_pending:
                await self.wait_for_approval(
                    command=approval_pending,
                    risk="unknown",
                    reason="Command requires approval before execution",
                )

            # Check for errors
            error = result.get("error")
            if error:
                self._app.post_message(ErrorOccurred(error=error, recoverable=False))

            self._app.post_message(SessionStateChanged(state="completed"))

        except Exception as exc:
            self._app.post_message(
                ErrorOccurred(error=str(exc), recoverable=False)
            )
            self._app.post_message(SessionStateChanged(state="error"))

    async def wait_for_approval(
        self, command: str, risk: str, reason: str
    ) -> str:
        """Pause execution until the user approves or denies a command.

        Creates an asyncio.Event, posts an ApprovalRequired message carrying
        it, then blocks until the UI sets the event (after the user responds).
        """
        self._approval_event = asyncio.Event()
        self._approval_result = "deny"

        self._app.post_message(SessionStateChanged(state="awaiting_approval"))
        self._app.post_message(
            ApprovalRequired(
                command=command,
                risk=risk,
                reason=reason,
                response_event=self._approval_event,
            )
        )

        await self._approval_event.wait()
        self._approval_event = None

        return self._approval_result

    def respond_to_approval(self, result: str) -> None:
        """Called by the UI to unblock wait_for_approval with a decision."""
        self._approval_result = result
        if self._approval_event is not None:
            self._approval_event.set()

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from agent_ls.tui.screens.approval import ApprovalModal


class AgentLSApp(App):
    """Main TUI application for agent-ls."""

    TITLE = "agent-ls"
    CSS_PATH = Path(__file__).parent / "styles" / "agent_ls.tcss"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("tab", "focus_next", "Focus Next"),
    ]

    def __init__(
        self,
        initial_message: Optional[str] = None,
        show_config: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._initial_message = initial_message
        self._show_config = show_config
        self._graph = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static(
                "Model: configurable   Status: idle   [Ctrl+? for help]",
                id="header",
            )
            yield RichLog(id="chat-panel", wrap=True, highlight=True, markup=True)
            yield RichLog(id="command-log", wrap=True, highlight=True, markup=True)
        yield Input(placeholder="Type a message...", id="input-bar")
        yield Footer()

    def on_mount(self) -> None:
        chat = self.query_one("#chat-panel", RichLog)
        chat.write("[bold green]agent-ls[/] ready. Type a setup instruction or ask a question.")
        chat.write("")

        if self._initial_message:
            self._process_message(self._initial_message)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip():
            return
        message = event.value.strip()
        event.input.value = ""
        self._process_message(message)

    def _process_message(self, message: str) -> None:
        chat = self.query_one("#chat-panel", RichLog)
        chat.write(f"[bold blue]You:[/] {message}")
        chat.write("")

        self.run_worker(self._run_graph(message), exclusive=True)

    async def _run_graph(self, message: str) -> None:
        from langchain_core.messages import HumanMessage

        from agent_ls.graph.builder import build_graph
        from agent_ls.graph.state import UserContext

        chat = self.query_one("#chat-panel", RichLog)
        cmd_log = self.query_one("#command-log", RichLog)

        chat.write("[dim]Thinking...[/]")

        try:
            graph = build_graph()
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
            }

            result = await graph.ainvoke(initial_state)

            if result.get("approval_pending"):
                command = result["approval_pending"]
                approved = await self._request_approval(command)
                if approved:
                    result = await graph.ainvoke(
                        {**result, "approval_pending": None},
                        {"configurable": {"resume_node": "execute_after_approval"}},
                    )

            if result.get("plan"):
                chat.write("[bold]Plan:[/]")
                for i, step in enumerate(result["plan"]):
                    icon = {"done": "[green]✓[/]", "failed": "[red]✗[/]", "skipped": "[dim]-[/]"}.get(
                        step.status, "[ ]"
                    )
                    time_str = f" [dim]({step.duration_ms}ms)[/]" if step.duration_ms else ""
                    chat.write(f"  {icon} {step.description}{time_str}")

            if result.get("execution_log"):
                for entry in result["execution_log"]:
                    status = "[green]OK[/]" if entry.exit_code == 0 else f"[red]exit={entry.exit_code}[/]"
                    cmd_log.write(f"[dim]{status}[/] $ {entry.command}  ({entry.duration_ms}ms)")

            if result.get("messages"):
                last_msg = result["messages"][-1]
                if hasattr(last_msg, "content"):
                    chat.write("")
                    chat.write(f"[bold green]Agent:[/] {last_msg.content}")

        except Exception as e:
            chat.write(f"[bold red]Error:[/] {e}")

    async def _request_approval(self, command: str) -> bool:
        modal = ApprovalModal(command)
        result = await self.push_screen_wait(modal)
        return result == "approve"

    def action_clear_chat(self) -> None:
        chat = self.query_one("#chat-panel", RichLog)
        chat.clear()

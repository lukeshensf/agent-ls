from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input

from agent_ls.config.settings import get_settings
from agent_ls.tui.events import (
    ApprovalRequired,
    ApprovalResponse,
    ErrorOccurred,
    ExecutionCompleted,
    GraphNodeCompleted,
    GraphNodeStarted,
    PlanGenerated,
    SessionStateChanged,
    StepStatusChanged,
    StreamOutput,
)
from agent_ls.tui.screens.approval import ApprovalModal
from agent_ls.tui.screens.audit_viewer import AuditViewer
from agent_ls.tui.screens.config import ConfigScreen
from agent_ls.tui.slash_commands import parse_slash_command, get_command_help
from agent_ls.tui.widgets.dag_view import DAGView
from agent_ls.tui.widgets.plan_checklist import PlanChecklist
from agent_ls.tui.widgets.progress_indicator import ProgressIndicator
from agent_ls.tui.widgets.status_bar import StatusBar
from agent_ls.tui.widgets.streaming_log import StreamingLog


class AgentLSApp(App):
    """Main TUI application for agent-ls."""

    TITLE = "agent-ls"
    CSS_PATH = Path(__file__).parent / "styles" / "agent_ls.tcss"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+a", "approve_all", "Approve All"),
        Binding("ctrl+d", "quit", "Quit"),
        Binding("ctrl+p", "toggle_config", "Config"),
        Binding("ctrl+s", "show_audit", "Audit Log"),
        Binding("tab", "focus_next", "Focus Next"),
    ]

    def __init__(
        self,
        initial_message: Optional[str] = None,
        show_config: bool = False,
        resume_session_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._initial_message = initial_message
        self._show_config = show_config
        self._resume_session_id = resume_session_id
        self._graph_runner = None
        self._session_id = resume_session_id or str(uuid.uuid4())[:8]
        self._original_message: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar(id="status-bar")
        with Horizontal(id="main-area"):
            with Vertical(id="left-panel"):
                yield DAGView(id="dag-view")
                yield PlanChecklist(id="plan-panel")
            with Vertical(id="right-panel"):
                yield StreamingLog(id="chat-panel")
                yield ProgressIndicator(id="progress")
                yield StreamingLog(id="command-log")
        yield Input(placeholder="Type a message or /command...", id="input-bar")
        yield Footer()

    def on_mount(self) -> None:
        chat = self.query_one("#chat-panel", StreamingLog)
        chat.write("[bold green]agent-ls[/] ready. Type a setup instruction or ask a question.")
        chat.write("[dim]Use /help for available commands.[/]")
        chat.write("")

        if self._show_config:
            self.push_screen(ConfigScreen())

        if self._resume_session_id:
            self._resume_from_session()
        elif self._initial_message:
            self._process_message(self._initial_message)

    def _resume_from_session(self) -> None:
        from agent_ls.tui.session import SessionManager

        mgr = SessionManager()
        session_data = mgr.load_session(self._resume_session_id)
        if not session_data:
            chat = self.query_one("#chat-panel", StreamingLog)
            chat.write(f"[red]Session '{self._resume_session_id}' not found.[/]")
            return

        chat = self.query_one("#chat-panel", StreamingLog)
        chat.write(f"[dim]Resuming session: {self._resume_session_id}[/]")
        original = session_data.get("original_message", "")
        if original:
            self._process_message(original)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip():
            return
        message = event.value.strip()
        event.input.value = ""

        try:
            slash_cmd = parse_slash_command(message)
        except ValueError as e:
            chat = self.query_one("#chat-panel", StreamingLog)
            chat.write(f"[red]{e}[/]")
            return

        if slash_cmd:
            self._handle_slash_command(slash_cmd)
        else:
            self._process_message(message)

    def _handle_slash_command(self, cmd) -> None:
        match cmd.name:
            case "config":
                self.push_screen(ConfigScreen())
            case "audit":
                self.push_screen(AuditViewer())
            case "theme":
                if cmd.args:
                    self._switch_theme(cmd.args[0])
                else:
                    chat = self.query_one("#chat-panel", StreamingLog)
                    chat.write("[dim]Usage: /theme dark|light[/]")
            case "history":
                self._show_history()
            case "help":
                chat = self.query_one("#chat-panel", StreamingLog)
                chat.write(get_command_help())
            case "share" | "update-kb":
                self._process_message(f"/{cmd.name} {' '.join(cmd.args)}")
            case _:
                chat = self.query_one("#chat-panel", StreamingLog)
                chat.write(f"[dim]Command /{cmd.name} not yet implemented.[/]")

    def _switch_theme(self, theme_name: str) -> None:
        from agent_ls.config.settings import get_settings, save_settings

        chat = self.query_one("#chat-panel", StreamingLog)
        if theme_name not in ("dark", "light"):
            chat.write("[red]Unknown theme. Use 'dark' or 'light'.[/]")
            return

        settings = get_settings()
        settings.ui.theme = theme_name
        save_settings(settings)
        chat.write(f"[dim]Theme switched to: {theme_name}[/]")
        self.notify(f"Theme set to {theme_name}. Restart for full effect.")

    def _show_history(self) -> None:
        from agent_ls.tui.session import SessionManager

        chat = self.query_one("#chat-panel", StreamingLog)
        mgr = SessionManager()
        sessions = mgr.list_sessions()
        if not sessions:
            chat.write("[dim]No past sessions found.[/]")
            return

        chat.write("[bold]Recent Sessions:[/]")
        for s in sessions[:10]:
            status_icon = {"completed": "✓", "failed": "✗", "interrupted": "~"}.get(
                s.status, "?"
            )
            chat.write(
                f"  [{status_icon}] {s.session_id}  {s.original_message[:40]}  "
                f"[dim]{s.updated_at[:16]}[/]"
            )

    def _process_message(self, message: str) -> None:
        chat = self.query_one("#chat-panel", StreamingLog)
        chat.write(f"[bold blue]You:[/] {message}")
        chat.write("")

        self._original_message = message
        self.run_worker(self._run_graph(message), exclusive=True)

    async def _run_graph(self, message: str) -> None:
        from agent_ls.tui.graph_runner import GraphRunner

        runner = GraphRunner(self)
        self._graph_runner = runner
        await runner.run(message)

    def on_session_state_changed(self, event: SessionStateChanged) -> None:
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.execution_state = event.state

        progress = self.query_one("#progress", ProgressIndicator)
        progress.running = event.state in ("running", "planning", "executing", "thinking")

    def on_plan_generated(self, event: PlanGenerated) -> None:
        checklist = self.query_one("#plan-panel", PlanChecklist)
        checklist.plan = list(event.plan)

        status_bar = self.query_one("#status-bar", StatusBar)
        total = len(event.plan)
        done = sum(1 for s in event.plan if s.status == "done")
        status_bar.step_progress = f"{done}/{total}"

    def on_step_status_changed(self, event: StepStatusChanged) -> None:
        checklist = self.query_one("#plan-panel", PlanChecklist)
        checklist.update_step(event.step_index, event.new_status, event.duration_ms)

        status_bar = self.query_one("#status-bar", StatusBar)
        if checklist.plan:
            total = len(checklist.plan)
            done = sum(1 for s in checklist.plan if s.status == "done")
            status_bar.step_progress = f"{done}/{total}"

    def on_execution_completed(self, event: ExecutionCompleted) -> None:
        cmd_log = self.query_one("#command-log", StreamingLog)
        cmd_log.log_execution(
            event.result.command, event.result.exit_code, event.result.duration_ms
        )
        self._save_session_checkpoint()

    def on_stream_output(self, event: StreamOutput) -> None:
        cmd_log = self.query_one("#command-log", StreamingLog)
        cmd_log.append_stream(event.stream, event.data)

    def on_approval_required(self, event: ApprovalRequired) -> None:
        self.push_screen(
            ApprovalModal(command=event.command, risk=event.risk, reason=event.reason),
            callback=lambda result: self._handle_approval_response(result, event),
        )

    def _handle_approval_response(self, result: str, event: ApprovalRequired) -> None:
        self.post_message(ApprovalResponse(result=result))
        if self._graph_runner:
            self._graph_runner.respond_to_approval(result)
        if event.response_event:
            event.response_event.set()

    def on_error_occurred(self, event: ErrorOccurred) -> None:
        chat = self.query_one("#chat-panel", StreamingLog)
        chat.write(f"[bold red]Error:[/] {event.error}")
        if event.recoverable:
            chat.write("[dim]This error may be recoverable. Try again.[/]")
        self.notify(f"Error: {event.error}", severity="error")

    def on_graph_node_started(self, event: GraphNodeStarted) -> None:
        dag = self.query_one("#dag-view", DAGView)
        dag.active_node = event.node_name

    def on_graph_node_completed(self, event: GraphNodeCompleted) -> None:
        dag = self.query_one("#dag-view", DAGView)
        dag.active_node = ""

    def _save_session_checkpoint(self) -> None:
        settings = get_settings()
        if not settings.ui.session_persistence:
            return

        from agent_ls.tui.session import SessionManager

        checklist = self.query_one("#plan-panel", PlanChecklist)
        mgr = SessionManager()
        state = {
            "plan": list(checklist.plan) if checklist.plan else [],
            "current_step": sum(1 for s in checklist.plan if s.status == "done") if checklist.plan else 0,
            "execution_log": [],
            "messages": [],
        }
        mgr.save_checkpoint(self._session_id, state, self._original_message or "")

    def action_clear_chat(self) -> None:
        chat = self.query_one("#chat-panel", StreamingLog)
        chat.clear()

    def action_approve_all(self) -> None:
        if self._graph_runner:
            self._graph_runner.respond_to_approval("always")

    def action_toggle_config(self) -> None:
        self.push_screen(ConfigScreen())

    def action_show_audit(self) -> None:
        self.push_screen(AuditViewer())

from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from agent_ls.config.settings import get_settings


class AuditViewer(ModalScreen[None]):
    """Modal screen that displays the audit log in a DataTable."""

    DEFAULT_CSS = """
    AuditViewer {
        align: center middle;
    }

    AuditViewer > Vertical {
        width: 100;
        height: 35;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    AuditViewer .title {
        text-align: center;
        text-style: bold;
        padding: 1 0;
    }

    AuditViewer DataTable {
        height: 1fr;
        margin: 1 0;
    }

    AuditViewer .button-row {
        height: 3;
        align: center middle;
    }
    """

    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Audit Log", classes="title")
            yield DataTable(id="audit-table")
            yield Button("Close", variant="primary", id="btn-close", classes="button-row")

    def on_mount(self) -> None:
        table = self.query_one("#audit-table", DataTable)
        table.add_columns("Timestamp", "Command", "Classification", "Exit Code", "Duration")
        self._load_entries(table)

    def _load_entries(self, table: DataTable) -> None:
        settings = get_settings()
        audit_path = Path(settings.audit_log_path)

        if not audit_path.exists():
            table.add_row("--", "No audit log found", "--", "--", "--")
            return

        try:
            lines = audit_path.read_text().strip().splitlines()
        except OSError:
            table.add_row("--", "Error reading audit log", "--", "--", "--")
            return

        if not lines:
            table.add_row("--", "Audit log is empty", "--", "--", "--")
            return

        for line in lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            timestamp = entry.get("timestamp", "?")
            command = entry.get("command", "?")
            classification = entry.get("classification", "?")
            exit_code = str(entry.get("exit_code", "?"))
            duration = entry.get("duration_ms", entry.get("duration", "?"))
            duration_str = f"{duration}ms" if duration != "?" else "?"

            style = self._row_style(classification)

            table.add_row(
                timestamp,
                command if len(command) <= 60 else command[:57] + "...",
                classification,
                exit_code,
                duration_str,
                key=None,
            )
            row_key = table.row_count - 1
            if style:
                table.rows[list(table.rows.keys())[row_key]].style = style

    def _row_style(self, classification: str) -> str:
        styles = {
            "auto_approve": "green",
            "needs_approval": "yellow",
            "blocked": "red",
        }
        return styles.get(classification, "")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

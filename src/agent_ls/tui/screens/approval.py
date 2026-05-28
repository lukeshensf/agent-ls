from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ApprovalModal(ModalScreen[str]):
    """Modal dialog for command approval."""

    def __init__(self, command: str, risk: str = "unknown", reason: str = "", **kwargs):
        super().__init__(**kwargs)
        self._command = command
        self._risk = risk
        self._reason = reason

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-dialog"):
            yield Label("Command Approval Required", classes="title")
            yield Static("")
            yield Label("The agent wants to run:")
            yield Static(f"  $ {self._command}", id="approval-command")
            yield Static("")
            yield Label(f"Risk: {self._risk.upper()}")
            if self._reason:
                yield Label(f"Reason: {self._reason}")
            yield Static("")
            with Horizontal(id="approval-buttons"):
                yield Button("Approve [y]", variant="success", id="btn-approve")
                yield Button("Reject [n]", variant="error", id="btn-reject")
                yield Button("Always [a]", variant="default", id="btn-always")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-approve":
            self.dismiss("approve")
        elif event.button.id == "btn-reject":
            self.dismiss("reject")
        elif event.button.id == "btn-always":
            self.dismiss("always")

    def key_y(self) -> None:
        self.dismiss("approve")

    def key_n(self) -> None:
        self.dismiss("reject")

    def key_a(self) -> None:
        self.dismiss("always")

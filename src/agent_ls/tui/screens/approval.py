from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ApprovalModal(ModalScreen[str]):
    """Modal dialog for command approval with risk-level coloring."""

    def __init__(
        self,
        command: str,
        risk: str = "unknown",
        reason: str = "",
        risk_score: int = 50,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._command = command
        self._risk = risk
        self._reason = reason
        self._risk_score = risk_score

    def compose(self) -> ComposeResult:
        risk_color = self._get_risk_color()
        with Vertical(id="approval-dialog"):
            yield Label("Command Approval Required", classes="title")
            yield Static("")
            yield Label("The agent wants to run:")
            yield Static(f"  $ {self._command}", id="approval-command")
            yield Static("")
            yield Label(f"[{risk_color}]Risk: {self._risk.upper()} ({self._risk_score}/100)[/]")
            if self._reason:
                yield Label(f"Reason: {self._reason}")
            yield Static("")
            with Horizontal(id="approval-buttons"):
                yield Button("Approve [y]", variant="success", id="btn-approve")
                yield Button("Reject [n]", variant="error", id="btn-reject")
                yield Button("Always [a]", variant="default", id="btn-always")

    def _get_risk_color(self) -> str:
        if self._risk_score < 30:
            return "green"
        elif self._risk_score < 60:
            return "yellow"
        return "red"

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

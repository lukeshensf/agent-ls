from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from agent_ls.config.settings import get_settings


class StatusBar(Static):
    """Single-line status bar showing model, execution state, and progress."""

    model_name: reactive[str] = reactive("")
    execution_state: reactive[str] = reactive("idle")
    step_progress: reactive[str] = reactive("")

    def on_mount(self) -> None:
        settings = get_settings()
        self.model_name = settings.models.expensive.split("/")[-1]

    def render(self) -> str:
        parts = [f"Model: {self.model_name}"]
        parts.append(f"Status: {self.execution_state}")
        if self.step_progress:
            parts.append(f"Progress: {self.step_progress}")
        parts.append("[Ctrl+? for help]")
        return "   ".join(parts)

    def watch_execution_state(self) -> None:
        self.refresh()

    def watch_step_progress(self) -> None:
        self.refresh()

    def watch_model_name(self) -> None:
        self.refresh()

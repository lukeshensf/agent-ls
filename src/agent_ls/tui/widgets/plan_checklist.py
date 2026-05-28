from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from agent_ls.graph.state import PlanStep


_STATUS_ICONS = {
    "done": ("[x]", "green"),
    "pending": ("[ ]", "white"),
    "running": ("[~]", "yellow"),
    "failed": ("[!]", "red"),
    "skipped": ("[-]", "dim"),
}


class PlanChecklist(Static):
    """Displays plan steps as a checklist with colored status indicators."""

    plan: reactive[list[PlanStep]] = reactive(list, always_update=True)

    def render(self) -> Text:
        text = Text()
        if not self.plan:
            text.append("No plan generated yet.", style="dim")
            return text

        for idx, step in enumerate(self.plan):
            icon, style = _STATUS_ICONS.get(step.status, ("[ ]", "white"))

            text.append(f"  {icon} ", style=style)
            text.append(f"{idx + 1}. {step.description}", style=style)

            if step.duration_ms is not None and step.status == "done":
                text.append(f"  ({step.duration_ms}ms)", style="dim")
            elif step.command and step.status == "pending":
                text.append(f"  $ {step.command}", style="dim")

            text.append("\n")

        return text

    def update_step(self, index: int, status: str, duration_ms: int = 0) -> None:
        """Update the status and duration of a specific step."""
        if 0 <= index < len(self.plan):
            self.plan[index].status = status
            if duration_ms:
                self.plan[index].duration_ms = duration_ms
            self.mutate_reactive(PlanChecklist.plan)

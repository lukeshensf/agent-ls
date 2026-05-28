from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class DAGView(Static):
    """Renders the LangGraph node DAG using box-drawing/Unicode characters.

    Shows nodes: Router -> Plan -> Execute -> Summarize, with Security Gate
    branching from Execute. Active node is highlighted in bold green.
    """

    active_node: reactive[str] = reactive("")

    NODES = ["router", "plan", "execute", "summarize"]
    BRANCH_NODE = "security_gate"
    BRANCH_PARENT = "execute"

    def render(self) -> str:
        parts: list[str] = []
        for i, node in enumerate(self.NODES):
            label = self._format_node(node)
            parts.append(label)
            if i < len(self.NODES) - 1:
                parts.append(" ──→ ")

        main_line = "".join(parts)

        # Calculate position of the branch indicator under "Execute"
        # Find the center of the Execute node label in the plain-text version
        plain_parts: list[str] = []
        for i, node in enumerate(self.NODES):
            plain_parts.append(f"[{node.title()}]")
            if i < len(self.NODES) - 1:
                plain_parts.append(" ──→ ")

        plain_line = "".join(plain_parts)
        execute_display = f"[{self.BRANCH_PARENT.title()}]"
        execute_start = plain_line.find(execute_display)
        execute_center = execute_start + len(execute_display) // 2

        # Build the branch lines
        arrow_line = " " * execute_center + "↕"
        branch_label = self._format_node(self.BRANCH_NODE)
        branch_display = f"[{self._display_name(self.BRANCH_NODE)}]"
        branch_offset = max(0, execute_center - len(branch_display) // 2)
        branch_line = " " * branch_offset + branch_label

        return f"{main_line}\n{arrow_line}\n{branch_line}"

    def _format_node(self, node: str) -> str:
        display = self._display_name(node)
        if node == self.active_node:
            return f"[bold green]\\[{display}][/bold green]"
        return f"[dim]\\[{display}][/dim]"

    def _display_name(self, node: str) -> str:
        return node.replace("_", " ").title()

    def watch_active_node(self) -> None:
        self.refresh()

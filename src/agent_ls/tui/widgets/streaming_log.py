from __future__ import annotations

from rich.text import Text
from textual.widgets import RichLog


class StreamingLog(RichLog):
    """A RichLog that handles streaming command output with coloring."""

    def __init__(self, **kwargs) -> None:
        super().__init__(auto_scroll=True, wrap=True, **kwargs)

    def append_stream(self, stream: str, data: str) -> None:
        """Append a line of streaming output, coloring stderr red."""
        text = Text(data.rstrip("\n"))
        if stream == "stderr":
            text.stylize("red")
        self.write(text)

    def log_execution(self, command: str, exit_code: int, duration_ms: int) -> None:
        """Log a command completion entry with status styling."""
        separator = Text("─" * 40, style="dim")
        self.write(separator)

        cmd_text = Text()
        cmd_text.append("$ ", style="bold")
        cmd_text.append(command)
        self.write(cmd_text)

        status_text = Text()
        if exit_code == 0:
            status_text.append("✓ ", style="bold green")
            status_text.append(f"exit {exit_code}", style="green")
        else:
            status_text.append("✗ ", style="bold red")
            status_text.append(f"exit {exit_code}", style="red")

        status_text.append(f"  ({duration_ms}ms)", style="dim")
        self.write(status_text)

        self.write(Text("─" * 40, style="dim"))

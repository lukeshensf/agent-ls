from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from textual.widgets import RichLog


@dataclass
class ChatMessage:
    """A single chat message stored in history."""

    sender: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class ChatPanel(RichLog):
    """A chat panel widget with message history support.

    Extends RichLog to maintain a message history buffer and provide
    formatted message display with sender-appropriate colors.
    """

    SENDER_COLORS = {
        "You": "blue",
        "Agent": "green",
    }
    SYSTEM_STYLE = "dim"

    def __init__(
        self,
        *args,
        max_history: int = 1000,
        **kwargs,
    ) -> None:
        kwargs.setdefault("wrap", True)
        kwargs.setdefault("highlight", True)
        kwargs.setdefault("markup", True)
        super().__init__(*args, **kwargs)
        self._max_history = max_history
        self._history: list[ChatMessage] = []

    @property
    def history(self) -> list[ChatMessage]:
        """Return a copy of the message history."""
        return list(self._history)

    @property
    def max_history(self) -> int:
        """Maximum number of messages to retain in history."""
        return self._max_history

    def add_message(self, sender: str, content: str) -> None:
        """Add a message from a sender to the chat panel.

        Args:
            sender: The name of the message sender (e.g., "You", "Agent").
            content: The message content to display.
        """
        message = ChatMessage(sender=sender, content=content)
        self._append_to_history(message)

        color = self.SENDER_COLORS.get(sender, "white")
        self.write(f"[bold {color}]{sender}:[/] {content}")
        self.write("")

    def add_system_message(self, content: str) -> None:
        """Add a system/status message to the chat panel.

        Args:
            content: The system message content to display.
        """
        message = ChatMessage(sender="system", content=content)
        self._append_to_history(message)

        self.write(f"[{self.SYSTEM_STYLE}]{content}[/]")
        self.write("")

    def _append_to_history(self, message: ChatMessage) -> None:
        """Append a message to history, trimming if over max."""
        self._history.append(message)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

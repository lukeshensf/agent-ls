from __future__ import annotations

from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static


_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class ProgressIndicator(Static):
    """A spinner widget that animates while running is True."""

    running: reactive[bool] = reactive(False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._frame_index: int = 0
        self._timer: Timer | None = None

    def watch_running(self, value: bool) -> None:
        """Start or stop the spinner timer when running changes."""
        if value:
            self._frame_index = 0
            self._timer = self.set_interval(0.08, self._advance_frame)
            self.update(_SPINNER_FRAMES[0])
        else:
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
            self.update("")

    def _advance_frame(self) -> None:
        """Move to the next spinner frame."""
        self._frame_index = (self._frame_index + 1) % len(_SPINNER_FRAMES)
        self.update(_SPINNER_FRAMES[self._frame_index])

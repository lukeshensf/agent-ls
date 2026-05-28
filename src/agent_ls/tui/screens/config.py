from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.widgets import (
    Button,
    Input,
    Label,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from agent_ls.config.settings import get_settings, save_settings, Settings


class ConfigScreen(ModalScreen[bool]):
    """Configuration modal screen with tabbed settings."""

    DEFAULT_CSS = """
    ConfigScreen {
        align: center middle;
    }

    ConfigScreen > Vertical {
        width: 80;
        height: 40;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    ConfigScreen .title {
        text-align: center;
        text-style: bold;
        padding: 1 0;
    }

    ConfigScreen .field-row {
        height: 3;
        margin: 0 0 1 0;
    }

    ConfigScreen .field-label {
        width: 20;
        padding: 1 1 0 0;
    }

    ConfigScreen .field-input {
        width: 1fr;
    }

    ConfigScreen .button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    ConfigScreen .button-row Button {
        margin: 0 2;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        settings = get_settings()

        with Vertical():
            yield Static("Configuration", classes="title")

            with TabbedContent():
                with TabPane("Models", id="tab-models"):
                    with Horizontal(classes="field-row"):
                        yield Label("Cheap Model:", classes="field-label")
                        yield Input(
                            value=settings.models.cheap,
                            id="input-model-cheap",
                            classes="field-input",
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Expensive Model:", classes="field-label")
                        yield Input(
                            value=settings.models.expensive,
                            id="input-model-expensive",
                            classes="field-input",
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Computer Use:", classes="field-label")
                        yield Input(
                            value=settings.models.computer_use,
                            id="input-model-computer-use",
                            classes="field-input",
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Ollama Base URL:", classes="field-label")
                        yield Input(
                            value=settings.ollama.base_url,
                            id="input-ollama-url",
                            classes="field-input",
                        )

                with TabPane("Integrations", id="tab-integrations"):
                    with Horizontal(classes="field-row"):
                        yield Label("Vault Path:", classes="field-label")
                        yield Input(
                            value=settings.obsidian.vault_path or "",
                            id="input-vault-path",
                            classes="field-input",
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Slack Token:", classes="field-label")
                        yield Input(
                            value=settings.slack.user_token or "",
                            id="input-slack-token",
                            password=True,
                            classes="field-input",
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Git Auto Sync:", classes="field-label")
                        yield Switch(
                            value=settings.obsidian.git_auto_sync,
                            id="switch-git-sync",
                        )

                with TabPane("UI", id="tab-ui"):
                    with Horizontal(classes="field-row"):
                        yield Label("Theme:", classes="field-label")
                        yield Select(
                            [(line, line) for line in ["dark", "light"]],
                            value=settings.ui.theme,
                            id="select-theme",
                        )
                    with Horizontal(classes="field-row"):
                        yield Label("Session Persist:", classes="field-label")
                        yield Switch(
                            value=settings.ui.session_persistence,
                            id="switch-session-persist",
                        )

            with Horizontal(classes="button-row"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self._save_settings()
            self.dismiss(True)
        elif event.button.id == "btn-cancel":
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _save_settings(self) -> None:
        settings = Settings(
            models={
                "cheap": self.query_one("#input-model-cheap", Input).value,
                "expensive": self.query_one("#input-model-expensive", Input).value,
                "computer_use": self.query_one("#input-model-computer-use", Input).value,
            },
            ollama={
                "base_url": self.query_one("#input-ollama-url", Input).value,
            },
            slack={
                "user_token": self.query_one("#input-slack-token", Input).value or None,
            },
            obsidian={
                "vault_path": self.query_one("#input-vault-path", Input).value or None,
                "git_auto_sync": self.query_one("#switch-git-sync", Switch).value,
            },
            ui={
                "theme": self.query_one("#select-theme", Select).value,
                "session_persistence": self.query_one("#switch-session-persist", Switch).value,
            },
        )
        save_settings(settings)

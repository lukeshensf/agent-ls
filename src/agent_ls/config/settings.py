from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


CONFIG_DIR = Path.home() / ".agent-ls"
CONFIG_FILE = CONFIG_DIR / "config.toml"


class ModelSettings(BaseModel):
    cheap: str = "anthropic/claude-haiku"
    expensive: str = "anthropic/claude-sonnet"
    computer_use: str = "anthropic/claude-sonnet"
    cheap_fallback: Optional[str] = None
    expensive_fallback: Optional[str] = None


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"


class SlackSettings(BaseModel):
    user_token: Optional[str] = None


class ObsidianSettings(BaseModel):
    vault_path: Optional[str] = None
    git_auto_sync: bool = True


class UISettings(BaseModel):
    theme: str = "dark"
    show_plan_panel: bool = True
    session_persistence: bool = True


class Settings(BaseModel):
    models: ModelSettings = Field(default_factory=ModelSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    obsidian: ObsidianSettings = Field(default_factory=ObsidianSettings)
    ui: UISettings = Field(default_factory=UISettings)
    audit_log_path: str = str(CONFIG_DIR / "audit.jsonl")
    allowlist_path: str = str(Path(__file__).parent / "allowlist.yaml")

    @classmethod
    def from_toml(cls, path: Path = CONFIG_FILE) -> Settings:
        if not path.exists():
            return cls()
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**data)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_toml()


def _serialize_toml(settings: Settings) -> str:
    """Serialize a Settings object to TOML format.

    Handles the flat nested structure of Settings which contains
    only strings, bools, and Optional[str] values.
    """
    lines: list[str] = []

    def _write_section(section_name: str, data: dict) -> None:
        lines.append(f"[{section_name}]")
        for key, value in data.items():
            if value is None:
                continue
            elif isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, str):
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{escaped}"')
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}")
        lines.append("")

    _write_section("models", settings.models.model_dump())
    _write_section("ollama", settings.ollama.model_dump())
    _write_section("slack", settings.slack.model_dump())
    _write_section("obsidian", settings.obsidian.model_dump())
    _write_section("ui", settings.ui.model_dump())

    return "\n".join(lines)


def save_settings(settings: Settings) -> None:
    """Save settings to the TOML config file.

    Creates the config directory if it does not exist, serializes the
    settings to TOML, writes to CONFIG_FILE, and clears the lru_cache.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    toml_content = _serialize_toml(settings)
    CONFIG_FILE.write_text(toml_content)
    get_settings.cache_clear()

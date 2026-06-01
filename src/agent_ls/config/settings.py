from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


CONFIG_DIR = Path.home() / ".agent-ls"
CONFIG_FILE = CONFIG_DIR / "config.toml"


class BedrockSettings(BaseModel):
    endpoint_url: Optional[str] = None
    auth_token: Optional[str] = None
    region: str = "us-west-2"


class ModelSettings(BaseModel):
    cheap: str = "bedrock/anthropic.claude-haiku-4-5-20251001"
    expensive: str = "bedrock/anthropic.claude-sonnet-4-20250514"
    computer_use: str = "bedrock/anthropic.claude-sonnet-4-20250514"
    cheap_fallback: Optional[str] = None
    expensive_fallback: Optional[str] = None


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"


class SlackSettings(BaseModel):
    user_token: Optional[str] = None
    follow_threads: bool = True
    semantic_threshold: float = 0.3


class ObsidianSettings(BaseModel):
    vault_path: Optional[str] = None
    git_auto_sync: bool = True
    git_push_on_success: bool = True
    freshness_fallback: bool = True


class CheckpointSettings(BaseModel):
    enabled: bool = True
    db_path: str = str(CONFIG_DIR / "checkpoints.db")
    max_age_days: int = 30


class UISettings(BaseModel):
    theme: str = "dark"
    show_plan_panel: bool = True
    session_persistence: bool = True


class Settings(BaseModel):
    models: ModelSettings = Field(default_factory=ModelSettings)
    bedrock: BedrockSettings = Field(default_factory=BedrockSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    obsidian: ObsidianSettings = Field(default_factory=ObsidianSettings)
    checkpoint: CheckpointSettings = Field(default_factory=CheckpointSettings)
    ui: UISettings = Field(default_factory=UISettings)
    audit_log_path: str = str(CONFIG_DIR / "audit.jsonl")
    allowlist_path: str = str(Path(__file__).parent / "allowlist.yaml")

    @classmethod
    def from_toml(cls, path: Path = CONFIG_FILE) -> Settings:
        if not path.exists():
            data = {}
        else:
            with open(path, "rb") as f:
                data = tomllib.load(f)

        settings = cls(**data)
        settings._apply_env_overrides()
        return settings

    def _apply_env_overrides(self) -> None:
        """Override settings with environment variables when present."""
        if val := os.environ.get("BEDROCK_ENDPOINT_URL"):
            self.bedrock.endpoint_url = val
        if val := os.environ.get("BEDROCK_AUTH_TOKEN"):
            self.bedrock.auth_token = val
        if val := os.environ.get("AWS_REGION"):
            self.bedrock.region = val
        if val := os.environ.get("BEDROCK_MODEL_CHEAP"):
            self.models.cheap = f"bedrock/{val}"
        if val := os.environ.get("BEDROCK_MODEL_EXPENSIVE"):
            self.models.expensive = f"bedrock/{val}"
        if val := os.environ.get("SLACK_USER_TOKEN"):
            self.slack.user_token = val
        if val := os.environ.get("OBSIDIAN_VAULT_PATH"):
            self.obsidian.vault_path = val
        if val := os.environ.get("OBSIDIAN_GIT_AUTO_SYNC"):
            self.obsidian.git_auto_sync = val.lower() in ("true", "1", "yes")
        if val := os.environ.get("OLLAMA_BASE_URL"):
            self.ollama.base_url = val


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
    _write_section("bedrock", settings.bedrock.model_dump())
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

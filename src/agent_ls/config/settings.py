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


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"


class SlackSettings(BaseModel):
    user_token: Optional[str] = None


class ObsidianSettings(BaseModel):
    vault_path: Optional[str] = None
    git_auto_sync: bool = True


class Settings(BaseModel):
    models: ModelSettings = Field(default_factory=ModelSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    obsidian: ObsidianSettings = Field(default_factory=ObsidianSettings)
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

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agent_ls.config.settings import get_settings


class ObsidianVault:
    def __init__(self, vault_path: Optional[str] = None):
        path = vault_path or get_settings().obsidian.vault_path
        if not path:
            raise ValueError(
                "Obsidian vault path not configured. "
                "Set it in ~/.agent-ls/config.toml under [obsidian] vault_path"
            )
        self._root = Path(path)
        if not self._root.exists():
            raise FileNotFoundError(f"Vault not found at {self._root}")

    @property
    def root(self) -> Path:
        return self._root

    def read(self, relative_path: str) -> str:
        full_path = self._root / relative_path
        if not full_path.exists():
            raise FileNotFoundError(f"Document not found: {relative_path}")
        return full_path.read_text()

    def write(self, relative_path: str, content: str) -> Path:
        full_path = self._root / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return full_path

    def list_docs(self, directory: str = "") -> list[str]:
        search_path = self._root / directory
        if not search_path.exists():
            return []
        return [
            str(p.relative_to(self._root))
            for p in search_path.rglob("*.md")
        ]

    def exists(self, relative_path: str) -> bool:
        return (self._root / relative_path).exists()

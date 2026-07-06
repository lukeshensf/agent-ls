from __future__ import annotations

from pathlib import Path
from typing import Optional

from agent_ls.config.settings import get_settings
from agent_ls.integrations.obsidian.templates import DocTemplate, Frontmatter, TemplateEngine


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

    def _resolve_within_root(self, relative_path: str) -> Path:
        """Join `relative_path` to the vault root and confirm it stays inside it.

        `relative_path` originates from LLM/Slack-derived text and is never validated
        upstream, so `../../etc/passwd` (traversal) or an absolute path (which would
        replace the root entirely under `/`) could otherwise read or write outside the
        vault. Resolving and checking containment — mirroring the guard in
        `emit_harness_node` — closes that hole. Symlinks are resolved too, so a link
        pointing outside the vault is rejected. Legitimate paths that normalize back
        inside (e.g. `a/../a/x.md`) are allowed, since the check is on the final location.
        """
        root = self._root.resolve()
        full_path = (self._root / relative_path).resolve()
        if full_path != root and not full_path.is_relative_to(root):
            raise ValueError(f"Path escapes vault root: {relative_path!r}")
        return full_path

    def read(self, relative_path: str) -> str:
        full_path = self._resolve_within_root(relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Document not found: {relative_path}")
        return full_path.read_text()

    def write(self, relative_path: str, content: str) -> Path:
        full_path = self._resolve_within_root(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return full_path

    def list_docs(self, directory: str = "") -> list[str]:
        search_path = self._resolve_within_root(directory)
        if not search_path.exists():
            return []
        # `search_path` is resolved, so returned paths must be relative to the
        # resolved root (they differ under symlinked roots, e.g. macOS /tmp).
        root = self._root.resolve()
        return [
            str(p.relative_to(root))
            for p in search_path.rglob("*.md")
        ]

    def exists(self, relative_path: str) -> bool:
        return self._resolve_within_root(relative_path).exists()

    def read_with_frontmatter(self, relative_path: str) -> tuple[Frontmatter, str]:
        content = self.read(relative_path)
        engine = TemplateEngine()
        return engine.parse_frontmatter(content)

    def write_with_template(self, relative_path: str, template: DocTemplate, context: dict) -> Path:
        engine = TemplateEngine()
        content = engine.render(template, context)
        return self.write(relative_path, content)

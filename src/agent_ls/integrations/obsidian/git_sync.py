from __future__ import annotations

from pathlib import Path
from typing import Optional

from git import Repo
from git.exc import InvalidGitRepositoryError


class GitSync:
    def __init__(self, vault_path: Path):
        try:
            self._repo = Repo(vault_path)
        except InvalidGitRepositoryError:
            raise ValueError(f"{vault_path} is not a git repository")

    def pull(self) -> None:
        if self._repo.remotes:
            self._repo.remotes.origin.pull()

    def push(self, message: str = "agent-ls: auto-update") -> None:
        if self._repo.is_dirty(untracked_files=True):
            self._repo.git.add(A=True)
            self._repo.index.commit(message)
        if self._repo.remotes:
            self._repo.remotes.origin.push()

    def commit_file(self, file_path: Path, message: Optional[str] = None) -> None:
        relative = file_path.relative_to(self._repo.working_dir)
        self._repo.index.add([str(relative)])
        self._repo.index.commit(message or f"agent-ls: update {relative}")

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog
from git import Repo
from git.exc import GitCommandError, GitError, InvalidGitRepositoryError

logger = structlog.get_logger()


@dataclass
class GitHistoryEntry:
    commit_hash: str
    author: str
    message: str
    timestamp: str
    files_changed: list[str] = field(default_factory=list)


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

    def commit_and_push(self, file_path: Path, message: Optional[str] = None) -> bool:
        """Atomic commit + push. Returns True on success."""
        try:
            self.commit_file(file_path, message)
            if self._repo.remotes:
                self._repo.remotes.origin.push()
            return True
        except (GitError, OSError) as e:
            # Expected failure modes only: any git error (GitError is the base of
            # GitCommandError et al.) or a filesystem error. Programming errors
            # (TypeError, etc.) are NOT caught here so they surface instead of
            # being masked as a silent False. `(GitCommandError, Exception)` was
            # redundant (Exception already covers it) and swallowed everything.
            logger.warning("commit_and_push_failed", error=str(e), error_type=type(e).__name__)
            return False

    def search_history(
        self, topic: str, max_results: int = 10, authors: Optional[list[str]] = None
    ) -> list[GitHistoryEntry]:
        """Search git log for commits related to a topic."""
        try:
            args = ["--all", f"--max-count={max_results}", f"--grep={topic}", "-i"]
            if authors:
                for author in authors:
                    args.append(f"--author={author}")

            log_output = self._repo.git.log(*args, format="%H|%an|%s|%aI", name_only=True)
        except GitCommandError:
            return []

        if not log_output.strip():
            return []

        entries = []
        current_entry: Optional[GitHistoryEntry] = None

        for line in log_output.strip().split("\n"):
            if "|" in line and line.count("|") >= 3:
                parts = line.split("|", 3)
                current_entry = GitHistoryEntry(
                    commit_hash=parts[0],
                    author=parts[1],
                    message=parts[3] if len(parts) > 3 else parts[2],
                    timestamp=parts[3] if len(parts) > 3 else "",
                )
                entries.append(current_entry)
            elif line.strip() and current_entry is not None:
                current_entry.files_changed.append(line.strip())

        return entries

    def get_file_at_commit(self, commit_hash: str, file_path: str) -> Optional[str]:
        """Retrieve file content at a specific commit."""
        try:
            return self._repo.git.show(f"{commit_hash}:{file_path}")
        except GitCommandError:
            return None

    def get_authors(self) -> list[str]:
        """Get unique authors from git log."""
        try:
            output = self._repo.git.log("--all", "--format=%an")
            return list(set(output.strip().split("\n"))) if output.strip() else []
        except GitCommandError:
            return []

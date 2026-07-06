from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

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
        except (GitCommandError, Exception) as e:
            logger.warning("commit_and_push_failed", error=str(e))
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

            # The commit subject (%s) is free-form and may contain '|', so it MUST be
            # the last field. With subject last, a bounded split("|", 3) keeps the
            # fixed-shape fields (hash|author|iso-date) intact and captures the entire
            # subject — pipes and all — as the final part.
            log_output = self._repo.git.log(*args, format="%H|%an|%aI|%s", name_only=True)
        except GitCommandError:
            return []

        if not log_output.strip():
            return []

        entries = []
        current_entry: Optional[GitHistoryEntry] = None

        for line in log_output.strip().split("\n"):
            # A header line has the three leading delimiters (hash|author|date|subject);
            # the subject may add more, so require at least 3, not exactly 3.
            if line.count("|") >= 3:
                commit_hash, author, timestamp, message = line.split("|", 3)
                current_entry = GitHistoryEntry(
                    commit_hash=commit_hash,
                    author=author,
                    message=message,
                    timestamp=timestamp,
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

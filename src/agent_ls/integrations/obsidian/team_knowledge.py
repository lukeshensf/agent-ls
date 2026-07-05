from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from agent_ls.integrations.obsidian.git_sync import GitSync

logger = structlog.get_logger()


@dataclass
class WorkingSetup:
    author: str
    timestamp: str
    commit_hash: str
    file_path: str
    content: str


class TeamKnowledge:
    def __init__(self, git_sync: GitSync):
        self._git = git_sync

    def find_working_setup(self, topic: str) -> Optional[WorkingSetup]:
        """Search git history for the most recent successful commit matching topic."""
        entries = self._git.search_history(topic, max_results=5)
        if not entries:
            return None

        for entry in entries:
            for file_path in entry.files_changed:
                if file_path.endswith(".md"):
                    content = self._git.get_file_at_commit(entry.commit_hash, file_path)
                    if content:
                        return WorkingSetup(
                            author=entry.author,
                            timestamp=entry.timestamp,
                            commit_hash=entry.commit_hash,
                            file_path=file_path,
                            content=content,
                        )

        return None

    def get_team_members(self) -> list[str]:
        """Extract unique authors from git log."""
        return self._git.get_authors()

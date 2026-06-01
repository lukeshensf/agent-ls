import pytest
from unittest.mock import MagicMock

from agent_ls.integrations.obsidian.git_sync import GitHistoryEntry
from agent_ls.integrations.obsidian.team_knowledge import TeamKnowledge


@pytest.fixture
def mock_git_sync():
    return MagicMock()


class TestFindWorkingSetup:
    def test_returns_first_match_with_md_file(self, mock_git_sync):
        mock_git_sync.search_history.return_value = [
            GitHistoryEntry(
                commit_hash="abc123",
                author="alice",
                message="agent-ls: setup log java",
                timestamp="2026-05-20T10:00:00",
                files_changed=["logs/platform-setup-2026-05-20.md"],
            ),
        ]
        mock_git_sync.get_file_at_commit.return_value = "# Java Setup\n\nbrew install java"

        kb = TeamKnowledge(mock_git_sync)
        result = kb.find_working_setup("java")

        assert result is not None
        assert result.author == "alice"
        assert result.content == "# Java Setup\n\nbrew install java"
        assert result.commit_hash == "abc123"

    def test_returns_none_when_no_history(self, mock_git_sync):
        mock_git_sync.search_history.return_value = []

        kb = TeamKnowledge(mock_git_sync)
        result = kb.find_working_setup("nonexistent")

        assert result is None

    def test_skips_non_md_files(self, mock_git_sync):
        mock_git_sync.search_history.return_value = [
            GitHistoryEntry(
                commit_hash="def456",
                author="bob",
                message="agent-ls: update",
                timestamp="2026-05-19",
                files_changed=["config.yaml", "script.sh"],
            ),
        ]

        kb = TeamKnowledge(mock_git_sync)
        result = kb.find_working_setup("setup")

        assert result is None

    def test_skips_when_file_content_unavailable(self, mock_git_sync):
        mock_git_sync.search_history.return_value = [
            GitHistoryEntry(
                commit_hash="ghi789",
                author="carol",
                message="agent-ls: setup",
                timestamp="2026-05-18",
                files_changed=["docs/setup.md"],
            ),
        ]
        mock_git_sync.get_file_at_commit.return_value = None

        kb = TeamKnowledge(mock_git_sync)
        result = kb.find_working_setup("setup")

        assert result is None


class TestGetTeamMembers:
    def test_returns_authors(self, mock_git_sync):
        mock_git_sync.get_authors.return_value = ["alice", "bob", "carol"]

        kb = TeamKnowledge(mock_git_sync)
        members = kb.get_team_members()

        assert set(members) == {"alice", "bob", "carol"}

"""Regression tests for `GitSync.search_history` field parsing (PLAN 3.2).

`search_history` formats git log as delimited fields and splits on ``|``. The
commit subject is free-form and may itself contain ``|``, so the field mapping
must be robust to that. These tests drive the REAL parser against a real git
repo (the consumer test `test_team_knowledge.py` mocks `search_history`
entirely, so the parse logic had no direct coverage).
"""
import pytest
from git import Repo

from agent_ls.integrations.obsidian.git_sync import GitSync


@pytest.fixture
def repo_with_history(tmp_path):
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Ada Lovelace").release()
    repo.config_writer().set_value("user", "email", "ada@example.com").release()

    def commit(filename: str, subject: str) -> None:
        f = tmp_path / filename
        f.write_text(f"content for {filename}\n")
        repo.index.add([filename])
        repo.index.commit(subject)

    # A plain subject, and a subject that itself contains the '|' delimiter.
    commit("setup-java.md", "setup java environment")
    commit("setup-node.md", "fix: retry brew || fall back to curl")
    return tmp_path, GitSync(tmp_path)


def _find(entries, filename):
    for e in entries:
        if filename in e.files_changed:
            return e
    raise AssertionError(f"no entry touched {filename}; got {entries!r}")


def test_message_is_subject_not_date(repo_with_history):
    """The message field must be the commit subject, and distinct from the timestamp."""
    _, git = repo_with_history
    entries = git.search_history("setup java")
    assert entries, "expected the java commit to match the grep"
    entry = _find(entries, "setup-java.md")

    assert entry.message == "setup java environment"
    # The timestamp must be the ISO author-date, NOT a copy of the message.
    assert entry.message != entry.timestamp
    assert "T" in entry.timestamp and entry.timestamp[:2] == "20"


def test_pipe_in_subject_is_preserved(repo_with_history):
    """A '|' inside the commit subject must not corrupt message/timestamp."""
    _, git = repo_with_history
    entries = git.search_history("fall back")
    assert entries, "expected the pipe-subject commit to match the grep"
    entry = _find(entries, "setup-node.md")

    # The full subject, pipe intact, is the message.
    assert entry.message == "fix: retry brew || fall back to curl"
    # The timestamp is still a clean ISO date, not a fragment of the subject.
    assert "T" in entry.timestamp and entry.timestamp[:2] == "20"
    assert "|" not in entry.timestamp

    # Hash and author are unaffected.
    assert len(entry.commit_hash) == 40
    assert entry.author == "Ada Lovelace"

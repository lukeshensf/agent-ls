import pytest
from git import Repo
from git.exc import GitCommandError

from agent_ls.integrations.obsidian.git_sync import GitSync


@pytest.fixture
def git_sync(tmp_path):
    Repo.init(tmp_path)
    return GitSync(tmp_path)


class TestCommitAndPushExceptionHandling:
    """commit_and_push is best-effort: expected git/OS failures degrade to False,
    but programming errors (e.g. TypeError) must surface, not be swallowed.
    """

    def test_returns_false_on_git_command_error(self, git_sync, tmp_path, monkeypatch):
        def boom(*args, **kwargs):
            raise GitCommandError("git push", 1)

        monkeypatch.setattr(git_sync, "commit_file", boom)
        # Expected git failure: degrade gracefully so the caller's success-gating
        # (failed push must not flip run_success) still works off the bool return.
        assert git_sync.commit_and_push(tmp_path / "doc.md") is False

    def test_returns_false_on_os_error(self, git_sync, tmp_path, monkeypatch):
        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(git_sync, "commit_file", boom)
        assert git_sync.commit_and_push(tmp_path / "doc.md") is False

    def test_does_not_swallow_type_error(self, git_sync, tmp_path, monkeypatch):
        # A TypeError is a programming bug, not an expected git failure. Before the
        # fix, `except (GitCommandError, Exception)` masked it and returned False.
        def boom(*args, **kwargs):
            raise TypeError("programming bug")

        monkeypatch.setattr(git_sync, "commit_file", boom)
        with pytest.raises(TypeError):
            git_sync.commit_and_push(tmp_path / "doc.md")

    def test_does_not_swallow_keyboard_interrupt(self, git_sync, tmp_path, monkeypatch):
        def boom(*args, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr(git_sync, "commit_file", boom)
        with pytest.raises(KeyboardInterrupt):
            git_sync.commit_and_push(tmp_path / "doc.md")

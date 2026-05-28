from pathlib import Path

import pytest

from agent_ls.security.allowlist import AllowlistChecker, SecurityClassification


@pytest.fixture
def checker():
    allowlist_path = Path(__file__).parent.parent.parent / "src" / "agent_ls" / "config" / "allowlist.yaml"
    return AllowlistChecker(str(allowlist_path))


class TestAutoApprove:
    def test_brew_install(self, checker):
        result = checker.classify("brew install python")
        assert result.classification == SecurityClassification.AUTO_APPROVE

    def test_brew_tap(self, checker):
        result = checker.classify("brew tap homebrew/cask")
        assert result.classification == SecurityClassification.AUTO_APPROVE

    def test_git_clone(self, checker):
        result = checker.classify("git clone https://github.com/user/repo.git")
        assert result.classification == SecurityClassification.AUTO_APPROVE

    def test_mkdir(self, checker):
        result = checker.classify("mkdir -p ~/projects/my-app")
        assert result.classification == SecurityClassification.AUTO_APPROVE

    def test_pip_install(self, checker):
        result = checker.classify("pip install requests")
        assert result.classification == SecurityClassification.AUTO_APPROVE

    def test_which(self, checker):
        result = checker.classify("which python3")
        assert result.classification == SecurityClassification.AUTO_APPROVE

    def test_ls(self, checker):
        result = checker.classify("ls")
        assert result.classification == SecurityClassification.AUTO_APPROVE

    def test_echo(self, checker):
        result = checker.classify("echo hello")
        assert result.classification == SecurityClassification.AUTO_APPROVE


class TestRequireApproval:
    def test_sudo(self, checker):
        result = checker.classify("sudo apt install something")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL

    def test_rm_rf(self, checker):
        result = checker.classify("rm -rf ~/old-project")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL

    def test_defaults_write(self, checker):
        result = checker.classify("defaults write com.apple.dock autohide -bool true")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL

    def test_curl_pipe_sh(self, checker):
        result = checker.classify("curl -fsSL https://example.com/install.sh | sh")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL

    def test_chmod(self, checker):
        result = checker.classify("chmod 755 /usr/local/bin/script")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL


class TestBlocked:
    def test_rm_rf_root(self, checker):
        result = checker.classify("rm -rf /")
        assert result.classification == SecurityClassification.BLOCKED

    def test_rm_rf_root_star(self, checker):
        result = checker.classify("rm -rf /*")
        assert result.classification == SecurityClassification.BLOCKED


class TestUnknownCommands:
    def test_unknown_defaults_to_approval(self, checker):
        result = checker.classify("some-custom-script --flag")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL
        assert result.reason == "Command not in allowlist"

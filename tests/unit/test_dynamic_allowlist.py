import pytest

from agent_ls.security.dynamic_allowlist import DynamicAllowlist


@pytest.fixture
def dynamic_allowlist(tmp_path):
    path = tmp_path / "approved_patterns.yaml"
    return DynamicAllowlist(persistent_path=path)


class TestDynamicAllowlist:
    def test_add_brew_pattern(self, dynamic_allowlist):
        pattern = dynamic_allowlist.add_approved_pattern("brew install requests")
        assert pattern == "brew install *"

    def test_add_pip_pattern(self, dynamic_allowlist):
        pattern = dynamic_allowlist.add_approved_pattern("pip install flask")
        assert pattern == "pip install *"

    def test_add_npm_global_pattern(self, dynamic_allowlist):
        pattern = dynamic_allowlist.add_approved_pattern("npm install -g typescript")
        assert pattern == "npm install -g *"

    def test_add_git_clone_pattern(self, dynamic_allowlist):
        pattern = dynamic_allowlist.add_approved_pattern("git clone https://github.com/x/y.git")
        assert pattern == "git clone *"

    def test_add_unknown_command(self, dynamic_allowlist):
        pattern = dynamic_allowlist.add_approved_pattern("custom-tool build --release")
        assert pattern == "custom-tool *"

    def test_persist_and_load(self, dynamic_allowlist):
        dynamic_allowlist.add_approved_pattern("brew install something")
        dynamic_allowlist.add_approved_pattern("pip install something")

        rules = dynamic_allowlist.load_dynamic_rules()
        assert len(rules) == 2
        patterns = [r["pattern"] for r in rules]
        assert "brew install *" in patterns
        assert "pip install *" in patterns

    def test_no_duplicates(self, dynamic_allowlist):
        dynamic_allowlist.add_approved_pattern("brew install foo")
        dynamic_allowlist.add_approved_pattern("brew install bar")

        rules = dynamic_allowlist.load_dynamic_rules()
        assert len(rules) == 1

    def test_load_empty(self, dynamic_allowlist):
        rules = dynamic_allowlist.load_dynamic_rules()
        assert rules == []

    def test_rules_have_metadata(self, dynamic_allowlist):
        dynamic_allowlist.add_approved_pattern("cargo install ripgrep")
        rules = dynamic_allowlist.load_dynamic_rules()
        assert rules[0]["risk"] == "low"
        assert rules[0]["reason"] == "User-approved"
        assert "approved_at" in rules[0]
        assert rules[0]["original_command"] == "cargo install ripgrep"

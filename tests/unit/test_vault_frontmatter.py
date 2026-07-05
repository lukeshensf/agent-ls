import pytest

from agent_ls.integrations.obsidian.vault import ObsidianVault
from agent_ls.integrations.obsidian.templates import DocTemplate


@pytest.fixture
def tmp_vault(tmp_path):
    return ObsidianVault(vault_path=str(tmp_path))


class TestVaultWithFrontmatter:
    def test_write_with_template(self, tmp_vault):
        path = tmp_vault.write_with_template(
            "test.md",
            DocTemplate.DAILY_LOG,
            {
                "title": "Test Log",
                "team": "eng",
                "summary": "All good",
                "steps": "- [x] Done",
                "output": "ok",
            },
        )
        assert path.exists()
        content = path.read_text()
        assert "---" in content
        assert "title: Test Log" in content
        assert "All good" in content

    def test_read_with_frontmatter(self, tmp_vault):
        content = "---\ntitle: Existing Doc\ntags:\n  - old\nteam: backend\n---\n\n# Existing Doc\n\nSome content"
        tmp_vault.write("docs/existing.md", content)
        fm, body = tmp_vault.read_with_frontmatter("docs/existing.md")
        assert fm.title == "Existing Doc"
        assert fm.team == "backend"
        assert "old" in fm.tags
        assert "Some content" in body

    def test_read_with_frontmatter_no_frontmatter(self, tmp_vault):
        tmp_vault.write("plain.md", "# Plain\n\nNo frontmatter here")
        fm, body = tmp_vault.read_with_frontmatter("plain.md")
        assert fm.title == "Untitled"
        assert "# Plain" in body


from agent_ls.integrations.obsidian.templates import (
    DocTemplate,
    Frontmatter,
    TemplateEngine,
    _get_placeholders,
)


class TestFrontmatter:
    def test_to_yaml(self):
        fm = Frontmatter(
            title="Test Doc",
            tags=["test"],
            team="payments",
            created="2024-01-01T00:00:00Z",
            updated="2024-01-01T00:00:00Z",
        )
        yaml_str = fm.to_yaml()
        assert "title: Test Doc" in yaml_str
        assert "team: payments" in yaml_str
        assert "- test" in yaml_str

    def test_from_yaml(self):
        yaml_str = "title: My Doc\ncreated: 2024-01-01\ntags:\n  - setup\nteam: eng"
        fm = Frontmatter.from_yaml(yaml_str)
        assert fm.title == "My Doc"
        assert fm.team == "eng"
        assert "setup" in fm.tags

    def test_from_yaml_empty(self):
        fm = Frontmatter.from_yaml("")
        assert fm.title == "Untitled"

    def test_auto_timestamps(self):
        fm = Frontmatter(title="Test")
        assert fm.created != ""
        assert fm.updated != ""

    def test_roundtrip(self):
        fm = Frontmatter(
            title="Round Trip",
            tags=["a", "b"],
            team="backend",
            created="2024-06-15T10:00:00Z",
            updated="2024-06-15T10:00:00Z",
        )
        yaml_str = fm.to_yaml()
        fm2 = Frontmatter.from_yaml(yaml_str)
        assert fm2.title == fm.title
        assert fm2.team == fm.team
        assert fm2.tags == fm.tags


class TestTemplateEngine:
    def test_render_daily_log(self):
        engine = TemplateEngine()
        content = engine.render(
            DocTemplate.DAILY_LOG,
            {
                "title": "Setup Log",
                "team": "payments",
                "summary": "3/3 done",
                "steps": "- [x] Install node",
                "output": "```\nv20.0.0\n```",
            },
        )
        assert "---" in content
        assert "title: Setup Log" in content
        assert "team: payments" in content
        assert "# Setup Log" in content
        assert "3/3 done" in content
        assert "- [x] Install node" in content

    def test_render_setup_guide(self):
        engine = TemplateEngine()
        content = engine.render(
            DocTemplate.SETUP_GUIDE,
            {
                "title": "Python Setup",
                "prerequisites": "macOS 14+",
                "steps": "1. Install brew\n2. Install python",
                "verification": "python3 --version",
                "troubleshooting": "If brew fails, run xcode-select --install",
            },
        )
        assert "# Python Setup" in content
        assert "macOS 14+" in content
        assert "xcode-select" in content

    def test_render_missing_placeholders(self):
        engine = TemplateEngine()
        content = engine.render(DocTemplate.DESIGN_DOC, {"title": "Test"})
        assert "# Test" in content
        assert "{context}" not in content

    def test_parse_frontmatter(self):
        content = "---\ntitle: My Doc\ntags:\n  - test\n---\n\n# My Doc\n\nBody here"
        engine = TemplateEngine()
        fm, body = engine.parse_frontmatter(content)
        assert fm.title == "My Doc"
        assert "test" in fm.tags
        assert "# My Doc" in body
        assert "Body here" in body

    def test_parse_frontmatter_no_frontmatter(self):
        content = "# Just a doc\n\nNo frontmatter"
        engine = TemplateEngine()
        fm, body = engine.parse_frontmatter(content)
        assert fm.title == "Untitled"
        assert body == content


class TestGetPlaceholders:
    def test_finds_placeholders(self):
        assert _get_placeholders("{foo} and {bar}") == ["foo", "bar"]

    def test_no_placeholders(self):
        assert _get_placeholders("no placeholders") == []

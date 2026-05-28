import pytest

from agent_ls.integrations.slack.formatter import SlackFormatter


@pytest.fixture
def formatter():
    return SlackFormatter()


class TestSlackFormatter:
    def test_strip_frontmatter(self, formatter):
        md = "---\ntitle: Test\ntags: [a]\n---\n\n# Hello\n\nContent"
        result = formatter.convert(md)
        assert "title: Test" not in result
        assert "*Hello*" in result
        assert "Content" in result

    def test_convert_headers(self, formatter):
        assert "*Title*" in formatter.convert("# Title")
        assert "*Sub*" in formatter.convert("## Sub")
        assert "*Deep*" in formatter.convert("### Deep")

    def test_convert_bold(self, formatter):
        result = formatter.convert("This is **bold** text")
        assert "*bold*" in result

    def test_convert_wikilinks_simple(self, formatter):
        result = formatter.convert("See [[Setup Guide]] for details")
        assert "Setup Guide" in result
        assert "[[" not in result

    def test_convert_wikilinks_with_alias(self, formatter):
        result = formatter.convert("Check [[long-page-name|the guide]]")
        assert "the guide" in result
        assert "long-page-name" not in result

    def test_convert_links(self, formatter):
        result = formatter.convert("Visit [docs](https://example.com)")
        assert "<https://example.com|docs>" in result

    def test_convert_callouts_note(self, formatter):
        result = formatter.convert("> [!NOTE] This is important")
        assert ":information_source:" in result
        assert "This is important" in result

    def test_convert_callouts_warning(self, formatter):
        result = formatter.convert("> [!WARNING] Be careful")
        assert ":warning:" in result

    def test_convert_callouts_tip(self, formatter):
        result = formatter.convert("> [!TIP] Helpful hint")
        assert ":bulb:" in result

    def test_convert_checklists_done(self, formatter):
        result = formatter.convert("- [x] Install Python")
        assert ":white_check_mark:" in result
        assert "Install Python" in result

    def test_convert_checklists_pending(self, formatter):
        result = formatter.convert("- [ ] Configure IDE")
        assert ":white_large_square:" in result
        assert "Configure IDE" in result

    def test_code_blocks_preserved(self, formatter):
        md = "```python\nprint('hello')\n```"
        result = formatter.convert(md)
        assert "```python" in result
        assert "print('hello')" in result

    def test_to_blocks(self, formatter):
        md = "# Title\n\nSome content here"
        blocks = formatter.to_blocks(md)
        assert len(blocks) >= 1
        assert blocks[0]["type"] == "section"
        assert blocks[0]["text"]["type"] == "mrkdwn"

    def test_full_document(self, formatter):
        md = """---
title: Setup Guide
tags: [setup]
---

# Python Setup

## Prerequisites

- [x] macOS installed
- [ ] Xcode CLI tools

## Steps

1. Install Homebrew
2. Run `brew install python@3.12`

> [!NOTE] Use Python 3.12 for compatibility

See [[Troubleshooting]] or [official docs](https://python.org) for help.
"""
        result = formatter.convert(md)
        assert "title: Setup Guide" not in result
        assert "*Python Setup*" in result
        assert ":white_check_mark: macOS installed" in result
        assert ":white_large_square: Xcode CLI tools" in result
        assert ":information_source:" in result
        assert "Troubleshooting" in result
        assert "<https://python.org|official docs>" in result

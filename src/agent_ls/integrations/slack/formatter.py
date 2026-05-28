from __future__ import annotations

import re


class SlackFormatter:
    """Convert Obsidian markdown to Slack mrkdwn format."""

    def convert(self, obsidian_markdown: str) -> str:
        text = self._strip_frontmatter(obsidian_markdown)
        text = self._convert_code_blocks(text)
        text = self._convert_headers(text)
        text = self._convert_bold_italic(text)
        text = self._convert_wikilinks(text)
        text = self._convert_links(text)
        text = self._convert_callouts(text)
        text = self._convert_checklists(text)
        return text.strip()

    def to_blocks(self, obsidian_markdown: str) -> list[dict]:
        """Convert to Slack Block Kit format."""
        text = self.convert(obsidian_markdown)
        blocks = []

        sections = re.split(r"\n(?=\*[^*]+\*\n)", text)
        for section in sections:
            section = section.strip()
            if not section:
                continue
            if len(section) > 3000:
                section = section[:3000] + "..."
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": section},
            })

        return blocks

    def _strip_frontmatter(self, text: str) -> str:
        if not text.startswith("---"):
            return text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return text
        return parts[2].lstrip("\n")

    def _convert_headers(self, text: str) -> str:
        return re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)

    def _convert_bold_italic(self, text: str) -> str:
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"_*\1*_", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
        return text

    def _convert_wikilinks(self, text: str) -> str:
        text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
        text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
        return text

    def _convert_links(self, text: str) -> str:
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)

    def _convert_callouts(self, text: str) -> str:
        def _replace_callout(m):
            callout_type = m.group(1).lower()
            content = m.group(2)
            icons = {
                "note": ":information_source:",
                "info": ":information_source:",
                "tip": ":bulb:",
                "warning": ":warning:",
                "danger": ":rotating_light:",
                "important": ":exclamation:",
            }
            icon = icons.get(callout_type, ":memo:")
            return f"{icon} *{callout_type.title()}:* {content}"

        return re.sub(
            r"^>\s*\[!(\w+)\]\s*(.+)$", _replace_callout, text, flags=re.MULTILINE
        )

    def _convert_checklists(self, text: str) -> str:
        text = re.sub(
            r"^- \[x\]\s+(.+)$",
            r":white_check_mark: \1",
            text,
            flags=re.MULTILINE,
        )
        text = re.sub(
            r"^- \[ \]\s+(.+)$",
            r":white_large_square: \1",
            text,
            flags=re.MULTILINE,
        )
        return text

    def _convert_code_blocks(self, text: str) -> str:
        return text

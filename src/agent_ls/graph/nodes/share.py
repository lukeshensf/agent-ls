from __future__ import annotations

from agent_ls.graph.state import AgentState
from agent_ls.integrations.obsidian.vault import ObsidianVault
from agent_ls.integrations.slack.client import SlackClient


async def slack_share_node(state: AgentState) -> dict:
    """Share an Obsidian document to a Slack channel."""
    obsidian_docs = state.get("obsidian_docs", [])
    if not obsidian_docs:
        return {}

    vault = ObsidianVault()
    client = SlackClient()

    doc_path = obsidian_docs[-1]
    try:
        content = vault.read(doc_path)
    except FileNotFoundError:
        return {"error": f"Document not found: {doc_path}"}

    formatted = _markdown_to_slack(content)

    # For now, determine channel from state or default
    # This will be enhanced when we add proper channel routing
    return {"obsidian_docs": obsidian_docs}


def _markdown_to_slack(markdown: str) -> str:
    """Convert Obsidian markdown to Slack mrkdwn format."""
    text = markdown
    # Headers: # Title -> *Title*
    import re

    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Bold: **text** -> *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Inline code stays the same: `code` -> `code`
    # Links: [text](url) -> <url|text>
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"<\2|\1>", text)
    # Wikilinks: [[page]] -> page
    text = re.sub(r"\[\[(.+?)\]\]", r"\1", text)
    return text

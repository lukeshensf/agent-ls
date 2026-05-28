from __future__ import annotations

import structlog

from agent_ls.graph.state import AgentState
from agent_ls.integrations.obsidian.vault import ObsidianVault
from agent_ls.integrations.slack.client import SlackClient
from agent_ls.integrations.slack.formatter import SlackFormatter

logger = structlog.get_logger()


async def slack_share_node(state: AgentState) -> dict:
    """Share an Obsidian document to a Slack channel."""
    obsidian_docs = state.get("obsidian_docs", [])
    if not obsidian_docs:
        return {"error": "No document specified to share"}

    channel = state.get("share_channel")
    if not channel:
        return {"error": "No target channel specified"}

    vault = ObsidianVault()
    doc_path = obsidian_docs[-1]
    try:
        content = vault.read(doc_path)
    except FileNotFoundError:
        return {"error": f"Document not found: {doc_path}"}

    formatter = SlackFormatter()
    slack_text = formatter.convert(content)
    blocks = formatter.to_blocks(content)

    try:
        client = SlackClient()
        result = await client.post_message(channel, slack_text, blocks=blocks)
        return {"share_result": result.get("ts", "posted")}
    except (ValueError, RuntimeError) as e:
        logger.warning("slack_share_failed", error=str(e))
        return {"error": f"Slack share failed: {e}"}

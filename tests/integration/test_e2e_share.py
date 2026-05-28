"""End-to-end test for the share flow: router -> obsidian_read -> slack_share."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.graph.state import UserContext


@pytest.mark.asyncio
async def test_share_flow_end_to_end():
    """Verify: message with share intent -> reads doc -> formats -> posts to Slack."""
    from langchain_core.messages import HumanMessage

    from agent_ls.graph.nodes.share import slack_share_node
    from agent_ls.graph.router import router_node

    initial_state = {
        "messages": [HumanMessage(content="share docs/setup-guide.md to #eng-team")],
        "user_context": UserContext(team="eng"),
        "intent": "",
        "plan": [],
        "current_step": 0,
        "execution_log": [],
        "approval_pending": None,
        "obsidian_docs": [],
        "slack_results": [],
        "error": None,
        "share_channel": None,
        "share_result": None,
        "extracted_urls": [],
    }

    # Step 1: Router classifies intent and extracts channel
    model_response = MagicMock()
    model_response.content = "share"

    with patch("agent_ls.graph.router.ModelRouter") as mock_router_cls:
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        router_result = await router_node(initial_state)

    assert router_result["intent"] == "share"
    assert router_result["share_channel"] == "eng-team"

    # Step 2: Merge router output into state
    state_after_router = {**initial_state, **router_result}
    state_after_router["obsidian_docs"] = ["docs/setup-guide.md"]

    # Step 3: Share node reads doc and posts to Slack
    doc_content = """---
title: Setup Guide
team: eng
---

# Setup Guide

## Steps

- [x] Install Python
- [ ] Configure IDE

> [!NOTE] Use Python 3.12

See [[Troubleshooting]] for help.
"""

    with (
        patch("agent_ls.graph.nodes.share.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.share.SlackClient") as mock_client_cls,
    ):
        mock_vault = MagicMock()
        mock_vault.read.return_value = doc_content
        mock_vault_cls.return_value = mock_vault

        mock_client = MagicMock()
        mock_client.post_message = AsyncMock(return_value={"ts": "1700000000.000"})
        mock_client_cls.return_value = mock_client

        share_result = await slack_share_node(state_after_router)

    assert share_result["share_result"] == "1700000000.000"

    # Verify the posted text was properly formatted
    post_call = mock_client.post_message.call_args
    posted_text = post_call[0][1]
    assert "title: Setup Guide" not in posted_text
    assert "*Setup Guide*" in posted_text
    assert ":white_check_mark:" in posted_text
    assert ":information_source:" in posted_text
    assert "Troubleshooting" in posted_text
    assert "[[" not in posted_text

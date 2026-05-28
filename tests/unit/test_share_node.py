from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.graph.nodes.share import slack_share_node
from agent_ls.graph.state import UserContext


@pytest.fixture
def share_state():
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="share setup guide to #eng-team")],
        "user_context": UserContext(team="eng"),
        "intent": "share",
        "plan": [],
        "current_step": 0,
        "execution_log": [],
        "approval_pending": None,
        "obsidian_docs": ["docs/setup-guide.md"],
        "slack_results": [],
        "error": None,
        "share_channel": "eng-team",
        "share_result": None,
        "extracted_urls": [],
    }


@pytest.mark.asyncio
async def test_share_node_success(share_state):
    with (
        patch("agent_ls.graph.nodes.share.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.share.SlackClient") as mock_client_cls,
    ):
        mock_vault = MagicMock()
        mock_vault.read.return_value = "# Setup Guide\n\nInstall python"
        mock_vault_cls.return_value = mock_vault

        mock_client = MagicMock()
        mock_client.post_message = AsyncMock(return_value={"ts": "123.456"})
        mock_client_cls.return_value = mock_client

        result = await slack_share_node(share_state)

    assert result["share_result"] == "123.456"
    mock_client.post_message.assert_called_once()
    call_args = mock_client.post_message.call_args
    assert call_args[0][0] == "eng-team"


@pytest.mark.asyncio
async def test_share_node_no_docs():
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content="share")],
        "user_context": UserContext(),
        "intent": "share",
        "plan": [],
        "current_step": 0,
        "execution_log": [],
        "approval_pending": None,
        "obsidian_docs": [],
        "slack_results": [],
        "error": None,
        "share_channel": "eng",
        "share_result": None,
        "extracted_urls": [],
    }
    result = await slack_share_node(state)
    assert "error" in result
    assert "No document" in result["error"]


@pytest.mark.asyncio
async def test_share_node_no_channel(share_state):
    share_state["share_channel"] = None
    result = await slack_share_node(share_state)
    assert "error" in result
    assert "No target channel" in result["error"]


@pytest.mark.asyncio
async def test_share_node_doc_not_found(share_state):
    with patch("agent_ls.graph.nodes.share.ObsidianVault") as mock_vault_cls:
        mock_vault = MagicMock()
        mock_vault.read.side_effect = FileNotFoundError("not found")
        mock_vault_cls.return_value = mock_vault

        result = await slack_share_node(share_state)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_share_node_slack_failure(share_state):
    with (
        patch("agent_ls.graph.nodes.share.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.share.SlackClient") as mock_client_cls,
    ):
        mock_vault = MagicMock()
        mock_vault.read.return_value = "# Doc\n\nContent"
        mock_vault_cls.return_value = mock_vault

        mock_client_cls.side_effect = ValueError("No token")

        result = await slack_share_node(share_state)

    assert "error" in result

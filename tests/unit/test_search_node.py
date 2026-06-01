from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.graph.nodes.search import slack_search_node
from agent_ls.graph.state import SlackMessage, UserContext


@pytest.fixture
def base_state():
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="how do I set up python")],
        "user_context": UserContext(team="payments"),
        "intent": "search",
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
        "processed_message_ids": [],
        "run_success": False,
    }


@pytest.mark.asyncio
async def test_search_node_success(base_state):
    from agent_ls.integrations.slack.smart_search import SmartSearchResult

    model_response = MagicMock()
    model_response.content = "python setup guide"

    mock_messages = [
        SlackMessage(
            channel="eng", user="alice", text="install python", timestamp="1", permalink=None
        )
    ]
    mock_search_result = SmartSearchResult(
        messages=mock_messages,
        thread_contexts={},
        new_processed_ids=["1"],
        total_raw=1,
        total_after_dedup=1,
    )

    with (
        patch("agent_ls.graph.nodes.search.ModelRouter") as mock_router_cls,
        patch("agent_ls.graph.nodes.search.SmartSearch") as mock_search_cls,
        patch("agent_ls.graph.nodes.search.get_settings") as mock_settings,
    ):
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        mock_settings.return_value.slack.follow_threads = True

        mock_search = MagicMock()
        mock_search.search = AsyncMock(return_value=mock_search_result)
        mock_search_cls.return_value = mock_search

        result = await slack_search_node(base_state)

    assert len(result["slack_results"]) == 1
    assert result["slack_results"][0].text == "install python"
    assert result["processed_message_ids"] == ["1"]
    mock_search.search.assert_called_once()


@pytest.mark.asyncio
async def test_search_node_slack_failure(base_state):
    model_response = MagicMock()
    model_response.content = "python setup"

    with (
        patch("agent_ls.graph.nodes.search.ModelRouter") as mock_router_cls,
        patch("agent_ls.graph.nodes.search.SmartSearch") as mock_search_cls,
        patch("agent_ls.graph.nodes.search.get_settings") as mock_settings,
    ):
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        mock_settings.return_value.slack.follow_threads = True

        mock_search_cls.side_effect = ValueError("No token")

        result = await slack_search_node(base_state)

    assert result["slack_results"] == []
    assert "error" in result

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.graph.nodes.context_gather import context_gather_node
from agent_ls.graph.state import UserContext


@pytest.fixture
def base_state():
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="set up my dev environment")],
        "user_context": UserContext(),
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


@pytest.mark.asyncio
async def test_context_gather_success(base_state):
    mock_profile = {
        "title": "Senior Backend Engineer - Payments Team",
        "display_name": "jdoe",
        "status_text": "Working on payments v2",
    }
    model_response = MagicMock()
    model_response.content = '{"team": "payments", "role": "backend engineer", "tech_stack": ["java", "kafka"]}'

    with (
        patch(
            "agent_ls.graph.nodes.context_gather.SlackClient"
        ) as mock_client_cls,
        patch(
            "agent_ls.graph.nodes.context_gather.ModelRouter"
        ) as mock_router_cls,
    ):
        mock_client = MagicMock()
        mock_client.get_user_profile = AsyncMock(return_value=mock_profile)
        mock_client_cls.return_value = mock_client

        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        result = await context_gather_node(base_state)

    ctx = result["user_context"]
    assert ctx.team == "payments"
    assert ctx.role == "backend engineer"
    assert "java" in ctx.tech_stack
    assert "kafka" in ctx.tech_stack


@pytest.mark.asyncio
async def test_context_gather_no_slack_token(base_state):
    with patch(
        "agent_ls.graph.nodes.context_gather.SlackClient",
        side_effect=ValueError("Slack token not configured"),
    ):
        result = await context_gather_node(base_state)

    ctx = result["user_context"]
    assert ctx.team is None
    assert ctx.role is None
    assert ctx.tech_stack == []


@pytest.mark.asyncio
async def test_context_gather_model_parse_failure(base_state):
    mock_profile = {"title": "Engineer", "display_name": "test", "status_text": ""}
    model_response = MagicMock()
    model_response.content = "not valid json"

    with (
        patch(
            "agent_ls.graph.nodes.context_gather.SlackClient"
        ) as mock_client_cls,
        patch(
            "agent_ls.graph.nodes.context_gather.ModelRouter"
        ) as mock_router_cls,
    ):
        mock_client = MagicMock()
        mock_client.get_user_profile = AsyncMock(return_value=mock_profile)
        mock_client_cls.return_value = mock_client

        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        result = await context_gather_node(base_state)

    ctx = result["user_context"]
    assert ctx.team is None

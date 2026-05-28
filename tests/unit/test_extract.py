from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.graph.nodes.extract import extract_node, _extract_urls, _deduplicate
from agent_ls.graph.state import SlackMessage, UserContext


@pytest.fixture
def state_with_slack_results():
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="how to set up python")],
        "user_context": UserContext(),
        "intent": "search",
        "plan": [],
        "current_step": 0,
        "execution_log": [],
        "approval_pending": None,
        "obsidian_docs": [],
        "slack_results": [
            SlackMessage(
                channel="eng-setup",
                user="alice",
                text="For python setup: brew install python@3.12 then pip install poetry",
                timestamp="1700000000",
                permalink=None,
            ),
            SlackMessage(
                channel="eng-setup",
                user="bob",
                text="Also clone https://github.com/team/backend.git after that",
                timestamp="1700000001",
                permalink=None,
            ),
        ],
        "error": None,
        "share_channel": None,
        "share_result": None,
        "extracted_urls": [],
    }


@pytest.mark.asyncio
async def test_extract_produces_plan_steps(state_with_slack_results):
    model_response = MagicMock()
    model_response.content = """[
        {"description": "Install Python 3.12", "command": "brew install python@3.12"},
        {"description": "Install Poetry", "command": "pip install poetry"},
        {"description": "Clone backend repo", "command": "git clone https://github.com/team/backend.git"}
    ]"""

    with patch("agent_ls.graph.nodes.extract.ModelRouter") as mock_router_cls:
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        result = await extract_node(state_with_slack_results)

    assert len(result["plan"]) == 3
    assert result["plan"][0].description == "Install Python 3.12"
    assert result["plan"][0].command == "brew install python@3.12"
    assert result["current_step"] == 0


@pytest.mark.asyncio
async def test_extract_empty_slack_results():
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content="test")],
        "user_context": UserContext(),
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
    }
    result = await extract_node(state)
    assert result["plan"] == []
    assert result["current_step"] == 0


@pytest.mark.asyncio
async def test_extract_bad_model_response(state_with_slack_results):
    model_response = MagicMock()
    model_response.content = "I don't know what to do"

    with patch("agent_ls.graph.nodes.extract.ModelRouter") as mock_router_cls:
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        result = await extract_node(state_with_slack_results)

    assert result["plan"] == []


@pytest.mark.asyncio
async def test_extract_captures_urls(state_with_slack_results):
    model_response = MagicMock()
    model_response.content = "[]"

    with patch("agent_ls.graph.nodes.extract.ModelRouter") as mock_router_cls:
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        result = await extract_node(state_with_slack_results)

    assert "https://github.com/team/backend.git" in result["extracted_urls"]


def test_extract_urls():
    text = "Check https://example.com/setup and http://internal.dev/docs for more"
    urls = _extract_urls(text)
    assert "https://example.com/setup" in urls
    assert "http://internal.dev/docs" in urls


def test_extract_urls_empty():
    assert _extract_urls("no urls here") == []


def test_deduplicate_removes_near_duplicates():
    messages = [
        SlackMessage(channel="eng", user="a", text="install python via brew", timestamp="1"),
        SlackMessage(channel="eng", user="b", text="install python via brew please", timestamp="2"),
        SlackMessage(channel="eng", user="c", text="set up docker compose", timestamp="3"),
    ]
    result = _deduplicate(messages)
    assert len(result) == 2
    assert result[0].text == "install python via brew"
    assert result[1].text == "set up docker compose"


def test_deduplicate_empty():
    assert _deduplicate([]) == []


def test_deduplicate_all_unique():
    messages = [
        SlackMessage(channel="eng", user="a", text="install python", timestamp="1"),
        SlackMessage(channel="eng", user="b", text="set up docker", timestamp="2"),
        SlackMessage(channel="eng", user="c", text="configure vim", timestamp="3"),
    ]
    result = _deduplicate(messages)
    assert len(result) == 3

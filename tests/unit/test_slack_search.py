from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.integrations.slack.search import SlackSearch
from agent_ls.graph.state import SlackMessage


@pytest.fixture
def mock_slack_client():
    client = MagicMock()
    client._client = MagicMock()
    return client


class TestSlackSearch:
    @pytest.mark.asyncio
    async def test_basic_search(self, mock_slack_client):
        mock_slack_client._client.search_messages.return_value = {
            "messages": {
                "matches": [
                    {
                        "channel": {"name": "eng"},
                        "username": "alice",
                        "text": "install node",
                        "ts": "1",
                        "permalink": "http://x",
                    }
                ]
            }
        }
        search = SlackSearch(client=mock_slack_client)
        results = await search.search("node setup")
        assert len(results) == 1
        assert results[0].channel == "eng"
        assert results[0].text == "install node"

    @pytest.mark.asyncio
    async def test_channel_filter(self, mock_slack_client):
        mock_slack_client._client.search_messages.return_value = {
            "messages": {"matches": []}
        }
        search = SlackSearch(client=mock_slack_client)
        await search.search("setup", channels=["payments-eng"])
        call_args = mock_slack_client._client.search_messages.call_args
        query = call_args.kwargs.get("query", call_args[1].get("query", ""))
        assert "in:#payments-eng" in query

    @pytest.mark.asyncio
    async def test_date_range_filter(self, mock_slack_client):
        mock_slack_client._client.search_messages.return_value = {
            "messages": {"matches": []}
        }
        search = SlackSearch(client=mock_slack_client)
        await search.search("setup", date_range=("2024-01-01", "2024-06-01"))
        call_args = mock_slack_client._client.search_messages.call_args
        query = call_args.kwargs.get("query", call_args[1].get("query", ""))
        assert "after:2024-01-01" in query
        assert "before:2024-06-01" in query

    @pytest.mark.asyncio
    async def test_text_truncation(self, mock_slack_client):
        long_text = "x" * 5000
        mock_slack_client._client.search_messages.return_value = {
            "messages": {
                "matches": [
                    {
                        "channel": {"name": "eng"},
                        "username": "a",
                        "text": long_text,
                        "ts": "1",
                        "permalink": None,
                    }
                ]
            }
        }
        search = SlackSearch(client=mock_slack_client)
        results = await search.search("test")
        assert len(results[0].text) == 2000

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, mock_slack_client):
        mock_slack_client._client.search_messages.side_effect = [
            Exception("ratelimited"),
            {
                "messages": {
                    "matches": [
                        {
                            "channel": {"name": "eng"},
                            "username": "a",
                            "text": "ok",
                            "ts": "1",
                            "permalink": None,
                        }
                    ]
                }
            },
        ]
        search = SlackSearch(client=mock_slack_client)
        results = await search.search("test")
        assert len(results) == 1
        assert mock_slack_client._client.search_messages.call_count == 2

    @pytest.mark.asyncio
    async def test_pagination(self, mock_slack_client):
        page1 = [
            {
                "channel": {"name": "eng"},
                "username": "a",
                "text": f"msg{i}",
                "ts": str(i),
                "permalink": None,
            }
            for i in range(20)
        ]
        page2 = [
            {
                "channel": {"name": "eng"},
                "username": "a",
                "text": "last",
                "ts": "21",
                "permalink": None,
            }
        ]
        mock_slack_client._client.search_messages.side_effect = [
            {"messages": {"matches": page1}},
            {"messages": {"matches": page2}},
        ]
        search = SlackSearch(client=mock_slack_client)
        results = await search.search("test", max_results=50)
        assert len(results) == 21
        assert mock_slack_client._client.search_messages.call_count == 2

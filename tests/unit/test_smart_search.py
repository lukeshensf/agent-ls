import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_ls.graph.state import SlackMessage
from agent_ls.integrations.slack.smart_search import SmartSearch


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_thread_replies = AsyncMock(return_value=[])
    return client


@pytest.fixture
def sample_messages():
    return [
        SlackMessage(channel="eng", user="alice", text="install java with brew install java", timestamp="1.0"),
        SlackMessage(channel="eng", user="bob", text="python setup guide", timestamp="2.0"),
        SlackMessage(channel="eng", user="carol", text="java jdk 21 setup instructions", timestamp="3.0"),
    ]


class TestDeduplicate:
    def test_filters_processed_ids(self, mock_client, sample_messages):
        search = SmartSearch(client=mock_client)
        result = search._deduplicate(sample_messages, processed_ids=["1.0", "2.0"])
        assert len(result) == 1
        assert result[0].timestamp == "3.0"

    def test_no_dedup_with_empty_ids(self, mock_client, sample_messages):
        search = SmartSearch(client=mock_client)
        result = search._deduplicate(sample_messages, processed_ids=[])
        assert len(result) == 3

    def test_deduplicates_within_batch(self, mock_client):
        msgs = [
            SlackMessage(channel="eng", user="a", text="x", timestamp="1.0"),
            SlackMessage(channel="eng", user="b", text="y", timestamp="1.0"),
        ]
        search = SmartSearch(client=mock_client)
        result = search._deduplicate(msgs, processed_ids=[])
        assert len(result) == 1


class TestRankResults:
    def test_ranks_by_keyword_overlap(self, mock_client, sample_messages):
        search = SmartSearch(client=mock_client)
        ranked = search._rank_results(sample_messages, "java setup")
        assert ranked[0].timestamp == "3.0"

    def test_empty_query_preserves_order(self, mock_client, sample_messages):
        search = SmartSearch(client=mock_client)
        ranked = search._rank_results(sample_messages, "")
        assert len(ranked) == 3


class TestSearch:
    @pytest.mark.asyncio
    async def test_full_search_flow(self, mock_client, sample_messages):
        search = SmartSearch(client=mock_client)
        search._search = MagicMock()
        search._search.search = AsyncMock(return_value=sample_messages)

        result = await search.search(
            "java setup",
            processed_ids=["1.0"],
            follow_threads=False,
        )

        assert result.total_raw == 3
        assert result.total_after_dedup == 2
        assert "1.0" not in result.new_processed_ids

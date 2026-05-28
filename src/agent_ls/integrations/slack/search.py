from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

import structlog

from agent_ls.integrations.slack.client import SlackClient

if TYPE_CHECKING:
    from agent_ls.graph.state import SlackMessage

logger = structlog.get_logger()


class SlackSearch:
    def __init__(self, client: Optional[SlackClient] = None):
        self._client = client or SlackClient()

    async def search(
        self,
        query: str,
        channels: list[str] | None = None,
        max_results: int = 50,
        sort: str = "timestamp",
        date_range: tuple[str, str] | None = None,
    ) -> list[SlackMessage]:
        """Search Slack with pagination, filtering, and retry."""
        from agent_ls.graph.state import SlackMessage

        full_query = self._build_query(query, channels, date_range)
        raw_results = await self._paginate(
            full_query, count=20, max_pages=(max_results // 20) + 1
        )

        return [
            SlackMessage(
                channel=msg.get("channel", {}).get("name", "unknown"),
                user=msg.get("username", "unknown"),
                text=msg.get("text", "")[:2000],
                timestamp=msg.get("ts", ""),
                permalink=msg.get("permalink"),
            )
            for msg in raw_results[:max_results]
        ]

    def _build_query(
        self,
        query: str,
        channels: list[str] | None,
        date_range: tuple[str, str] | None,
    ) -> str:
        parts = [query]
        if channels:
            parts.extend(f"in:#{ch}" for ch in channels)
        if date_range:
            parts.append(f"after:{date_range[0]}")
            parts.append(f"before:{date_range[1]}")
        return " ".join(parts)

    async def _paginate(self, query: str, count: int, max_pages: int) -> list[dict]:
        all_results = []
        for page in range(1, max_pages + 1):
            try:
                results = await self._search_with_retry(query, count, page)
                all_results.extend(results)
                if len(results) < count:
                    break
            except RuntimeError:
                break
        return all_results

    async def _search_with_retry(
        self, query: str, count: int, page: int, max_retries: int = 3
    ) -> list[dict]:
        for attempt in range(max_retries):
            try:
                response = self._client._client.search_messages(
                    query=query, count=count, page=page
                )
                return response["messages"]["matches"]
            except Exception as e:
                if "ratelimited" in str(e).lower() and attempt < max_retries - 1:
                    wait = 0.5 * (2**attempt)
                    logger.info("slack_rate_limited", retry_in=wait)
                    await asyncio.sleep(wait)
                    continue
                raise RuntimeError(f"Slack search failed: {e}") from e
        return []

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import structlog

from agent_ls.graph.state import SlackMessage
from agent_ls.integrations.slack.client import SlackClient
from agent_ls.integrations.slack.search import SlackSearch

logger = structlog.get_logger()


@dataclass
class SmartSearchResult:
    messages: list[SlackMessage]
    thread_contexts: dict[str, list[SlackMessage]]
    new_processed_ids: list[str]
    total_raw: int
    total_after_dedup: int


class SmartSearch:
    def __init__(self, client: Optional[SlackClient] = None):
        self._client = client or SlackClient()
        self._search = SlackSearch(self._client)

    async def search(
        self,
        query: str,
        channels: Optional[list[str]] = None,
        max_results: int = 30,
        processed_ids: Optional[list[str]] = None,
        follow_threads: bool = True,
    ) -> SmartSearchResult:
        raw_results = await self._search.search(query, channels=channels, max_results=max_results)
        total_raw = len(raw_results)

        deduped = self._deduplicate(raw_results, processed_ids or [])
        ranked = self._rank_results(deduped, query)

        thread_contexts: dict[str, list[SlackMessage]] = {}
        if follow_threads:
            thread_contexts = await self._follow_threads(ranked[:10])

        new_ids = [msg.timestamp for msg in ranked]

        return SmartSearchResult(
            messages=ranked,
            thread_contexts=thread_contexts,
            new_processed_ids=new_ids,
            total_raw=total_raw,
            total_after_dedup=len(ranked),
        )

    def _deduplicate(
        self, messages: list[SlackMessage], processed_ids: list[str]
    ) -> list[SlackMessage]:
        seen = set(processed_ids)
        result = []
        for msg in messages:
            if msg.timestamp not in seen:
                seen.add(msg.timestamp)
                result.append(msg)
        return result

    def _rank_results(self, messages: list[SlackMessage], query: str) -> list[SlackMessage]:
        """Rank by keyword overlap, tiebreak by recency."""
        query_terms = set(self._tokenize(query))
        if not query_terms:
            return messages

        scored = []
        for msg in messages:
            msg_terms = set(self._tokenize(msg.text))
            overlap = len(query_terms & msg_terms)
            score = overlap / len(query_terms) if query_terms else 0
            scored.append((score, msg))

        scored.sort(key=lambda x: (x[0], x[1].timestamp), reverse=True)
        return [msg for _, msg in scored]

    async def _follow_threads(
        self, messages: list[SlackMessage]
    ) -> dict[str, list[SlackMessage]]:
        """Fetch thread replies for messages that are thread parents."""
        contexts: dict[str, list[SlackMessage]] = {}

        for msg in messages:
            try:
                replies = await self._client.get_thread_replies(msg.channel, msg.timestamp)
                if len(replies) > 1:
                    contexts[msg.timestamp] = [
                        SlackMessage(
                            channel=msg.channel,
                            user=r.get("user", "unknown"),
                            text=r.get("text", "")[:2000],
                            timestamp=r.get("ts", ""),
                            permalink=None,
                        )
                        for r in replies[1:]
                    ]
            except RuntimeError:
                continue

        return contexts

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

from __future__ import annotations

from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from agent_ls.config.settings import get_settings


class SlackClient:
    def __init__(self, token: Optional[str] = None):
        self._token = token or get_settings().slack.user_token
        if not self._token:
            raise ValueError(
                "Slack token not configured. Set it in ~/.agent-ls/config.toml "
                "under [slack] user_token or pass it directly."
            )
        self._client = WebClient(token=self._token)

    async def search_messages(
        self, query: str, count: int = 20, sort: str = "timestamp"
    ) -> list[dict]:
        try:
            response = self._client.search_messages(
                query=query, count=count, sort=sort
            )
            return response["messages"]["matches"]
        except SlackApiError as e:
            raise RuntimeError(f"Slack search failed: {e.response['error']}") from e

    async def post_message(self, channel: str, text: str, blocks: Optional[list] = None) -> dict:
        try:
            response = self._client.chat_postMessage(
                channel=channel, text=text, blocks=blocks
            )
            return response.data
        except SlackApiError as e:
            raise RuntimeError(f"Slack post failed: {e.response['error']}") from e

    async def get_user_profile(self) -> dict:
        try:
            response = self._client.auth_test()
            user_id = response["user_id"]
            profile = self._client.users_profile_get(user=user_id)
            return profile["profile"]
        except SlackApiError as e:
            raise RuntimeError(f"Slack profile fetch failed: {e.response['error']}") from e

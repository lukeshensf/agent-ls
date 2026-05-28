from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agent_ls.graph.state import AgentState, SlackMessage
from agent_ls.integrations.models.router import ModelRouter
from agent_ls.integrations.slack.client import SlackClient


SEARCH_QUERY_PROMPT = """Given the user's setup request, generate a Slack search query
to find relevant setup documentation and instructions.
Output ONLY the search query string, nothing else."""


async def slack_search_node(state: AgentState) -> dict:
    router = ModelRouter()
    model = router.get_model_for_task("extract_context")

    last_message = state["messages"][-1]
    response = await model.ainvoke([
        SystemMessage(content=SEARCH_QUERY_PROMPT),
        HumanMessage(content=last_message.content),
    ])

    query = response.content.strip()

    client = SlackClient()
    raw_results = await client.search_messages(query)

    slack_results = [
        SlackMessage(
            channel=msg.get("channel", {}).get("name", "unknown"),
            user=msg.get("username", "unknown"),
            text=msg.get("text", ""),
            timestamp=msg.get("ts", ""),
            permalink=msg.get("permalink"),
        )
        for msg in raw_results[:10]
    ]

    return {"slack_results": slack_results}

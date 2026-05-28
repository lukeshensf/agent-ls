from __future__ import annotations

import structlog

from langchain_core.messages import HumanMessage, SystemMessage

from agent_ls.graph.state import AgentState
from agent_ls.integrations.models.router import ModelRouter
from agent_ls.integrations.slack.search import SlackSearch

logger = structlog.get_logger()

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

    # Derive team channel if possible
    channels = None
    user_context = state.get("user_context")
    if user_context and user_context.team:
        channels = [f"{user_context.team}-eng", f"{user_context.team}-setup"]

    try:
        search = SlackSearch()
        results = await search.search(query, channels=channels, max_results=20)
    except (ValueError, RuntimeError) as e:
        logger.warning("slack_search_failed", error=str(e))
        return {"slack_results": [], "error": f"Slack search failed: {e}"}

    return {"slack_results": results}

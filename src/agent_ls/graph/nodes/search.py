from __future__ import annotations

import structlog

from langchain_core.messages import HumanMessage, SystemMessage

from agent_ls.config.settings import get_settings
from agent_ls.graph.state import AgentState
from agent_ls.graph.utils import message_content_as_text
from agent_ls.integrations.models.router import ModelRouter
from agent_ls.integrations.slack.smart_search import SmartSearch

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

    query = message_content_as_text(response.content).strip()

    channels = None
    user_context = state.get("user_context")
    if user_context and user_context.team:
        channels = [f"{user_context.team}-eng", f"{user_context.team}-setup"]

    settings = get_settings()
    processed_ids = state.get("processed_message_ids", [])

    try:
        smart_search = SmartSearch()
        result = await smart_search.search(
            query,
            channels=channels,
            max_results=30,
            processed_ids=processed_ids,
            follow_threads=settings.slack.follow_threads,
        )
    except (ValueError, RuntimeError) as e:
        logger.warning("slack_search_failed", error=str(e))
        return {"slack_results": [], "error": f"Slack search failed: {e}"}

    logger.info(
        "smart_search_complete",
        raw=result.total_raw,
        after_dedup=result.total_after_dedup,
        threads_followed=len(result.thread_contexts),
    )

    updated_ids = processed_ids + result.new_processed_ids
    return {"slack_results": result.messages, "processed_message_ids": updated_ids}

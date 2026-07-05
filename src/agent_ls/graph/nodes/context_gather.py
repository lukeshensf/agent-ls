from __future__ import annotations

import structlog

from langchain_core.messages import HumanMessage, SystemMessage

from agent_ls.graph.state import AgentState, UserContext
from agent_ls.graph.utils import message_content_as_text
from agent_ls.integrations.models.router import ModelRouter
from agent_ls.integrations.slack.client import SlackClient

logger = structlog.get_logger()

CONTEXT_EXTRACT_PROMPT = """Extract user context from the following Slack profile data.
Output ONLY a JSON object with these fields:
- "team": the team name (or null if unclear)
- "role": their role/title (or null if unclear)
- "tech_stack": list of technologies mentioned (empty list if none)

Example: {"team": "payments", "role": "backend engineer", "tech_stack": ["java", "kotlin"]}"""


async def context_gather_node(state: AgentState) -> dict:
    try:
        client = SlackClient()
        profile = await client.get_user_profile()
    except (ValueError, RuntimeError) as e:
        logger.info("slack_profile_unavailable", reason=str(e))
        return {"user_context": UserContext()}

    profile_text = f"Title: {profile.get('title', '')}\n"
    profile_text += f"Display name: {profile.get('display_name', '')}\n"
    profile_text += f"Status: {profile.get('status_text', '')}\n"

    router = ModelRouter()
    model = router.get_model_for_task("extract_context")

    try:
        response = await model.ainvoke([
            SystemMessage(content=CONTEXT_EXTRACT_PROMPT),
            HumanMessage(content=profile_text),
        ])

        import json

        data = json.loads(message_content_as_text(response.content))
        return {
            "user_context": UserContext(
                team=data.get("team"),
                role=data.get("role"),
                tech_stack=data.get("tech_stack", []),
            )
        }
    except Exception as e:
        logger.warning("context_extraction_failed", error=str(e))
        return {"user_context": UserContext()}

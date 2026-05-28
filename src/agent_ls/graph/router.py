from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agent_ls.graph.state import AgentState
from agent_ls.integrations.models.router import ModelRouter


ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a developer setup assistant.
Classify the user's message into exactly one of these intents:
- setup: User wants to install software, configure tools, or set up their dev environment
- search: User wants to find information in Slack or documentation
- share: User wants to share a document to Slack
- update_kb: User wants to update or refresh the knowledge base
- general: General question or conversation

Respond with ONLY the intent name, nothing else."""


async def router_node(state: AgentState) -> dict:
    router = ModelRouter()
    model = router.get_model_for_task("classify_intent")

    last_message = state["messages"][-1]
    response = await model.ainvoke([
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=last_message.content),
    ])

    intent = response.content.strip().lower()
    valid_intents = {"setup", "search", "share", "update_kb", "general"}
    if intent not in valid_intents:
        intent = "general"

    return {"intent": intent}

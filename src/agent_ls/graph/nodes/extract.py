from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from agent_ls.graph.state import AgentState, PlanStep
from agent_ls.integrations.models.router import ModelRouter


EXTRACT_SYSTEM_PROMPT = """You are parsing Slack messages to extract actionable developer setup steps.
Given the messages below, extract a JSON array of steps that a developer should follow.

Each step has:
- "description": short human-readable description of what to do
- "command": the exact shell command to run (or null if it's a manual step)

Only include steps that are clearly actionable. Ignore chatter, questions, and off-topic messages.
Output ONLY the JSON array, nothing else.

Example:
[
  {"description": "Install Node.js via nvm", "command": "nvm install 20"},
  {"description": "Clone the repo", "command": "git clone git@github.com:team/repo.git"},
  {"description": "Request access to staging VPN", "command": null}
]"""


async def extract_node(state: AgentState) -> dict:
    slack_results = _deduplicate(state.get("slack_results", []))
    if not slack_results:
        return {"plan": [], "current_step": 0}

    messages_text = "\n\n".join(
        f"[{msg.channel}] {msg.user}: {msg.text[:500]}" for msg in slack_results[:10]
    )

    router = ModelRouter()
    model = router.get_model_for_task("extract_context")

    response = await model.ainvoke([
        SystemMessage(content=EXTRACT_SYSTEM_PROMPT),
        HumanMessage(content=messages_text),
    ])

    try:
        steps_data = json.loads(response.content)
        plan = [
            PlanStep(description=s["description"], command=s.get("command"))
            for s in steps_data
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        plan = []

    urls = _extract_urls(messages_text)

    return {"plan": plan, "current_step": 0, "extracted_urls": urls}


def _extract_urls(text: str) -> list[str]:
    import re

    url_pattern = re.compile(r"https?://[^\s<>\"')\]]+")
    return list(set(url_pattern.findall(text)))


def _deduplicate(messages: list, threshold: float = 0.8) -> list:
    """Remove near-duplicate messages using Jaccard similarity on word sets."""
    if not messages:
        return []

    unique = [messages[0]]
    for msg in messages[1:]:
        words = set(msg.text.lower().split())
        is_dup = False
        for existing in unique:
            existing_words = set(existing.text.lower().split())
            if not words or not existing_words:
                continue
            intersection = words & existing_words
            union = words | existing_words
            similarity = len(intersection) / len(union)
            if similarity >= threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(msg)
    return unique

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from agent_ls.graph.state import AgentState, PlanStep
from agent_ls.graph.utils import message_content_as_text
from agent_ls.integrations.models.router import ModelRouter


PLAN_SYSTEM_PROMPT = """You are a developer environment setup planner for macOS.
Given the user's request, generate a step-by-step plan of shell commands to execute.

Output a JSON array of steps. Each step has:
- "description": short human-readable description
- "command": the exact shell command to run (or null if it's a manual step)

Only include commands that are safe and standard for macOS development setup.
Prefer Homebrew for package installation.

Example output:
[
  {"description": "Install Homebrew", "command": "/bin/bash -c \\"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\\""},
  {"description": "Install Python 3.12", "command": "brew install python@3.12"},
  {"description": "Verify Python installation", "command": "python3 --version"}
]"""


async def plan_node(state: AgentState) -> dict:
    router = ModelRouter()
    model = router.get_model_for_task("generate_plan")

    last_message = state["messages"][-1]
    context_parts = []
    if state.get("user_context"):
        ctx = state["user_context"]
        if ctx.team:
            context_parts.append(f"Team: {ctx.team}")
        if ctx.tech_stack:
            context_parts.append(f"Tech stack: {', '.join(ctx.tech_stack)}")

    user_msg = message_content_as_text(last_message.content)
    if context_parts:
        user_msg += f"\n\nContext: {'; '.join(context_parts)}"

    response = await model.ainvoke([
        SystemMessage(content=PLAN_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ])

    try:
        steps_data = json.loads(message_content_as_text(response.content))
        plan = [
            PlanStep(description=s["description"], command=s.get("command"))
            for s in steps_data
        ]
    except (json.JSONDecodeError, KeyError):
        plan = [PlanStep(description="Parse plan from response", command=None)]

    return {"plan": plan, "current_step": 0}

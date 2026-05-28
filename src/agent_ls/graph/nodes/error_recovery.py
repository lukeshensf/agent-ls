from __future__ import annotations

import json

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agent_ls.graph.state import AgentState, PlanStep
from agent_ls.integrations.models.router import ModelRouter

logger = structlog.get_logger()

ERROR_RECOVERY_PROMPT = """A developer environment setup command failed. Analyze the error and suggest a fix.

Failed command: {command}
Exit code: {exit_code}
Stderr: {stderr}
Stdout: {stdout}

Respond with a JSON object:
{{"description": "short description of the fix", "command": "the fix command to run"}}

If no fix is possible, respond with: {{"description": "Skip - no fix available", "command": null}}"""


async def error_recovery_node(state: AgentState) -> dict:
    """Analyze a failed command and propose a recovery step."""
    plan = list(state["plan"])
    current_step = state["current_step"]
    execution_log = state.get("execution_log", [])

    if not execution_log:
        return {}

    last_result = execution_log[-1]
    if last_result.exit_code == 0:
        return {}

    router = ModelRouter()
    model = router.get_model_for_task("debug_error")

    prompt = ERROR_RECOVERY_PROMPT.format(
        command=last_result.command,
        exit_code=last_result.exit_code,
        stderr=last_result.stderr[:1000],
        stdout=last_result.stdout[:500],
    )

    try:
        response = await model.ainvoke([
            SystemMessage(content="You are a macOS developer environment troubleshooter."),
            HumanMessage(content=prompt),
        ])

        data = json.loads(response.content)
        recovery_step = PlanStep(
            description=f"[Recovery] {data['description']}",
            command=data.get("command"),
        )

        plan.insert(current_step, recovery_step)
        logger.info("error_recovery_proposed", fix=data["description"])

        return {"plan": plan}
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning("error_recovery_failed", error=str(e))
        return {}

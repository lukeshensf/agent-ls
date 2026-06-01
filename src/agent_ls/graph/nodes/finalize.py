from __future__ import annotations

from agent_ls.graph.state import AgentState


async def finalize_node(state: AgentState) -> dict:
    """Determine whether the run succeeded — gates git push in obsidian_write."""
    if state.get("error"):
        return {"run_success": False}

    plan = state.get("plan", [])
    if not plan:
        return {"run_success": False}

    has_success = any(step.status == "done" for step in plan)
    return {"run_success": has_success}

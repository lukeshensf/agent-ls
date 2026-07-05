from __future__ import annotations

from langchain_core.messages import AIMessage

from agent_ls.graph.state import AgentState


async def summarize_node(state: AgentState) -> dict:
    plan = state["plan"]

    done = sum(1 for s in plan if s.status == "done")
    failed = sum(1 for s in plan if s.status == "failed")
    skipped = sum(1 for s in plan if s.status == "skipped")
    total = len(plan)

    lines = [f"Setup complete: {done}/{total} steps succeeded."]
    if failed:
        lines.append(f"{failed} step(s) failed.")
    if skipped:
        lines.append(f"{skipped} step(s) skipped.")

    for step in plan:
        icon = {"done": "[x]", "failed": "[!]", "skipped": "[-]"}.get(
            step.status, "[ ]"
        )
        time_str = f" ({step.duration_ms}ms)" if step.duration_ms else ""
        lines.append(f"  {icon} {step.description}{time_str}")

    summary = "\n".join(lines)
    return {"messages": [AIMessage(content=summary)]}

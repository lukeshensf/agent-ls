from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent_ls.graph.nodes.execute import execute_after_approval, execute_node
from agent_ls.graph.nodes.plan import plan_node
from agent_ls.graph.nodes.summarize import summarize_node
from agent_ls.graph.router import router_node
from agent_ls.graph.state import AgentState


def _should_continue_execution(state: AgentState) -> str:
    if state.get("approval_pending"):
        return "await_approval"
    if state.get("error"):
        return "summarize"
    if state["current_step"] >= len(state["plan"]):
        return "summarize"
    return "execute"


def _route_intent(state: AgentState) -> str:
    intent = state.get("intent", "general")
    if intent == "setup":
        return "plan"
    # For POC, route everything through plan
    return "plan"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("execute_after_approval", execute_after_approval)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges("router", _route_intent, {"plan": "plan"})
    graph.add_edge("plan", "execute")
    graph.add_conditional_edges(
        "execute",
        _should_continue_execution,
        {
            "execute": "execute",
            "await_approval": END,
            "summarize": "summarize",
        },
    )
    graph.add_conditional_edges(
        "execute_after_approval",
        _should_continue_execution,
        {
            "execute": "execute",
            "await_approval": END,
            "summarize": "summarize",
        },
    )
    graph.add_edge("summarize", END)

    return graph.compile()

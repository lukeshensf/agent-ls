from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent_ls.graph.nodes.context_gather import context_gather_node
from agent_ls.graph.nodes.execute import execute_after_approval, execute_node
from agent_ls.graph.nodes.extract import extract_node
from agent_ls.graph.nodes.obsidian import obsidian_read_node, obsidian_write_node
from agent_ls.graph.nodes.plan import plan_node
from agent_ls.graph.nodes.search import slack_search_node
from agent_ls.graph.nodes.share import slack_share_node
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
    if intent in {"setup", "general"}:
        return "plan"
    if intent == "search":
        return "slack_search"
    if intent == "share":
        return "obsidian_read"
    if intent == "update_kb":
        return "kb_freshness"
    return "plan"


def _after_summarize(state: AgentState) -> str:
    if state.get("intent") == "setup":
        return "obsidian_write"
    return "end"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("context_gather", context_gather_node)
    graph.add_node("router", router_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("execute_after_approval", execute_after_approval)
    graph.add_node("summarize", summarize_node)
    graph.add_node("obsidian_write", obsidian_write_node)
    graph.add_node("obsidian_read", obsidian_read_node)
    graph.add_node("slack_search", slack_search_node)
    graph.add_node("extract", extract_node)
    graph.add_node("slack_share", slack_share_node)
    graph.add_node("kb_freshness", _kb_freshness_placeholder)

    graph.set_entry_point("context_gather")

    graph.add_edge("context_gather", "router")

    graph.add_conditional_edges(
        "router",
        _route_intent,
        {
            "plan": "plan",
            "slack_search": "slack_search",
            "obsidian_read": "obsidian_read",
            "kb_freshness": "kb_freshness",
        },
    )

    # Setup/general branch: plan -> execute loop -> summarize -> (optionally) obsidian_write
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

    graph.add_conditional_edges(
        "summarize",
        _after_summarize,
        {"obsidian_write": "obsidian_write", "end": END},
    )
    graph.add_edge("obsidian_write", END)

    # Search branch: slack_search -> extract -> execute loop
    graph.add_edge("slack_search", "extract")
    graph.add_edge("extract", "execute")

    # Share branch: obsidian_read -> slack_share -> END
    graph.add_edge("obsidian_read", "slack_share")
    graph.add_edge("slack_share", END)

    # Update KB branch: placeholder -> END
    graph.add_edge("kb_freshness", END)

    return graph.compile()


async def _kb_freshness_placeholder(state: AgentState) -> dict:
    return {}

import pytest

from agent_ls.graph.builder import _route_intent, _should_continue_execution, _after_summarize
from agent_ls.graph.state import PlanStep


def _make_state(intent="general", plan=None, current_step=0, approval_pending=None, error=None):
    return {
        "intent": intent,
        "plan": plan or [],
        "current_step": current_step,
        "approval_pending": approval_pending,
        "error": error,
    }


class TestRouteIntent:
    def test_setup_routes_to_plan(self):
        assert _route_intent(_make_state(intent="setup")) == "plan"

    def test_general_routes_to_plan(self):
        assert _route_intent(_make_state(intent="general")) == "plan"

    def test_search_routes_to_slack_search(self):
        assert _route_intent(_make_state(intent="search")) == "slack_search"

    def test_share_routes_to_obsidian_read(self):
        assert _route_intent(_make_state(intent="share")) == "obsidian_read"

    def test_update_kb_routes_to_kb_freshness(self):
        assert _route_intent(_make_state(intent="update_kb")) == "kb_freshness"

    def test_unknown_intent_defaults_to_plan(self):
        assert _route_intent(_make_state(intent="unknown")) == "plan"


class TestShouldContinueExecution:
    def test_approval_pending_awaits(self):
        state = _make_state(approval_pending="sudo apt install foo")
        assert _should_continue_execution(state) == "await_approval"

    def test_error_goes_to_summarize(self):
        state = _make_state(error="something failed")
        assert _should_continue_execution(state) == "summarize"

    def test_all_steps_done_goes_to_summarize(self):
        steps = [PlanStep(description="s1", command="echo 1", status="done")]
        state = _make_state(plan=steps, current_step=1)
        assert _should_continue_execution(state) == "summarize"

    def test_more_steps_continues_execution(self):
        steps = [
            PlanStep(description="s1", command="echo 1", status="done"),
            PlanStep(description="s2", command="echo 2"),
        ]
        state = _make_state(plan=steps, current_step=1)
        assert _should_continue_execution(state) == "execute"


class TestAfterSummarize:
    def test_setup_intent_goes_to_finalize(self):
        state = _make_state(intent="setup")
        assert _after_summarize(state) == "finalize"

    def test_search_intent_ends(self):
        state = _make_state(intent="search")
        assert _after_summarize(state) == "end"

    def test_general_intent_ends(self):
        state = _make_state(intent="general")
        assert _after_summarize(state) == "end"

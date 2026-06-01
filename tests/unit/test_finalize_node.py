import pytest

from agent_ls.graph.nodes.finalize import finalize_node
from agent_ls.graph.state import PlanStep


@pytest.mark.asyncio
async def test_success_when_steps_done():
    state = {
        "plan": [
            PlanStep(description="step1", status="done"),
            PlanStep(description="step2", status="done"),
        ],
        "error": None,
    }
    result = await finalize_node(state)
    assert result["run_success"] is True


@pytest.mark.asyncio
async def test_failure_when_error_present():
    state = {
        "plan": [PlanStep(description="step1", status="done")],
        "error": "something broke",
    }
    result = await finalize_node(state)
    assert result["run_success"] is False


@pytest.mark.asyncio
async def test_failure_when_no_steps_done():
    state = {
        "plan": [
            PlanStep(description="step1", status="failed"),
            PlanStep(description="step2", status="skipped"),
        ],
        "error": None,
    }
    result = await finalize_node(state)
    assert result["run_success"] is False


@pytest.mark.asyncio
async def test_failure_when_no_plan():
    state = {"plan": [], "error": None}
    result = await finalize_node(state)
    assert result["run_success"] is False


@pytest.mark.asyncio
async def test_partial_success():
    state = {
        "plan": [
            PlanStep(description="step1", status="done"),
            PlanStep(description="step2", status="failed"),
        ],
        "error": None,
    }
    result = await finalize_node(state)
    assert result["run_success"] is True

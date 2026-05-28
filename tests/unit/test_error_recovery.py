from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.graph.nodes.error_recovery import error_recovery_node
from agent_ls.graph.state import ExecutionResult, PlanStep, UserContext


@pytest.fixture
def failed_state():
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="setup python")],
        "user_context": UserContext(team="eng"),
        "intent": "setup",
        "plan": [
            PlanStep(description="Install Python", command="brew install python@3.12", status="failed"),
            PlanStep(description="Verify", command="python3 --version"),
        ],
        "current_step": 1,
        "execution_log": [
            ExecutionResult(
                command="brew install python@3.12",
                exit_code=1,
                stdout="",
                stderr="Error: python@3.12 is already installed",
                duration_ms=500,
            )
        ],
        "approval_pending": None,
        "obsidian_docs": [],
        "slack_results": [],
        "error": None,
        "share_channel": None,
        "share_result": None,
        "extracted_urls": [],
    }


@pytest.mark.asyncio
async def test_error_recovery_proposes_fix(failed_state):
    model_response = MagicMock()
    model_response.content = '{"description": "Reinstall Python", "command": "brew reinstall python@3.12"}'

    with patch("agent_ls.graph.nodes.error_recovery.ModelRouter") as mock_router_cls:
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        result = await error_recovery_node(failed_state)

    assert "plan" in result
    assert len(result["plan"]) == 3
    recovery_step = result["plan"][1]
    assert "[Recovery]" in recovery_step.description
    assert recovery_step.command == "brew reinstall python@3.12"


@pytest.mark.asyncio
async def test_error_recovery_no_execution_log():
    from langchain_core.messages import HumanMessage

    state = {
        "messages": [HumanMessage(content="test")],
        "user_context": UserContext(),
        "intent": "setup",
        "plan": [PlanStep(description="test", command="echo hi")],
        "current_step": 0,
        "execution_log": [],
        "approval_pending": None,
        "obsidian_docs": [],
        "slack_results": [],
        "error": None,
        "share_channel": None,
        "share_result": None,
        "extracted_urls": [],
    }
    result = await error_recovery_node(state)
    assert result == {}


@pytest.mark.asyncio
async def test_error_recovery_last_command_succeeded(failed_state):
    failed_state["execution_log"] = [
        ExecutionResult(command="echo hi", exit_code=0, stdout="hi", stderr="", duration_ms=10)
    ]
    result = await error_recovery_node(failed_state)
    assert result == {}


@pytest.mark.asyncio
async def test_error_recovery_model_failure(failed_state):
    model_response = MagicMock()
    model_response.content = "not json"

    with patch("agent_ls.graph.nodes.error_recovery.ModelRouter") as mock_router_cls:
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        result = await error_recovery_node(failed_state)

    assert result == {}

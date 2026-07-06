"""Tests for the command-execution node (`_execute_command`).

Focus of PLAN 3.1: the audit entry for an executed command must ALWAYS carry a
`duration_ms`, sourced consistently from the executor's own measurement
(`CommandResult.duration_ms`) rather than a separately-tracked timer. These tests
lock in that contract for both the success and the timeout outcome so a future
refactor cannot silently drop the duration or reintroduce a second, divergent
timer.
"""
import json
from unittest.mock import patch

import pytest

from agent_ls.graph.nodes import execute as execute_mod
from agent_ls.graph.nodes.execute import _execute_command
from agent_ls.graph.state import PlanStep
from agent_ls.integrations.computer_use.executor import CommandResult


class _FakeExecutor:
    """Stand-in for CommandExecutor returning a canned result (no subprocess)."""

    def __init__(self, result: CommandResult):
        self._result = result

    async def execute(self, command: str, cwd=None) -> CommandResult:
        return self._result


def _state(command: str = "echo hi") -> dict:
    return {
        "plan": [PlanStep(description="test step", command=command)],
        "current_step": 0,
        "execution_log": [],
    }


def _read_single_audit_entry(audit_path) -> dict:
    lines = [ln for ln in audit_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected exactly one audit entry, got {len(lines)}"
    return json.loads(lines[0])


async def _run(state: dict, command: str, result: CommandResult, tmp_path) -> dict:
    audit_path = tmp_path / "audit.jsonl"
    with (
        patch("agent_ls.security.audit.get_settings") as mock_settings,
        patch.object(execute_mod, "CommandExecutor", return_value=_FakeExecutor(result)),
    ):
        mock_settings.return_value.audit_log_path = str(audit_path)
        node_result = await _execute_command(state, command)
    node_result["_audit_entry"] = _read_single_audit_entry(audit_path)
    return node_result


@pytest.mark.asyncio
async def test_audit_entry_carries_duration_on_success(tmp_path):
    """A successful command's audit entry carries the executor's duration_ms."""
    result = CommandResult(
        command="echo hi",
        exit_code=0,
        stdout="hi\n",
        stderr="",
        duration_ms=123,
    )
    state = _state("echo hi")

    node_result = await _run(state, "echo hi", result, tmp_path)

    entry = node_result["_audit_entry"]
    assert entry["duration_ms"] == 123
    assert isinstance(entry["duration_ms"], int)
    assert entry["executed"] is True
    assert entry["exit_code"] == 0

    # The single executor measurement flows to the step and the execution log too.
    step = state["plan"][0]
    assert step.status == "done"
    assert step.duration_ms == 123
    assert node_result["execution_log"][-1].duration_ms == 123


@pytest.mark.asyncio
async def test_audit_entry_carries_duration_on_timeout(tmp_path):
    """Even a timed-out command (exit_code=-1) still records a duration_ms."""
    result = CommandResult(
        command="sleep 10",
        exit_code=-1,
        stdout="",
        stderr="Command timed out after 300s",
        duration_ms=456,
        timed_out=True,
    )
    state = _state("sleep 10")

    node_result = await _run(state, "sleep 10", result, tmp_path)

    entry = node_result["_audit_entry"]
    assert entry["duration_ms"] == 456
    assert isinstance(entry["duration_ms"], int)
    assert entry["exit_code"] == -1

    step = state["plan"][0]
    assert step.status == "failed"
    assert step.duration_ms == 456
    assert node_result["execution_log"][-1].duration_ms == 456

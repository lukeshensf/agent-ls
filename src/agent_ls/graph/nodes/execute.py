from __future__ import annotations

from agent_ls.graph.state import AgentState, ExecutionResult
from agent_ls.integrations.computer_use.executor import CommandExecutor
from agent_ls.security.allowlist import AllowlistChecker, SecurityClassification
from agent_ls.security.audit import AuditLogger, ExecutionTimer


async def execute_node(state: AgentState) -> dict:
    plan = state["plan"]
    current_step = state["current_step"]

    if current_step >= len(plan):
        return {"current_step": current_step}

    step = plan[current_step]
    if not step.command:
        step.status = "skipped"
        return {"current_step": current_step + 1, "plan": plan}

    checker = AllowlistChecker()
    result = checker.classify(step.command)

    if result.classification == SecurityClassification.BLOCKED:
        audit = AuditLogger()
        audit.log_command(
            step.command, result.classification, executed=False, reason=result.reason
        )
        step.status = "failed"
        return {
            "current_step": current_step + 1,
            "plan": plan,
            "error": f"Blocked: {result.reason}",
        }

    if result.classification == SecurityClassification.NEEDS_APPROVAL:
        return {"approval_pending": step.command}

    return await _execute_command(state, step.command)


async def execute_after_approval(state: AgentState) -> dict:
    """Called after user approves a command."""
    command = state["approval_pending"]
    if not command:
        return {"approval_pending": None}
    return await _execute_command(state, command)


async def _execute_command(state: AgentState, command: str) -> dict:
    plan = state["plan"]
    current_step = state["current_step"]
    step = plan[current_step]
    execution_log = list(state.get("execution_log", []))

    executor = CommandExecutor()
    audit = AuditLogger()

    step.status = "running"

    with ExecutionTimer() as _:
        cmd_result = await executor.execute(command)

    step.status = "done" if cmd_result.exit_code == 0 else "failed"
    step.exit_code = cmd_result.exit_code
    step.duration_ms = cmd_result.duration_ms

    audit.log_command(
        command,
        SecurityClassification.AUTO_APPROVE,
        executed=True,
        exit_code=cmd_result.exit_code,
        duration_ms=cmd_result.duration_ms,
    )

    execution_log.append(
        ExecutionResult(
            command=command,
            exit_code=cmd_result.exit_code,
            stdout=cmd_result.stdout,
            stderr=cmd_result.stderr,
            duration_ms=cmd_result.duration_ms,
        )
    )

    return {
        "current_step": current_step + 1,
        "plan": plan,
        "execution_log": execution_log,
        "approval_pending": None,
    }

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from agent_ls.config.settings import get_settings
from agent_ls.graph.state import AgentState
from agent_ls.integrations.obsidian.git_sync import GitSync
from agent_ls.integrations.obsidian.templates import DocTemplate
from agent_ls.integrations.obsidian.vault import ObsidianVault

logger = structlog.get_logger()


async def obsidian_write_node(state: AgentState) -> dict:
    vault = ObsidianVault()
    plan = state.get("plan", [])
    user_context = state.get("user_context")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    team = user_context.team if user_context else "general"
    filename = f"logs/{team}-setup-{timestamp}.md"

    steps_lines = []
    for step in plan:
        icon = {"done": "- [x]", "failed": "- [!]", "skipped": "- [-]"}.get(
            step.status, "- [ ]"
        )
        line = f"{icon} {step.description}"
        if step.command:
            line += f" (`{step.command}`)"
        if step.duration_ms:
            line += f" — {step.duration_ms}ms"
        steps_lines.append(line)

    output_lines = []
    for entry in state.get("execution_log", []):
        output_lines.append(f"### `{entry.command}`")
        output_lines.append(f"Exit code: {entry.exit_code}")
        if entry.stdout.strip():
            output_lines.append(f"```\n{entry.stdout[:500]}\n```")
        output_lines.append("")

    done = sum(1 for s in plan if s.status == "done")
    total = len(plan)

    context = {
        "title": f"Setup Log — {team} — {timestamp}",
        "team": team,
        "tags": ["setup-log", "auto-generated"],
        "summary": f"{done}/{total} steps completed successfully.",
        "steps": "\n".join(steps_lines) if steps_lines else "No steps executed.",
        "output": "\n".join(output_lines) if output_lines else "No output captured.",
    }

    path = vault.write_with_template(filename, DocTemplate.DAILY_LOG, context)

    settings = get_settings()
    if settings.obsidian.git_auto_sync:
        try:
            git_sync = GitSync(vault.root)
            git_sync.commit_file(path, f"agent-ls: setup log {timestamp}")
        except (ValueError, Exception) as e:
            logger.warning("git_sync_failed", error=str(e))

    obsidian_docs = list(state.get("obsidian_docs", []))
    obsidian_docs.append(str(path))
    return {"obsidian_docs": obsidian_docs}


async def obsidian_read_node(state: AgentState) -> dict:
    vault = ObsidianVault()
    user_context = state.get("user_context")
    team = user_context.team if user_context else "general"

    settings = get_settings()
    if settings.obsidian.git_auto_sync:
        try:
            git_sync = GitSync(vault.root)
            git_sync.pull()
        except (ValueError, Exception) as e:
            logger.warning("git_pull_failed", error=str(e))

    docs = vault.list_docs(f"teams/{team}")
    return {"obsidian_docs": docs}

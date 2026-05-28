from __future__ import annotations

from datetime import datetime, timezone

from agent_ls.graph.state import AgentState
from agent_ls.integrations.obsidian.vault import ObsidianVault


async def obsidian_write_node(state: AgentState) -> dict:
    vault = ObsidianVault()
    plan = state.get("plan", [])
    execution_log = state.get("execution_log", [])
    user_context = state.get("user_context")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    team = user_context.team if user_context else "general"
    filename = f"logs/{team}-setup-{timestamp}.md"

    lines = [
        f"# Setup Log - {timestamp}",
        "",
        f"**Team**: {team}",
        "",
        "## Steps Executed",
        "",
    ]

    for step in plan:
        icon = {"done": "✓", "failed": "✗", "skipped": "-"}.get(step.status, "?")
        lines.append(f"- [{icon}] {step.description}")
        if step.command:
            lines.append(f"  - Command: `{step.command}`")
        if step.duration_ms:
            lines.append(f"  - Duration: {step.duration_ms}ms")

    if execution_log:
        lines.extend(["", "## Command Output", ""])
        for entry in execution_log:
            lines.append(f"### `{entry.command}`")
            lines.append(f"Exit code: {entry.exit_code}")
            if entry.stdout.strip():
                lines.append(f"```\n{entry.stdout[:500]}\n```")

    content = "\n".join(lines)
    path = vault.write(filename, content)

    obsidian_docs = list(state.get("obsidian_docs", []))
    obsidian_docs.append(str(path))
    return {"obsidian_docs": obsidian_docs}


async def obsidian_read_node(state: AgentState) -> dict:
    vault = ObsidianVault()
    user_context = state.get("user_context")
    team = user_context.team if user_context else "general"

    docs = vault.list_docs(f"teams/{team}")
    contents = []
    for doc_path in docs[:5]:
        try:
            contents.append(vault.read(doc_path))
        except FileNotFoundError:
            continue

    return {"obsidian_docs": docs}

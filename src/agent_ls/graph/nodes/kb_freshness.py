from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

from agent_ls.config.settings import get_settings
from agent_ls.graph.state import AgentState
from agent_ls.integrations.computer_use.executor import CommandExecutor
from agent_ls.integrations.obsidian.vault import ObsidianVault

logger = structlog.get_logger()


@dataclass
class FreshnessCheck:
    doc_path: str
    commands_tested: list[tuple[str, bool]] = field(default_factory=list)
    urls_checked: list[tuple[str, int]] = field(default_factory=list)
    is_stale: bool = False


_CODE_BLOCK_PATTERN = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_INLINE_CMD_PATTERN = re.compile(r"`([^`]+)`")
_URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+")
_COMMAND_PREFIXES = ("brew ", "pip ", "npm ", "git ", "curl ", "apt ", "cargo ", "nvm ", "which ")


async def kb_freshness_node(state: AgentState) -> dict:
    """Check knowledge base docs for broken commands and URLs."""
    vault = ObsidianVault()
    user_context = state.get("user_context")
    team = user_context.team if user_context else "general"

    docs = vault.list_docs(f"teams/{team}")
    if not docs:
        docs = vault.list_docs("logs")

    freshness_results = []
    executor = CommandExecutor(timeout_seconds=10)

    for doc_path in docs[:10]:
        try:
            content = vault.read(doc_path)
        except FileNotFoundError:
            continue

        check = FreshnessCheck(doc_path=doc_path)

        commands = _extract_commands(content)
        for cmd in commands[:5]:
            test_cmd = _make_test_command(cmd)
            if test_cmd:
                result = await executor.execute(test_cmd)
                works = result.exit_code == 0
                check.commands_tested.append((cmd, works))
                if not works:
                    check.is_stale = True

        urls = _URL_PATTERN.findall(content)
        for url in urls[:5]:
            status = await _check_url(url)
            check.urls_checked.append((url, status))
            if status >= 400:
                check.is_stale = True

        freshness_results.append(check)

    stale_docs = [c.doc_path for c in freshness_results if c.is_stale]
    logger.info("kb_freshness_complete", total=len(freshness_results), stale=len(stale_docs))

    return {"obsidian_docs": stale_docs}


def _extract_commands(content: str) -> list[str]:
    """Extract shell commands from code blocks and inline code."""
    commands = []

    for block_match in _CODE_BLOCK_PATTERN.finditer(content):
        block = block_match.group(1)
        for line in block.strip().split("\n"):
            line = line.strip().lstrip("$ ")
            if any(line.startswith(prefix) for prefix in _COMMAND_PREFIXES):
                commands.append(line)

    for inline_match in _INLINE_CMD_PATTERN.finditer(content):
        cmd = inline_match.group(1)
        if any(cmd.startswith(prefix) for prefix in _COMMAND_PREFIXES):
            commands.append(cmd)

    return commands


def _make_test_command(cmd: str) -> str | None:
    """Convert a command to a safe test version."""
    first_word = cmd.split()[0] if cmd.split() else ""

    if first_word in ("brew", "pip", "pip3", "npm", "cargo", "gem"):
        return f"which {first_word}"
    if first_word == "git":
        return "git --version"
    if first_word == "which":
        return cmd
    if first_word in ("nvm", "pyenv", "rustup"):
        return f"which {first_word}"

    return None


async def _check_url(url: str) -> int:
    """Check URL accessibility, return HTTP status code."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.head(url)
            return response.status_code
    except Exception:
        return 999

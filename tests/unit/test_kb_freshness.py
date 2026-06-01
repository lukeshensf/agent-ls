from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.graph.nodes.kb_freshness import (
    _extract_commands,
    _make_test_command,
    kb_freshness_node,
)
from agent_ls.graph.state import UserContext


@pytest.fixture
def base_state():
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="update knowledge base")],
        "user_context": UserContext(team="eng"),
        "intent": "update_kb",
        "plan": [],
        "current_step": 0,
        "execution_log": [],
        "approval_pending": None,
        "obsidian_docs": [],
        "slack_results": [],
        "error": None,
        "share_channel": None,
        "share_result": None,
        "extracted_urls": [],
        "processed_message_ids": [],
        "run_success": False,
    }


class TestExtractCommands:
    def test_from_code_block(self):
        content = "```bash\nbrew install python\npip install flask\n```"
        commands = _extract_commands(content)
        assert "brew install python" in commands
        assert "pip install flask" in commands

    def test_from_inline_code(self):
        content = "Run `brew install node` to install Node.js"
        commands = _extract_commands(content)
        assert "brew install node" in commands

    def test_ignores_non_commands(self):
        content = "The `variable_name` is important\n```\nsome output text\n```"
        commands = _extract_commands(content)
        assert commands == []

    def test_strips_dollar_prefix(self):
        content = "```\n$ brew install git\n```"
        commands = _extract_commands(content)
        assert "brew install git" in commands


class TestMakeTestCommand:
    def test_brew(self):
        assert _make_test_command("brew install python") == "which brew"

    def test_pip(self):
        assert _make_test_command("pip install flask") == "which pip"

    def test_git(self):
        assert _make_test_command("git clone http://x") == "git --version"

    def test_which(self):
        assert _make_test_command("which python") == "which python"

    def test_unknown_returns_none(self):
        assert _make_test_command("echo hello") is None


@pytest.mark.asyncio
async def test_kb_freshness_detects_stale_doc(base_state):
    doc_content = "# Setup\n\nRun `brew install nonexistent-tool-xyz`"

    with (
        patch("agent_ls.graph.nodes.kb_freshness.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.kb_freshness.CommandExecutor") as mock_exec_cls,
        patch("agent_ls.graph.nodes.kb_freshness.get_settings") as mock_settings,
        patch("agent_ls.graph.nodes.kb_freshness.GitSync") as mock_git_cls,
        patch("agent_ls.graph.nodes.kb_freshness.TeamKnowledge") as mock_tk_cls,
        patch("agent_ls.graph.nodes.kb_freshness._check_url", new_callable=lambda: AsyncMock),
    ):
        mock_vault = MagicMock()
        mock_vault.list_docs.return_value = ["teams/eng/setup.md"]
        mock_vault.read.return_value = doc_content
        mock_vault.root = "/tmp/vault"
        mock_vault_cls.return_value = mock_vault

        mock_settings.return_value.obsidian.freshness_fallback = False

        mock_executor = MagicMock()
        failed_result = MagicMock()
        failed_result.exit_code = 1
        mock_executor.execute = AsyncMock(return_value=failed_result)
        mock_exec_cls.return_value = mock_executor

        result = await kb_freshness_node(base_state)

    assert "teams/eng/setup.md" in result["obsidian_docs"]


@pytest.mark.asyncio
async def test_kb_freshness_healthy_doc(base_state):
    doc_content = "# Setup\n\nRun `brew install python`"

    with (
        patch("agent_ls.graph.nodes.kb_freshness.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.kb_freshness.CommandExecutor") as mock_exec_cls,
        patch("agent_ls.graph.nodes.kb_freshness.get_settings") as mock_settings,
        patch("agent_ls.graph.nodes.kb_freshness._check_url", new_callable=lambda: AsyncMock),
    ):
        mock_vault = MagicMock()
        mock_vault.list_docs.return_value = ["teams/eng/setup.md"]
        mock_vault.read.return_value = doc_content
        mock_vault_cls.return_value = mock_vault

        mock_settings.return_value.obsidian.freshness_fallback = True

        mock_executor = MagicMock()
        ok_result = MagicMock()
        ok_result.exit_code = 0
        mock_executor.execute = AsyncMock(return_value=ok_result)
        mock_exec_cls.return_value = mock_executor

        result = await kb_freshness_node(base_state)

    assert result["obsidian_docs"] == []


@pytest.mark.asyncio
async def test_kb_freshness_stale_url(base_state):
    doc_content = "Visit https://broken-link.example.com/setup for details"

    with (
        patch("agent_ls.graph.nodes.kb_freshness.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.kb_freshness.CommandExecutor") as mock_exec_cls,
        patch("agent_ls.graph.nodes.kb_freshness.get_settings") as mock_settings,
        patch("agent_ls.graph.nodes.kb_freshness._check_url") as mock_check_url,
    ):
        mock_vault = MagicMock()
        mock_vault.list_docs.return_value = ["teams/eng/guide.md"]
        mock_vault.read.return_value = doc_content
        mock_vault_cls.return_value = mock_vault

        mock_settings.return_value.obsidian.freshness_fallback = False

        mock_exec_cls.return_value = MagicMock()
        mock_check_url.return_value = 404

        result = await kb_freshness_node(base_state)

    assert "teams/eng/guide.md" in result["obsidian_docs"]

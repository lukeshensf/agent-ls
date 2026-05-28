from unittest.mock import MagicMock, patch

import pytest

from agent_ls.graph.nodes.obsidian import obsidian_read_node, obsidian_write_node
from agent_ls.graph.state import ExecutionResult, PlanStep, UserContext


@pytest.fixture
def write_state():
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="setup")],
        "user_context": UserContext(team="payments"),
        "intent": "setup",
        "plan": [
            PlanStep(
                description="Install node",
                command="brew install node",
                status="done",
                duration_ms=1000,
            ),
            PlanStep(
                description="Install java",
                command="brew install java",
                status="failed",
            ),
        ],
        "current_step": 2,
        "execution_log": [
            ExecutionResult(
                command="brew install node",
                exit_code=0,
                stdout="installed",
                stderr="",
                duration_ms=1000,
            ),
        ],
        "approval_pending": None,
        "obsidian_docs": [],
        "slack_results": [],
        "error": None,
        "share_channel": None,
        "share_result": None,
        "extracted_urls": [],
    }


@pytest.fixture
def read_state():
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="share doc")],
        "user_context": UserContext(team="payments"),
        "intent": "share",
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
    }


@pytest.mark.asyncio
async def test_write_node_calls_git_commit(write_state, tmp_path):
    with (
        patch("agent_ls.graph.nodes.obsidian.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.obsidian.get_settings") as mock_settings,
        patch("agent_ls.graph.nodes.obsidian.GitSync") as mock_git_cls,
    ):
        mock_vault = MagicMock()
        mock_vault.write_with_template.return_value = tmp_path / "test.md"
        mock_vault_cls.return_value = mock_vault
        mock_vault.root = tmp_path

        mock_settings.return_value.obsidian.git_auto_sync = True

        mock_git = MagicMock()
        mock_git_cls.return_value = mock_git

        result = await obsidian_write_node(write_state)

    mock_git.commit_file.assert_called_once()
    assert len(result["obsidian_docs"]) == 1


@pytest.mark.asyncio
async def test_write_node_skips_git_when_disabled(write_state, tmp_path):
    with (
        patch("agent_ls.graph.nodes.obsidian.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.obsidian.get_settings") as mock_settings,
    ):
        mock_vault = MagicMock()
        mock_vault.write_with_template.return_value = tmp_path / "test.md"
        mock_vault_cls.return_value = mock_vault

        mock_settings.return_value.obsidian.git_auto_sync = False

        result = await obsidian_write_node(write_state)

    assert len(result["obsidian_docs"]) == 1


@pytest.mark.asyncio
async def test_read_node_calls_git_pull(read_state, tmp_path):
    with (
        patch("agent_ls.graph.nodes.obsidian.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.obsidian.get_settings") as mock_settings,
        patch("agent_ls.graph.nodes.obsidian.GitSync") as mock_git_cls,
    ):
        mock_vault = MagicMock()
        mock_vault.list_docs.return_value = ["teams/payments/setup.md"]
        mock_vault_cls.return_value = mock_vault
        mock_vault.root = tmp_path

        mock_settings.return_value.obsidian.git_auto_sync = True

        mock_git = MagicMock()
        mock_git_cls.return_value = mock_git

        result = await obsidian_read_node(read_state)

    mock_git.pull.assert_called_once()
    assert "teams/payments/setup.md" in result["obsidian_docs"]


@pytest.mark.asyncio
async def test_read_node_skips_git_when_disabled(read_state, tmp_path):
    with (
        patch("agent_ls.graph.nodes.obsidian.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.obsidian.get_settings") as mock_settings,
    ):
        mock_vault = MagicMock()
        mock_vault.list_docs.return_value = []
        mock_vault_cls.return_value = mock_vault

        mock_settings.return_value.obsidian.git_auto_sync = False

        result = await obsidian_read_node(read_state)

    assert result["obsidian_docs"] == []

"""End-to-end test for the update_kb flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.graph.state import UserContext


@pytest.mark.asyncio
async def test_update_kb_flow():
    """Verify: update_kb intent -> kb_freshness checks docs -> identifies stale."""
    from langchain_core.messages import HumanMessage

    from agent_ls.graph.nodes.kb_freshness import kb_freshness_node
    from agent_ls.graph.router import router_node

    initial_state = {
        "messages": [HumanMessage(content="update the knowledge base")],
        "user_context": UserContext(team="eng"),
        "intent": "",
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

    # Step 1: Router classifies as update_kb
    model_response = MagicMock()
    model_response.content = "update_kb"

    with patch("agent_ls.graph.router.ModelRouter") as mock_router_cls:
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=model_response)
        mock_router = MagicMock()
        mock_router.get_model_for_task.return_value = mock_model
        mock_router_cls.return_value = mock_router

        router_result = await router_node(initial_state)

    assert router_result["intent"] == "update_kb"

    # Step 2: KB freshness node finds a stale doc
    state_after_router = {**initial_state, **router_result}

    doc_content = """# Python Setup

Install Python:
```bash
brew install python@3.12
```

Check docs at https://broken-link.example.com/guide
"""

    with (
        patch("agent_ls.graph.nodes.kb_freshness.ObsidianVault") as mock_vault_cls,
        patch("agent_ls.graph.nodes.kb_freshness.CommandExecutor") as mock_exec_cls,
        patch("agent_ls.graph.nodes.kb_freshness.get_settings") as mock_settings,
        patch("agent_ls.graph.nodes.kb_freshness._check_url") as mock_check_url,
    ):
        mock_vault = MagicMock()
        mock_vault.list_docs.return_value = ["teams/eng/python-setup.md"]
        mock_vault.read.return_value = doc_content
        mock_vault_cls.return_value = mock_vault

        mock_settings.return_value.obsidian.freshness_fallback = False

        # brew is installed (which brew succeeds)
        ok_result = MagicMock()
        ok_result.exit_code = 0
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=ok_result)
        mock_exec_cls.return_value = mock_executor

        # URL is broken
        mock_check_url.return_value = 404

        kb_result = await kb_freshness_node(state_after_router)

    # Doc should be flagged as stale due to broken URL
    assert "teams/eng/python-setup.md" in kb_result["obsidian_docs"]

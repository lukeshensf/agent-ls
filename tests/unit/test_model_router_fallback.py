from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_ls.integrations.models.router import ModelRouter, ModelTier


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.models.cheap = "anthropic/claude-haiku"
    settings.models.expensive = "anthropic/claude-sonnet"
    settings.models.computer_use = "anthropic/claude-sonnet"
    settings.models.cheap_fallback = "ollama/llama3.2"
    settings.models.expensive_fallback = None
    settings.ollama.base_url = "http://localhost:11434"
    return settings


@pytest.mark.asyncio
async def test_ainvoke_success_first_try(mock_settings):
    with patch(
        "agent_ls.integrations.models.router.get_settings", return_value=mock_settings
    ):
        router = ModelRouter()
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "hello"
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        router._cache["anthropic/claude-haiku"] = mock_model

        result = await router.ainvoke_with_fallback("classify_intent", [])
        assert result.content == "hello"
        mock_model.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_ainvoke_retries_on_failure(mock_settings):
    with patch(
        "agent_ls.integrations.models.router.get_settings", return_value=mock_settings
    ):
        router = ModelRouter()
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "success"
        mock_model.ainvoke = AsyncMock(side_effect=[Exception("timeout"), mock_response])
        router._cache["anthropic/claude-haiku"] = mock_model

        result = await router.ainvoke_with_fallback("classify_intent", [], max_retries=2)
        assert result.content == "success"
        assert mock_model.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_ainvoke_falls_back_to_secondary(mock_settings):
    with patch(
        "agent_ls.integrations.models.router.get_settings", return_value=mock_settings
    ):
        router = ModelRouter()

        primary = MagicMock()
        primary.ainvoke = AsyncMock(side_effect=Exception("API down"))

        fallback = MagicMock()
        fallback_response = MagicMock()
        fallback_response.content = "fallback worked"
        fallback.ainvoke = AsyncMock(return_value=fallback_response)

        router._cache["anthropic/claude-haiku"] = primary
        router._cache["ollama/llama3.2"] = fallback

        result = await router.ainvoke_with_fallback("classify_intent", [], max_retries=1)
        assert result.content == "fallback worked"


@pytest.mark.asyncio
async def test_ainvoke_all_fail_raises(mock_settings):
    mock_settings.models.cheap_fallback = None
    with patch(
        "agent_ls.integrations.models.router.get_settings", return_value=mock_settings
    ):
        router = ModelRouter()
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(side_effect=Exception("permanent failure"))
        router._cache["anthropic/claude-haiku"] = mock_model

        with pytest.raises(RuntimeError, match="All models failed"):
            await router.ainvoke_with_fallback("classify_intent", [], max_retries=2)


@pytest.mark.asyncio
async def test_get_models_with_fallback(mock_settings):
    with patch(
        "agent_ls.integrations.models.router.get_settings", return_value=mock_settings
    ):
        router = ModelRouter()
        models = router._get_models_with_fallback(ModelTier.CHEAP)
        assert models == ["anthropic/claude-haiku", "ollama/llama3.2"]

        models = router._get_models_with_fallback(ModelTier.EXPENSIVE)
        assert models == ["anthropic/claude-sonnet"]

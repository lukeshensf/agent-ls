import os
from unittest.mock import MagicMock, patch

import pytest

from agent_ls.integrations.models.router import ModelRouter


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.models.cheap = "anthropic/claude-haiku"
    settings.models.expensive = "openai/gpt-4o"
    settings.models.computer_use = "anthropic/claude-sonnet"
    settings.models.cheap_fallback = None
    settings.models.expensive_fallback = None
    settings.ollama.base_url = "http://localhost:11434"
    return settings


def test_warns_missing_anthropic_key(mock_settings):
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with (
        patch(
            "agent_ls.integrations.models.router.get_settings", return_value=mock_settings
        ),
        patch.dict(os.environ, env, clear=True),
    ):
        router = ModelRouter()
        assert router is not None


def test_warns_missing_openai_key(mock_settings):
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with (
        patch(
            "agent_ls.integrations.models.router.get_settings", return_value=mock_settings
        ),
        patch.dict(os.environ, env, clear=True),
    ):
        router = ModelRouter()
        assert router is not None


def test_no_warning_for_ollama(mock_settings):
    mock_settings.models.cheap = "ollama/llama3.2"
    mock_settings.models.expensive = "ollama/codellama"
    mock_settings.models.computer_use = "ollama/llama3.2"
    with patch(
        "agent_ls.integrations.models.router.get_settings", return_value=mock_settings
    ):
        router = ModelRouter()
        assert router is not None

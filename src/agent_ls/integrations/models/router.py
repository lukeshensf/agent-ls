from __future__ import annotations

from enum import Enum
from typing import Optional

from langchain_core.language_models import BaseChatModel

from agent_ls.config.settings import get_settings


class ModelTier(Enum):
    CHEAP = "cheap"
    EXPENSIVE = "expensive"
    COMPUTER_USE = "computer_use"


TASK_ROUTING: dict[str, ModelTier] = {
    "classify_intent": ModelTier.CHEAP,
    "extract_context": ModelTier.CHEAP,
    "summarize_results": ModelTier.CHEAP,
    "check_doc_freshness": ModelTier.CHEAP,
    "generate_plan": ModelTier.EXPENSIVE,
    "debug_error": ModelTier.EXPENSIVE,
    "write_design_doc": ModelTier.EXPENSIVE,
    "computer_use": ModelTier.COMPUTER_USE,
}


class ModelRouter:
    def __init__(self):
        self._settings = get_settings()
        self._cache: dict[str, BaseChatModel] = {}

    def get_model_for_task(self, task: str) -> BaseChatModel:
        tier = TASK_ROUTING.get(task, ModelTier.EXPENSIVE)
        return self.get_model(tier)

    def get_model(self, tier: ModelTier) -> BaseChatModel:
        model_id = getattr(self._settings.models, tier.value)
        if model_id in self._cache:
            return self._cache[model_id]

        model = self._create_model(model_id)
        self._cache[model_id] = model
        return model

    def _create_model(self, model_id: str) -> BaseChatModel:
        provider, model_name = model_id.split("/", 1)

        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model=model_name)
        elif provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=model_name)
        elif provider == "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=model_name, base_url=self._settings.ollama.base_url
            )
        else:
            raise ValueError(f"Unknown model provider: {provider}")

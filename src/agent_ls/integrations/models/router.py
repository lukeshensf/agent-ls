from __future__ import annotations

import asyncio
import os
from enum import Enum
from typing import Optional

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from agent_ls.config.settings import get_settings

logger = structlog.get_logger()


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

_PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "bedrock": "BEDROCK_AUTH_TOKEN",
}


class ModelRouter:
    def __init__(self):
        self._settings = get_settings()
        self._cache: dict[str, BaseChatModel] = {}
        self._validate_config()

    def _validate_config(self) -> None:
        """Log warnings for missing API keys."""
        all_models = [
            self._settings.models.cheap,
            self._settings.models.expensive,
            self._settings.models.computer_use,
        ]
        if self._settings.models.cheap_fallback:
            all_models.append(self._settings.models.cheap_fallback)
        if self._settings.models.expensive_fallback:
            all_models.append(self._settings.models.expensive_fallback)

        warned: set[str] = set()
        for model_id in all_models:
            provider = model_id.split("/", 1)[0]
            env_var = _PROVIDER_ENV_VARS.get(provider)
            if env_var and not os.environ.get(env_var) and provider not in warned:
                logger.warning(
                    "missing_api_key",
                    provider=provider,
                    env_var=env_var,
                    model=model_id,
                )
                warned.add(provider)

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

    async def ainvoke_with_fallback(
        self, task: str, messages: list, max_retries: int = 2
    ) -> BaseMessage:
        """Invoke a model with automatic fallback and retry on failure."""
        tier = TASK_ROUTING.get(task, ModelTier.EXPENSIVE)
        models_to_try = self._get_models_with_fallback(tier)

        last_error: Optional[Exception] = None
        for model_id in models_to_try:
            model = self._get_or_create_model(model_id)
            for attempt in range(max_retries):
                try:
                    return await model.ainvoke(messages)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait = 0.5 * (2**attempt)
                        logger.info(
                            "model_retry",
                            model=model_id,
                            attempt=attempt + 1,
                            wait=wait,
                            error=str(e),
                        )
                        await asyncio.sleep(wait)
            logger.warning("model_failed", model=model_id, error=str(last_error))

        raise RuntimeError(f"All models failed for task '{task}': {last_error}")

    def _get_models_with_fallback(self, tier: ModelTier) -> list[str]:
        """Get primary model + fallback for a tier."""
        primary = getattr(self._settings.models, tier.value)
        models = [primary]

        fallback_attr = f"{tier.value}_fallback"
        fallback = getattr(self._settings.models, fallback_attr, None)
        if fallback:
            models.append(fallback)

        return models

    def _get_or_create_model(self, model_id: str) -> BaseChatModel:
        if model_id in self._cache:
            return self._cache[model_id]
        model = self._create_model(model_id)
        self._cache[model_id] = model
        return model

    def _create_model(self, model_id: str) -> BaseChatModel:
        provider, model_name = model_id.split("/", 1)

        if provider == "bedrock":
            from langchain_aws import ChatBedrockConverse

            bedrock_cfg = self._settings.bedrock
            kwargs = {
                "model": model_name,
                "region_name": bedrock_cfg.region,
            }
            if bedrock_cfg.endpoint_url:
                kwargs["endpoint_url"] = bedrock_cfg.endpoint_url
            if bedrock_cfg.auth_token:
                import boto3
                from botocore.config import Config

                session = boto3.Session(region_name=bedrock_cfg.region)
                client = session.client(
                    "bedrock-runtime",
                    endpoint_url=bedrock_cfg.endpoint_url,
                    config=Config(
                        inject_host_prefix=False,
                    ),
                )
                kwargs["client"] = client

            return ChatBedrockConverse(**kwargs)
        elif provider == "anthropic":
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

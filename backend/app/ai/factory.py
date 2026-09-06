"""
VoltAI LLM Provider Factory

Returns configured LLM provider adapter instance based on AIConfig.
This is the single coupling point for LLM instantiation.
"""

import logging
from typing import Optional

from backend.app.ai.config import AIConfig, AIConfigurationError
from backend.app.ai.providers import BaseLLMProvider

logger = logging.getLogger(__name__)


def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseLLMProvider:
    """
    Instantiate and return an LLM provider adapter.

    Args:
        provider_name: Optional override for AIConfig.PROVIDER
        api_key: Optional override for AIConfig.GEMINI_API_KEY

    Returns:
        BaseLLMProvider instance

    Raises:
        AIConfigurationError: If provider is unknown
    """
    from backend.app.ai.providers.gemini import GeminiProvider

    name = (provider_name or AIConfig.PROVIDER).lower().strip()
    key = api_key if api_key is not None else AIConfig.GEMINI_API_KEY

    if name == "gemini":
        return GeminiProvider(
            api_key=key,
            model_name=AIConfig.GEMINI_MODEL,
            timeout_seconds=AIConfig.TIMEOUT_SECONDS,
            max_retries=AIConfig.MAX_RETRIES,
        )
    else:
        raise AIConfigurationError(
            f"Unsupported LLM provider '{name}'. VoltAI currently supports 'gemini'."
        )

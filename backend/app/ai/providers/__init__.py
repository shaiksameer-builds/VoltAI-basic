"""
VoltAI Provider-Agnostic LLM Architecture

Base class and custom exceptions for LLM providers.
Business logic depends exclusively on BaseLLMProvider.
"""

from abc import ABC, abstractmethod
from typing import Optional


class LLMError(Exception):
    """Base exception for all LLM provider errors."""
    pass


class LLMAuthError(LLMError):
    """Raised when authentication fails (401/403 or invalid API key)."""
    pass


class LLMQuotaError(LLMError):
    """Raised when rate limits or quotas are exceeded (429)."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when an HTTP request to the LLM provider times out."""
    pass


class LLMProviderError(LLMError):
    """Raised for server errors (5xx) or unexpected provider behavior."""
    pass


class BaseLLMProvider(ABC):
    """
    Abstract Base Class for all VoltAI LLM providers.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (e.g., 'gemini')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return configured model name (e.g., 'gemini-1.5-flash')."""
        pass

    @abstractmethod
    def generate_explanation(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate a natural-language response given system instructions and user context.

        Args:
            system_instruction: Bounded grounding instructions.
            user_prompt: Structured context and user query.
            temperature: Generation temperature (low for deterministic factual answers).
            max_tokens: Maximum response tokens.

        Returns:
            Generated response string.

        Raises:
            LLMAuthError, LLMQuotaError, LLMTimeoutError, LLMProviderError
        """
        pass

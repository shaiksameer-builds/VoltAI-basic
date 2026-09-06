"""
VoltAI AI / LLM Layer Configuration

Reads environment variables for LLM provider configuration.
Default provider: gemini
Model: gemini-1.5-flash (or configured via GEMINI_MODEL)
"""

import os


class AIConfig:
    """
    Centralized AI configuration loaded from environment variables.
    """

    PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower().strip()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
    TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "15.0"))
    MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "1"))

    @classmethod
    def is_api_key_configured(cls) -> bool:
        """Return True if a non-empty API key is present."""
        return bool(cls.GEMINI_API_KEY)

    @classmethod
    def validate(cls) -> None:
        """
        Validate provider configuration.
        Raises AIConfigurationError if configured provider requires credentials that are missing.
        """
        if cls.PROVIDER == "gemini" and not cls.is_api_key_configured():
            raise AIConfigurationError(
                "Gemini provider requires GEMINI_API_KEY environment variable to be set. "
                "AI layer will operate in deterministic fallback mode."
            )


class AIConfigurationError(Exception):
    """Raised when LLM configuration is invalid or missing credentials."""
    pass

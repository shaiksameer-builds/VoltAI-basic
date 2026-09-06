"""
VoltAI Weather Provider Configuration

Reads weather provider settings from environment variables.
No API key is required for Open-Meteo (the default development provider).
Future providers (key-based) are supported via WEATHER_API_KEY.

Environment Variables:
    WEATHER_PROVIDER          : Provider name (default: open_meteo)
    WEATHER_API_KEY           : Optional API key (empty for Open-Meteo)
    WEATHER_API_BASE_URL      : Optional custom base URL override
    WEATHER_TIMEOUT_SECONDS   : HTTP timeout in seconds (default: 30)
    WEATHER_MAX_RETRIES       : Number of HTTP retries (default: 2)
"""

import os


class WeatherConfig:
    """
    Centralized weather integration configuration loaded from environment.
    API key is optional — Open-Meteo does not require one.
    """

    # The active provider name. Determines which adapter is instantiated.
    PROVIDER: str = os.getenv("WEATHER_PROVIDER", "open_meteo")

    # Optional API key — empty string means no key required (e.g. Open-Meteo).
    API_KEY: str = os.getenv("WEATHER_API_KEY", "")

    # Optional base URL override. Providers have built-in defaults.
    API_BASE_URL: str = os.getenv("WEATHER_API_BASE_URL", "")

    # HTTP request timeout in seconds
    TIMEOUT_SECONDS: float = float(os.getenv("WEATHER_TIMEOUT_SECONDS", "30"))

    # Number of retries on transient HTTP failures (5xx, timeout)
    MAX_RETRIES: int = int(os.getenv("WEATHER_MAX_RETRIES", "2"))

    @classmethod
    def is_key_required(cls) -> bool:
        """Return True if the current provider requires a non-empty API key."""
        key_required_providers = {"weatherapi", "tomorrow_io", "openweathermap"}
        return cls.PROVIDER.lower() in key_required_providers

    @classmethod
    def validate(cls) -> None:
        """
        Raise ConfigurationError if the active provider requires a key but none is set.
        Open-Meteo always passes validation.
        """
        if cls.is_key_required() and not cls.API_KEY:
            raise WeatherConfigurationError(
                f"Weather provider '{cls.PROVIDER}' requires WEATHER_API_KEY to be set. "
                f"Open-Meteo does not require a key. "
                f"Set WEATHER_PROVIDER=open_meteo to use the key-free default."
            )


class WeatherConfigurationError(Exception):
    """Raised when weather provider configuration is invalid or incomplete."""
    pass

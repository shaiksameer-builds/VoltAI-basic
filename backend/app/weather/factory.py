"""
VoltAI Weather Provider Factory

Instantiates the correct weather provider adapter based on the WEATHER_PROVIDER
environment variable. Business logic calls get_provider() rather than importing
any concrete adapter — this is the single coupling point.

Adding a new provider:
  1. Implement BaseWeatherProvider in providers/<your_provider>.py
  2. Register it in the PROVIDER_REGISTRY dict below.
  3. Set WEATHER_PROVIDER=<your_key> in .env.
"""

import logging
from typing import Optional

from backend.app.weather.config import WeatherConfig, WeatherConfigurationError
from backend.app.weather.providers import BaseWeatherProvider

logger = logging.getLogger(__name__)


def get_provider(provider_name: Optional[str] = None) -> BaseWeatherProvider:
    """
    Return a configured provider adapter instance.

    Args:
        provider_name: Override the WEATHER_PROVIDER env setting for this call.
                       Defaults to WeatherConfig.PROVIDER.

    Returns:
        Concrete BaseWeatherProvider instance.

    Raises:
        WeatherConfigurationError: If the provider is unknown or misconfigured.
    """
    # Import here to avoid circular imports and allow lazy loading
    from backend.app.weather.providers.open_meteo import OpenMeteoProvider

    # Registry maps provider keys → factory callables
    PROVIDER_REGISTRY = {
        "open_meteo": lambda: OpenMeteoProvider(
            base_url=WeatherConfig.API_BASE_URL or "",
            timeout_seconds=WeatherConfig.TIMEOUT_SECONDS,
            max_retries=WeatherConfig.MAX_RETRIES,
        ),
        # Future providers:
        # "weatherapi": lambda: WeatherAPIProvider(api_key=WeatherConfig.API_KEY, ...),
        # "tomorrow_io": lambda: TomorrowIOProvider(api_key=WeatherConfig.API_KEY, ...),
        # "govt_imd": lambda: IMDProvider(...),
    }

    name = (provider_name or WeatherConfig.PROVIDER).lower().strip()

    if name not in PROVIDER_REGISTRY:
        available = ", ".join(PROVIDER_REGISTRY.keys())
        raise WeatherConfigurationError(
            f"Unknown weather provider '{name}'. Available providers: {available}. "
            f"Set WEATHER_PROVIDER environment variable to one of these values."
        )

    # Validate configuration (checks API key requirement)
    WeatherConfig.validate()

    provider = PROVIDER_REGISTRY[name]()
    logger.info("Weather provider initialized: %s (requires_key=%s)", name, provider.requires_api_key)
    return provider

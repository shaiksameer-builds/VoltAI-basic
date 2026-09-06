"""
VoltAI Weather Provider Interface

Defines the abstract base class that all weather provider adapters must implement.
Business logic (forecasting, analytics) depends ONLY on this interface — never on
any concrete provider such as Open-Meteo.

Provider Adapter Contract:
  1. Accepts a site_id and a date range.
  2. Retrieves raw weather data from its source (API, file, sensor, etc.).
  3. Normalizes the response into a list of NormalizedWeatherRecord.
  4. Raises WeatherProviderError on provider-level failures.

Future providers (key-based, government, IoT) implement BaseWeatherProvider
without changing any forecasting or ingestion business logic.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List

from backend.app.weather.schemas import NormalizedWeatherRecord


class WeatherProviderError(Exception):
    """Raised when a weather provider fails to return usable data."""
    pass


class WeatherAuthError(WeatherProviderError):
    """Raised when a provider rejects the API key or authentication fails."""
    pass


class WeatherQuotaError(WeatherProviderError):
    """Raised when provider quota or rate limits are exceeded."""
    pass


class WeatherTimeoutError(WeatherProviderError):
    """Raised when the provider HTTP request times out."""
    pass


class BaseWeatherProvider(ABC):
    """
    Abstract base class for all VoltAI weather provider adapters.

    Subclasses implement provider-specific HTTP calls and response parsing.
    All adapters normalize output into NormalizedWeatherRecord so that
    the rest of the application is provider-agnostic.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Unique string identifier for the provider (e.g., 'open_meteo', 'weatherapi').
        Stored in the WeatherReading.provider field.
        """
        pass

    @property
    def requires_api_key(self) -> bool:
        """
        Override to True for providers that require WEATHER_API_KEY.
        Open-Meteo returns False — no key needed.
        """
        return False

    @abstractmethod
    def fetch_hourly_weather(
        self,
        site_id: str,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        timezone: str = "Asia/Kolkata",
    ) -> List[NormalizedWeatherRecord]:
        """
        Fetch and normalize hourly weather for the given site and date range.

        Args:
            site_id:    VoltAI site identifier (stored on each record).
            latitude:   Site latitude in decimal degrees.
            longitude:  Site longitude in decimal degrees.
            start_date: Inclusive start date for historical/forecast data.
            end_date:   Inclusive end date.
            timezone:   IANA timezone string for the site.

        Returns:
            List of NormalizedWeatherRecord, one per hour.

        Raises:
            WeatherAuthError:    On authentication failure.
            WeatherQuotaError:   On quota/rate-limit exceeded.
            WeatherTimeoutError: On HTTP timeout.
            WeatherProviderError: On any other provider failure.
        """
        pass

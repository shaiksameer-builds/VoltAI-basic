"""
VoltAI Open-Meteo Weather Provider Adapter (Stage 9)

Implements BaseWeatherProvider using the Open-Meteo API:
  https://open-meteo.com/en/docs

Open-Meteo is a free, no-API-key-required weather service suitable for:
  - Development
  - SIH (Smart India Hackathon) non-commercial use
  - Fallback when paid providers fail

This adapter is isolated behind the BaseWeatherProvider interface.
The rest of VoltAI never imports this class directly.
Use WeatherProviderFactory.get_provider() to obtain a provider instance.

Fetched Variables (hourly):
  - temperature_2m              : Air temperature at 2m (°C)
  - relative_humidity_2m        : Relative humidity at 2m (%)
  - precipitation                : Hourly precipitation (mm)
  - cloud_cover                  : Total cloud cover (%)
  - wind_speed_10m              : Wind speed at 10m (m/s)
  - wind_direction_10m          : Wind direction at 10m (°)
  - shortwave_radiation         : Solar shortwave radiation (W/m²)

Error Handling:
  - HTTP 4xx authentication errors → WeatherAuthError
  - HTTP 429 quota exceeded → WeatherQuotaError
  - Timeout → WeatherTimeoutError
  - HTTP 5xx / connection errors → WeatherProviderError
  - Malformed response → WeatherProviderError with description
  - Missing optional fields → logged, None stored (not a fatal failure)
"""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from backend.app.weather.providers import (
    BaseWeatherProvider,
    WeatherAuthError,
    WeatherProviderError,
    WeatherQuotaError,
    WeatherTimeoutError,
)
from backend.app.weather.schemas import NormalizedWeatherRecord

logger = logging.getLogger(__name__)

OPEN_METEO_DEFAULT_BASE_URL = "https://api.open-meteo.com"

# Hourly variable names as expected by Open-Meteo API
OPEN_METEO_HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "shortwave_radiation",
]


class OpenMeteoProvider(BaseWeatherProvider):
    """
    Open-Meteo weather provider adapter.

    No API key is required. Uses httpx for HTTP requests.
    """

    def __init__(
        self,
        base_url: str = "",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        """
        Args:
            base_url:        Override the default Open-Meteo API base URL (useful for tests).
            timeout_seconds: HTTP request timeout.
            max_retries:     Number of retry attempts on transient failures.
            http_client:     Inject a custom httpx.Client (for testing/mocking).
        """
        self._base_url = (base_url or OPEN_METEO_DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._client = http_client  # None → create fresh per request

    @property
    def provider_name(self) -> str:
        return "open_meteo"

    @property
    def requires_api_key(self) -> bool:
        return False

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
        Fetch hourly weather from Open-Meteo for the given location and date range.
        Returns a list of NormalizedWeatherRecord, one per hour.
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(OPEN_METEO_HOURLY_VARS),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": timezone,
            "timeformat": "iso8601",
        }

        raw = self._get_with_retry(f"{self._base_url}/v1/forecast", params)
        return self._parse_response(raw, site_id, latitude, longitude)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_with_retry(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a GET request with retry on transient failures.
        Returns parsed JSON dict.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                raw = self._do_get(url, params)
                return raw
            except WeatherTimeoutError as exc:
                last_exc = exc
                logger.warning(
                    "Open-Meteo request timeout (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                )
            except WeatherProviderError:
                # Non-retriable errors (4xx etc.) — re-raise immediately
                raise

        raise WeatherTimeoutError(
            f"Open-Meteo request timed out after {self._max_retries + 1} attempts."
        ) from last_exc

    def _do_get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single HTTP GET and map errors to WeatherProvider exceptions.
        """
        if self._client is not None:
            # Use injected client (test/mock scenario)
            return self._execute_request(self._client, url, params)
        else:
            with httpx.Client(timeout=self._timeout) as client:
                return self._execute_request(client, url, params)

    def _execute_request(
        self, client: httpx.Client, url: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise WeatherTimeoutError(f"HTTP timeout fetching Open-Meteo data: {exc}") from exc
        except httpx.RequestError as exc:
            raise WeatherProviderError(
                f"HTTP connection error fetching Open-Meteo data: {exc}"
            ) from exc

        if response.status_code == 401 or response.status_code == 403:
            raise WeatherAuthError(
                f"Open-Meteo returned HTTP {response.status_code} — authentication failure."
            )
        if response.status_code == 429:
            raise WeatherQuotaError("Open-Meteo rate limit exceeded (HTTP 429).")
        if response.status_code >= 500:
            raise WeatherProviderError(
                f"Open-Meteo server error: HTTP {response.status_code} — {response.text[:200]}"
            )
        if response.status_code != 200:
            raise WeatherProviderError(
                f"Open-Meteo returned unexpected HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            return response.json()
        except Exception as exc:
            raise WeatherProviderError(
                f"Open-Meteo returned malformed JSON: {exc}"
            ) from exc

    def _parse_response(
        self,
        raw: Dict[str, Any],
        site_id: str,
        latitude: float,
        longitude: float,
    ) -> List[NormalizedWeatherRecord]:
        """
        Parse Open-Meteo JSON response into NormalizedWeatherRecord list.
        Missing optional fields are set to None (never fatal).
        """
        hourly = raw.get("hourly")
        if not isinstance(hourly, dict):
            raise WeatherProviderError(
                "Open-Meteo response missing 'hourly' section."
            )

        times = hourly.get("time", [])
        if not times:
            logger.warning("Open-Meteo returned empty 'time' array for site '%s'.", site_id)
            return []

        fetched_at = datetime.now(timezone.utc)

        def get_col(key: str) -> List[Optional[float]]:
            col = hourly.get(key, [])
            # Pad with None if shorter than times (defensive)
            while len(col) < len(times):
                col.append(None)
            return col

        temps = get_col("temperature_2m")
        humids = get_col("relative_humidity_2m")
        precips = get_col("precipitation")
        clouds = get_col("cloud_cover")
        winds = get_col("wind_speed_10m")
        wind_dirs = get_col("wind_direction_10m")
        radiations = get_col("shortwave_radiation")

        records: List[NormalizedWeatherRecord] = []
        rejected = 0

        for i, ts_str in enumerate(times):
            try:
                ts = _parse_timestamp(ts_str)
            except ValueError as exc:
                logger.warning(
                    "Skipping Open-Meteo record at index %d for site '%s': invalid timestamp '%s': %s",
                    i, site_id, ts_str, exc,
                )
                rejected += 1
                continue

            record = NormalizedWeatherRecord(
                site_id=site_id,
                timestamp=ts,
                latitude=latitude,
                longitude=longitude,
                temperature_c=_safe_float(temps[i]),
                relative_humidity_pct=_safe_float(humids[i]),
                precipitation_mm=_safe_float(precips[i]),
                cloud_cover_pct=_safe_float(clouds[i]),
                wind_speed_ms=_safe_float(winds[i]),
                wind_direction_deg=_safe_float(wind_dirs[i]),
                shortwave_radiation_wm2=_safe_float(radiations[i]),
                provider=self.provider_name,
                fetched_at=fetched_at,
            )
            records.append(record)

        if rejected:
            logger.warning(
                "Open-Meteo parser rejected %d record(s) for site '%s' due to invalid timestamps.",
                rejected, site_id,
            )

        logger.info(
            "Open-Meteo: fetched %d hourly records for site '%s'.",
            len(records), site_id,
        )
        return records


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _parse_timestamp(ts_str: str) -> datetime:
    """
    Parse an ISO 8601 timestamp string from Open-Meteo into a timezone-aware UTC datetime.
    Supports strings like '2026-01-01T00:00', '2026-01-01T00:00:00Z', '2026-01-01T00:00+05:30'.
    """
    ts_str = ts_str.strip()
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception as exc:
        raise ValueError(f"Cannot parse timestamp: '{ts_str}'") from exc


def _safe_float(val: Any) -> Optional[float]:
    """Convert a value to float, returning None if null or unconvertible."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

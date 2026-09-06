"""
VoltAI Weather Schemas (Stage 9)

Pydantic models for normalized weather records, ingestion requests/responses,
and API query parameters.

All weather data flowing through VoltAI is normalized into NormalizedWeatherRecord
regardless of the originating provider.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NormalizedWeatherRecord(BaseModel):
    """
    Normalized hourly weather observation or forecast point.

    Units:
        temperature_c           : Degrees Celsius (°C)
        relative_humidity_pct   : Percentage (0.0 – 100.0)
        precipitation_mm        : Millimeters per hour
        cloud_cover_pct         : Percentage (0.0 – 100.0)
        wind_speed_ms           : Metres per second
        wind_direction_deg      : Degrees (0 – 360, meteorological convention)
        shortwave_radiation_wm2 : Watts per square metre (W/m²)
    """

    site_id: str = Field(..., min_length=1, max_length=64)
    timestamp: datetime = Field(..., description="Hourly observation time (timezone-aware UTC)")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)

    # Core meteorological fields — all optional to support partial provider responses
    temperature_c: Optional[float] = Field(default=None, description="Air temperature in °C")
    relative_humidity_pct: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Relative humidity %"
    )
    precipitation_mm: Optional[float] = Field(
        default=None, ge=0.0, description="Hourly precipitation in mm"
    )
    cloud_cover_pct: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Cloud cover %"
    )
    wind_speed_ms: Optional[float] = Field(
        default=None, ge=0.0, description="Wind speed in m/s"
    )
    wind_direction_deg: Optional[float] = Field(
        default=None, ge=0.0, le=360.0, description="Wind direction in degrees"
    )
    shortwave_radiation_wm2: Optional[float] = Field(
        default=None, ge=0.0, description="Solar shortwave radiation in W/m²"
    )

    # Provenance
    provider: str = Field(..., description="Provider identifier (e.g., 'open_meteo')")
    fetched_at: datetime = Field(..., description="When this record was retrieved (UTC)")

    model_config = ConfigDict(from_attributes=True)


class WeatherIngestRequest(BaseModel):
    """Request body for triggering weather data ingestion for a site and date range."""

    site_id: str = Field(..., min_length=1, max_length=64, description="VoltAI site identifier")
    start_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Inclusive start date in YYYY-MM-DD format",
    )
    end_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Inclusive end date in YYYY-MM-DD format",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Override provider for this request. Defaults to WEATHER_PROVIDER env setting.",
    )


class WeatherIngestSummary(BaseModel):
    """Summary returned after a weather ingestion operation."""

    site_id: str
    provider: str
    start_date: str
    end_date: str
    rows_received: int = Field(..., description="Total weather records received from provider")
    rows_inserted: int = Field(..., description="New records successfully inserted")
    rows_skipped: int = Field(..., description="Records skipped due to existing duplicates")
    rows_rejected: int = Field(..., description="Records rejected due to validation errors")
    errors: List[str] = Field(default_factory=list, description="Error messages for rejected records")


class WeatherRecord(BaseModel):
    """Schema returned when querying persisted weather readings from the API."""

    id: int
    site_id: str
    timestamp: datetime
    latitude: float
    longitude: float
    temperature_c: Optional[float]
    relative_humidity_pct: Optional[float]
    precipitation_mm: Optional[float]
    cloud_cover_pct: Optional[float]
    wind_speed_ms: Optional[float]
    wind_direction_deg: Optional[float]
    shortwave_radiation_wm2: Optional[float]
    provider: str
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeatherStatusResponse(BaseModel):
    """Status of the weather integration subsystem."""

    configured_provider: str
    provider_requires_key: bool
    api_key_configured: bool
    status: str  # "ready" | "degraded" | "misconfigured"
    message: str
    available_sites: List[str]
    total_weather_records: int


class WeatherFeatures(BaseModel):
    """
    Engineered weather features for a specific site at a specific hour,
    suitable for inclusion in the forecasting feature matrix.
    """

    site_id: str
    timestamp: datetime
    temperature_c: float = 25.0            # Fallback: moderate temperature
    relative_humidity_pct: float = 60.0   # Fallback: moderate humidity
    precipitation_mm: float = 0.0
    cloud_cover_pct: float = 50.0         # Fallback: partial cloud
    wind_speed_ms: float = 3.0            # Fallback: light breeze
    shortwave_radiation_wm2: float = 0.0
    # Derived / engineered
    is_clear_sky: bool = False             # cloud_cover_pct < 20
    wind_speed_category: int = 1           # 0=calm, 1=light, 2=moderate, 3=strong
    heat_index: float = 25.0              # Apparent temperature proxy

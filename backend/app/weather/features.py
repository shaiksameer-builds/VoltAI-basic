"""
VoltAI Weather Feature Engineering (Stage 9)

Transforms persisted WeatherReading records into ML-ready features that can
be joined with the existing EnergyReading feature matrix in feature_engineering.py.

Design Principles:
  - No target leakage: only use weather available at prediction time.
  - Graceful degradation: if weather is unavailable, return fallback defaults.
  - The forecasting engine NEVER crashes due to missing weather.
  - Clearly separate energy telemetry / weather data / engineered features / output.

Fallback Values (used when no weather data is available):
  Temperature:       25°C    (moderate Indian climate)
  Humidity:          60%     (moderate)
  Cloud cover:       50%     (partial cloud — neutral for solar)
  Wind speed:        3 m/s   (light breeze)
  Precipitation:     0 mm
  Radiation:         0 W/m² (conservative — let lag features carry solar history)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.database.models import WeatherReading
from backend.app.weather.ingestion import WeatherIngestionService

logger = logging.getLogger(__name__)

# Default weather feature values used when no persisted weather is available
WEATHER_FEATURE_DEFAULTS: Dict[str, float] = {
    "weather_temp_c": 25.0,
    "weather_humidity_pct": 60.0,
    "weather_cloud_cover_pct": 50.0,
    "weather_wind_speed_ms": 3.0,
    "weather_precipitation_mm": 0.0,
    "weather_radiation_wm2": 0.0,
    "weather_is_clear_sky": 0.0,         # 0 = not clear
    "weather_wind_category": 1.0,        # 1 = light wind
    "weather_heat_index": 25.0,
    "weather_available": 0.0,            # 0 = no weather data (fallback active)
}

WEATHER_FEATURE_COLUMNS = list(WEATHER_FEATURE_DEFAULTS.keys())


def _compute_heat_index(temp_c: float, humidity_pct: float) -> float:
    """
    Simplified apparent temperature (heat index) proxy.
    Uses a linear approximation valid for high-humidity tropical conditions.
    """
    hi = temp_c + 0.33 * (humidity_pct / 100.0 * 6.105 * np.exp(17.27 * temp_c / (237.7 + temp_c))) - 4.0
    return round(float(hi), 2)


def _wind_speed_category(wind_speed_ms: float) -> int:
    """
    Categorize wind speed into 4 classes.
    0: calm (<1 m/s), 1: light (1-5 m/s), 2: moderate (5-10 m/s), 3: strong (>10 m/s)
    """
    if wind_speed_ms < 1.0:
        return 0
    elif wind_speed_ms < 5.0:
        return 1
    elif wind_speed_ms < 10.0:
        return 2
    else:
        return 3


def weather_row_to_features(row: WeatherReading) -> Dict[str, float]:
    """
    Convert a single WeatherReading ORM row to a feature dict.
    Uses fallback defaults for any None fields.
    """
    temp = row.temperature_c if row.temperature_c is not None else WEATHER_FEATURE_DEFAULTS["weather_temp_c"]
    humidity = row.relative_humidity_pct if row.relative_humidity_pct is not None else WEATHER_FEATURE_DEFAULTS["weather_humidity_pct"]
    cloud = row.cloud_cover_pct if row.cloud_cover_pct is not None else WEATHER_FEATURE_DEFAULTS["weather_cloud_cover_pct"]
    wind = row.wind_speed_ms if row.wind_speed_ms is not None else WEATHER_FEATURE_DEFAULTS["weather_wind_speed_ms"]
    precip = row.precipitation_mm if row.precipitation_mm is not None else 0.0
    radiation = row.shortwave_radiation_wm2 if row.shortwave_radiation_wm2 is not None else 0.0

    return {
        "weather_temp_c": round(temp, 3),
        "weather_humidity_pct": round(humidity, 3),
        "weather_cloud_cover_pct": round(cloud, 3),
        "weather_wind_speed_ms": round(wind, 3),
        "weather_precipitation_mm": round(precip, 3),
        "weather_radiation_wm2": round(radiation, 3),
        "weather_is_clear_sky": 1.0 if cloud < 20.0 else 0.0,
        "weather_wind_category": float(_wind_speed_category(wind)),
        "weather_heat_index": _compute_heat_index(temp, humidity),
        "weather_available": 1.0,
    }


def build_weather_feature_dataframe(
    db: Session,
    site_id: str,
    timestamps: List[datetime],
) -> pd.DataFrame:
    """
    Build a weather feature DataFrame aligned to a list of energy timestamps.

    For each timestamp, look up the matching weather record.
    Missing weather hours are filled with fallback defaults (weather_available=0).

    Args:
        db:         SQLAlchemy session.
        site_id:    Site identifier.
        timestamps: List of datetime objects from energy readings.

    Returns:
        pd.DataFrame with one row per timestamp and WEATHER_FEATURE_COLUMNS columns.
        Index matches the input timestamps list order.
    """
    if not timestamps:
        return pd.DataFrame(columns=WEATHER_FEATURE_COLUMNS)

    # Fetch all weather for this site in the timestamp range (single query)
    start_ts = min(timestamps) - timedelta(hours=1)
    end_ts = max(timestamps) + timedelta(hours=1)
    weather_rows = WeatherIngestionService.get_weather_for_site(
        db=db, site_id=site_id, start_ts=start_ts, end_ts=end_ts, limit=10000
    )

    # Build a lookup dict: truncated_utc_hour → feature dict
    weather_lookup: Dict[datetime, Dict[str, float]] = {}
    for row in weather_rows:
        # Normalize timestamp to UTC-aware, truncate to hour for matching
        ts = _normalize_to_utc_hour(row.timestamp)
        weather_lookup[ts] = weather_row_to_features(row)

    # Build feature rows aligned to energy timestamps
    feature_rows = []
    for ts in timestamps:
        ts_key = _normalize_to_utc_hour(ts)
        if ts_key in weather_lookup:
            feature_rows.append(weather_lookup[ts_key])
        else:
            feature_rows.append(dict(WEATHER_FEATURE_DEFAULTS))

    df = pd.DataFrame(feature_rows, columns=WEATHER_FEATURE_COLUMNS)
    n_available = int(df["weather_available"].sum())
    logger.debug(
        "WeatherFeatureEngineering: site='%s', %d/%d timestamps have weather data.",
        site_id, n_available, len(timestamps),
    )
    return df


def _normalize_to_utc_hour(ts: datetime) -> datetime:
    """Normalize a datetime to UTC-aware truncated to the hour."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def get_weather_features_for_latest(
    db: Session,
    site_id: str,
    latest_ts: datetime,
) -> Dict[str, float]:
    """
    Get weather features for the latest timestamp used in inference.
    Returns fallback defaults if no weather record exists for that hour.

    Args:
        db:         SQLAlchemy session.
        site_id:    Site identifier.
        latest_ts:  Latest energy reading timestamp (inference time).

    Returns:
        Feature dict with WEATHER_FEATURE_COLUMNS keys.
    """
    ts_key = _normalize_to_utc_hour(latest_ts)

    rows = WeatherIngestionService.get_weather_for_site(
        db=db, site_id=site_id, start_ts=ts_key, end_ts=ts_key, limit=1
    )

    if rows:
        features = weather_row_to_features(rows[0])
        logger.debug(
            "WeatherFeatures: found weather for site='%s' at %s (provider=%s).",
            site_id, ts_key, rows[0].provider,
        )
        return features

    logger.info(
        "WeatherFeatures: no weather data for site='%s' at %s — using fallback defaults.",
        site_id, ts_key,
    )
    return dict(WEATHER_FEATURE_DEFAULTS)

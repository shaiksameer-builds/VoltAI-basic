# VoltAI — Weather Integration (Stage 9)

## Executive Summary

Stage 9 introduces a provider-agnostic, API-key-optional weather integration module into VoltAI. Weather telemetry (temperature, humidity, precipitation, cloud cover, wind speed, wind direction, and solar irradiance) is fetched from external providers, stored in the database, and integrated into the feature engineering pipeline for solar and wind forecasting.

By default, VoltAI uses **Open-Meteo**, a free and open-source weather API that requires **no API key** for non-commercial/academic use.

---

## Key Features

1. **Provider-Agnostic Architecture**:
   - Built on an Abstract Base Class (`BaseWeatherProvider`).
   - Factory pattern (`get_provider()`) decouples the application from concrete weather API providers.
   - Simple addition of future key-based providers (e.g. Visual Crossing, OpenWeatherMap) without changing business or forecasting logic.

2. **API-Key Optional Configuration**:
   - `open_meteo` requires no API key.
   - Built-in validation ensures key-requiring providers are flagged if their key is missing from environment variables.

3. **Data Ingestion & Deduplication**:
   - Database model `WeatherReading` with `UniqueConstraint("site_id", "timestamp")`.
   - Idempotent ingestion pipeline (`WeatherIngestionService`) skips duplicate records gracefully.

4. **Weather Feature Engineering**:
   - Extends the feature matrix from **21 to 31 columns**.
   - Includes derived features such as heat index, wind categories, cloud opacity, and weather availability flags.
   - Robust fallback mode: if weather telemetry is unavailable, features default to safe neutral values without breaking forecasting models.

---

## Module Structure

```
backend/app/weather/
├── __init__.py          # Package initialization
├── config.py            # Environment-driven WeatherConfig
├── factory.py           # Provider registry and factory (get_provider)
├── features.py          # Feature extraction & fallback transformation
├── ingestion.py         # Database persistence & querying service
├── schemas.py           # Pydantic schemas for requests, responses, records
├── service.py           # High-level orchestrator service
├── sites.py             # Registered site locations (latitude, longitude, timezone)
└── providers/
    ├── __init__.py      # Base class (BaseWeatherProvider) & exception hierarchy
    └── open_meteo.py    # Open-Meteo adapter implementation
```

---

## Data Model

### `WeatherReading` (ORM Model)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | Primary Key | Auto-incrementing ID |
| `site_id` | String | Indexed | Site identifier (e.g. `site_001`) |
| `timestamp` | DateTime(timezone=True) | Indexed | UTC timestamp |
| `temperature` | Float | Optional | Temperature in °C |
| `relative_humidity` | Float | Optional | Humidity in % (0–100) |
| `precipitation` | Float | Optional | Precipitation in mm |
| `cloud_cover` | Float | Optional | Cloud cover % (0–100) |
| `wind_speed` | Float | Optional | Wind speed in km/h |
| `wind_direction` | Float | Optional | Wind direction in degrees (0–360) |
| `solar_irradiance` | Float | Optional | Shortwave radiation in W/m² |
| `provider` | String | Default "open_meteo" | Source provider name |
| `fetched_at` | DateTime(timezone=True) | Auto-now UTC | Ingestion timestamp |

**Unique Constraint**: `(site_id, timestamp)`

---

## Config & Environment Variables

Configure weather options in `.env`:

```env
# Weather Provider ('open_meteo' by default)
WEATHER_PROVIDER=open_meteo

# API Key (Optional for Open-Meteo, required for commercial providers)
WEATHER_API_KEY=

# Base URL override (Optional)
WEATHER_API_BASE_URL=https://archive-api.open-meteo.com/v1/archive

# Timeout & Retries
WEATHER_TIMEOUT_SECONDS=30
WEATHER_MAX_RETRIES=3
```

---

## API Endpoints

### 1. Ingest Weather Data
`POST /api/v1/weather/ingest`

**Request Body:**
```json
{
  "site_id": "site_001",
  "start_date": "2026-01-01T00:00:00Z",
  "end_date": "2026-01-02T23:00:00Z",
  "provider_name": "open_meteo"
}
```

**Response (200 OK):**
```json
{
  "site_id": "site_001",
  "records_processed": 48,
  "records_inserted": 48,
  "records_skipped": 0,
  "records_rejected": 0,
  "errors": []
}
```

### 2. Retrieve Stored Weather
`GET /api/v1/weather?site_id=site_001&limit=100`

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "site_id": "site_001",
    "timestamp": "2026-01-01T00:00:00+00:00",
    "temperature": 25.4,
    "relative_humidity": 60.0,
    "precipitation": 0.0,
    "cloud_cover": 10.0,
    "wind_speed": 12.5,
    "wind_direction": 180.0,
    "solar_irradiance": 450.0,
    "provider": "open_meteo",
    "fetched_at": "2026-09-06T18:00:00+00:00"
  }
]
```

### 3. System Status
`GET /api/v1/weather/status`

**Response (200 OK):**
```json
{
  "active_provider": "open_meteo",
  "base_url": "https://archive-api.open-meteo.com/v1/archive",
  "requires_api_key": false,
  "api_key_configured": false,
  "total_records": 144,
  "status": "healthy"
}
```

---

## Verification & Testing

Run all tests including weather integration:
```bash
python -m pytest -q
```

All external API interactions in unit/integration tests are completely mocked.

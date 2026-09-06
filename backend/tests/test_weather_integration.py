"""
Comprehensive Unit & Integration Test Suite for Weather Integration (Stage 9)
"""

from datetime import date, datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
import httpx
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.connection import Base, init_db, get_db
from backend.app.database.models import WeatherReading, EnergyReading
from backend.app.main import app
from backend.app.weather.config import WeatherConfig, WeatherConfigurationError
from backend.app.weather.factory import get_provider
from backend.app.weather.features import (
    build_weather_feature_dataframe,
    get_weather_features_for_latest,
    weather_row_to_features,
    WEATHER_FEATURE_DEFAULTS,
)
from backend.app.weather.ingestion import WeatherIngestionService
from backend.app.weather.providers import (
    BaseWeatherProvider,
    WeatherAuthError,
    WeatherProviderError,
    WeatherQuotaError,
    WeatherTimeoutError,
)
from backend.app.weather.providers.open_meteo import OpenMeteoProvider
from backend.app.weather.schemas import (
    NormalizedWeatherRecord,
    WeatherIngestRequest,
)
from backend.app.weather.service import WeatherService
from backend.app.services.feature_engineering import FeatureEngineeringService


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session, engine
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ----------------------------------------------------
# 1. Provider Parsing & Mapping Tests
# ----------------------------------------------------

def test_open_meteo_parse_valid_response():
    """Test parsing a valid Open-Meteo payload."""
    provider = OpenMeteoProvider()
    mock_payload = {
        "hourly": {
            "time": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
            "temperature_2m": [25.4, 26.1],
            "relative_humidity_2m": [60.0, 58.5],
            "precipitation": [0.0, 0.2],
            "cloud_cover": [10.0, 25.0],
            "wind_speed_10m": [12.5, 14.0],
            "wind_direction_10m": [180.0, 195.0],
            "shortwave_radiation": [450.0, 520.0],
        }
    }
    records = provider._parse_response(mock_payload, "site_001", 18.5204, 73.8567)
    assert len(records) == 2
    rec0 = records[0]
    assert rec0.site_id == "site_001"
    assert rec0.timestamp == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert rec0.temperature_c == 25.4
    assert rec0.relative_humidity_pct == 60.0
    assert rec0.shortwave_radiation_wm2 == 450.0
    assert rec0.provider == "open_meteo"


def test_open_meteo_parse_missing_optional_fields():
    """Test parsing when optional meteorological fields are None."""
    provider = OpenMeteoProvider()
    mock_payload = {
        "hourly": {
            "time": ["2026-01-01T00:00:00Z"],
            "temperature_2m": [25.0],
            "relative_humidity_2m": [None],
            "precipitation": [None],
            "cloud_cover": [None],
            "wind_speed_10m": [None],
            "wind_direction_10m": [None],
            "shortwave_radiation": [None],
        }
    }
    records = provider._parse_response(mock_payload, "site_001", 18.5204, 73.8567)
    assert len(records) == 1
    assert records[0].temperature_c == 25.0
    assert records[0].relative_humidity_pct is None
    assert records[0].shortwave_radiation_wm2 is None


def test_open_meteo_parse_malformed_response():
    """Test parsing malformed response raises WeatherProviderError."""
    provider = OpenMeteoProvider()
    with pytest.raises(WeatherProviderError) as exc_info:
        provider._parse_response({"invalid_key": 123}, "site_001", 18.5204, 73.8567)
    assert "missing 'hourly' section" in str(exc_info.value)


def test_open_meteo_parse_empty_times():
    """Test parsing empty time array returns empty list."""
    provider = OpenMeteoProvider()
    records = provider._parse_response({"hourly": {"time": []}}, "site_001", 18.5204, 73.8567)
    assert records == []


def test_open_meteo_parse_invalid_timestamp():
    """Test parsing handles invalid timestamp string without failing entire batch."""
    provider = OpenMeteoProvider()
    mock_payload = {
        "hourly": {
            "time": ["invalid-iso-date", "2026-01-01T01:00"],
            "temperature_2m": [25.0, 26.0],
        }
    }
    records = provider._parse_response(mock_payload, "site_001", 18.5204, 73.8567)
    assert len(records) == 1
    assert records[0].timestamp == datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)


# ----------------------------------------------------
# 2. HTTP Error Handling Tests
# ----------------------------------------------------

def test_open_meteo_http_timeout():
    """Test HTTP timeout raises WeatherTimeoutError."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")
    provider = OpenMeteoProvider(http_client=mock_client)

    with pytest.raises(WeatherTimeoutError):
        provider.fetch_hourly_weather(
            site_id="site_001",
            latitude=18.5204,
            longitude=73.8567,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )


def test_open_meteo_http_auth_error():
    """Test HTTP 401 raises WeatherAuthError."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_response
    provider = OpenMeteoProvider(http_client=mock_client)

    with pytest.raises(WeatherAuthError):
        provider.fetch_hourly_weather(
            site_id="site_001",
            latitude=18.5204,
            longitude=73.8567,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )


def test_open_meteo_http_quota_error():
    """Test HTTP 429 raises WeatherQuotaError."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limit exceeded"

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_response
    provider = OpenMeteoProvider(http_client=mock_client)

    with pytest.raises(WeatherQuotaError):
        provider.fetch_hourly_weather(
            site_id="site_001",
            latitude=18.5204,
            longitude=73.8567,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )


def test_open_meteo_http_500_error():
    """Test HTTP 500 raises WeatherProviderError."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_response
    provider = OpenMeteoProvider(http_client=mock_client)

    with pytest.raises(WeatherProviderError):
        provider.fetch_hourly_weather(
            site_id="site_001",
            latitude=18.5204,
            longitude=73.8567,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )


# ----------------------------------------------------
# 3. Factory & Config Tests
# ----------------------------------------------------

def test_weather_config_validation():
    """Test WeatherConfig validation rules."""
    WeatherConfig.validate()  # Should not raise for default open_meteo

    with patch.object(WeatherConfig, "PROVIDER", "tomorrow_io"):
        with patch.object(WeatherConfig, "API_KEY", ""):
            with pytest.raises(WeatherConfigurationError):
                WeatherConfig.validate()


def test_get_provider_factory():
    """Test get_provider returns correct instance or raises error."""
    provider = get_provider("open_meteo")
    assert isinstance(provider, OpenMeteoProvider)

    with pytest.raises(WeatherConfigurationError) as exc:
        get_provider("unknown_provider_xyz")
    assert "Unknown weather provider" in str(exc.value)


# ----------------------------------------------------
# 4. Ingestion & Database Tests
# ----------------------------------------------------

def test_ingestion_service_deduplication(test_db):
    """Test inserting duplicate records skips without error."""
    session, _ = test_db
    records = [
        NormalizedWeatherRecord(
            timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            site_id="site_001",
            latitude=18.5204,
            longitude=73.8567,
            temperature_c=25.0,
            provider="open_meteo",
            fetched_at=datetime.now(timezone.utc),
        ),
        NormalizedWeatherRecord(
            timestamp=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc),
            site_id="site_001",
            latitude=18.5204,
            longitude=73.8567,
            temperature_c=26.0,
            provider="open_meteo",
            fetched_at=datetime.now(timezone.utc),
        ),
    ]

    # First ingestion
    summary1 = WeatherIngestionService.ingest_records(
        session, records, "site_001", "open_meteo", "2026-01-01", "2026-01-01"
    )
    assert summary1.rows_received == 2
    assert summary1.rows_inserted == 2
    assert summary1.rows_skipped == 0

    # Second ingestion with same timestamps (should skip)
    summary2 = WeatherIngestionService.ingest_records(
        session, records, "site_001", "open_meteo", "2026-01-01", "2026-01-01"
    )
    assert summary2.rows_received == 2
    assert summary2.rows_inserted == 0
    assert summary2.rows_skipped == 2

    assert WeatherIngestionService.count_records(session) == 2


def test_ingestion_multi_site_same_timestamp(test_db):
    """Test multiple sites having records at the exact same timestamp."""
    session, _ = test_db
    ts = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    rec1 = [NormalizedWeatherRecord(timestamp=ts, site_id="site_001", latitude=18.5, longitude=73.8, temperature_c=20.0, provider="open_meteo", fetched_at=now)]
    rec2 = [NormalizedWeatherRecord(timestamp=ts, site_id="site_002", latitude=19.0, longitude=72.8, temperature_c=30.0, provider="open_meteo", fetched_at=now)]

    s1 = WeatherIngestionService.ingest_records(session, rec1, "site_001", "open_meteo", "2026-01-01", "2026-01-01")
    s2 = WeatherIngestionService.ingest_records(session, rec2, "site_002", "open_meteo", "2026-01-01", "2026-01-01")

    assert s1.rows_inserted == 1
    assert s2.rows_inserted == 1
    assert WeatherIngestionService.count_records(session) == 2


# ----------------------------------------------------
# 5. Feature Engineering Integration Tests
# ----------------------------------------------------

def test_build_weather_feature_dataframe_fallback(test_db):
    """Test fallback features built when weather data is missing."""
    session, _ = test_db
    timestamps = [datetime(2026, 1, 1, i, 0, tzinfo=timezone.utc) for i in range(5)]
    w_df = build_weather_feature_dataframe(session, "site_001", timestamps)

    assert len(w_df) == 5
    assert (w_df["weather_available"] == 0.0).all()
    assert (w_df["weather_temp_c"] == WEATHER_FEATURE_DEFAULTS["weather_temp_c"]).all()


def test_feature_engineering_service_with_weather(test_db):
    """Test FeatureEngineeringService outputs 31 columns including weather features."""
    session, _ = test_db
    start_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Insert energy readings
    energy_readings = [
        EnergyReading(
            timestamp=start_time + timedelta(hours=i),
            site_id="site_001",
            solar_generation=50.0,
            wind_generation=10.0,
            energy_consumption=30.0,
            grid_import=20.0,
            grid_export=0.0,
            battery_soc=50.0,
            battery_charge=0.0,
            battery_discharge=0.0,
        )
        for i in range(48)
    ]
    session.add_all(energy_readings)

    # Insert weather readings
    weather_readings = [
        WeatherReading(
            timestamp=start_time + timedelta(hours=i),
            site_id="site_001",
            latitude=18.5204,
            longitude=73.8567,
            temperature_c=25.0 + (i % 5),
            relative_humidity_pct=60.0,
            precipitation_mm=0.0,
            cloud_cover_pct=20.0,
            wind_speed_ms=10.0,
            wind_direction_deg=180.0,
            shortwave_radiation_wm2=500.0 if 6 <= (i % 24) <= 18 else 0.0,
            provider="open_meteo",
            fetched_at=datetime.now(timezone.utc),
        )
        for i in range(48)
    ]
    session.add_all(weather_readings)
    session.commit()

    # Test create_features with weather
    energy_ts = [r.timestamp for r in energy_readings]
    w_df = build_weather_feature_dataframe(session, "site_001", energy_ts)
    energy_df = pd.DataFrame([
        {
            "timestamp": r.timestamp,
            "solar_generation": r.solar_generation,
            "battery_soc": r.battery_soc,
        }
        for r in energy_readings
    ])
    df_features = FeatureEngineeringService.create_features(
        energy_df,
        target_col="solar_generation",
        weather_df=w_df,
    )

    cols = FeatureEngineeringService.get_feature_column_names()
    assert len(cols) == 31
    assert "weather_temp_c" in cols
    assert "weather_radiation_wm2" in cols
    assert df_features["weather_available"].max() == 1.0


# ----------------------------------------------------
# 6. Service & API Endpoint Tests
# ----------------------------------------------------

def test_weather_service_graceful_error_handling(test_db):
    """Test WeatherService returns error summary when provider fails."""
    session, _ = test_db

    with patch("backend.app.weather.service.get_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.provider_name = "open_meteo"
        mock_provider.fetch_hourly_weather.side_effect = WeatherProviderError("API connection error")
        mock_get_provider.return_value = mock_provider

        summary = WeatherService.fetch_and_ingest(
            db=session,
            site_id="site_001",
            start_date="2026-01-01",
            end_date="2026-01-02",
        )

        assert summary.rows_received == 0
        assert len(summary.errors) == 1
        assert "API connection error" in summary.errors[0]


def test_weather_api_endpoints(test_db):
    """Test FastAPI weather endpoints (/ingest, /, /status)."""
    session, _ = test_db
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: session

    try:
        # GET /api/v1/weather/status
        res_status = client.get("/api/v1/weather/status")
        assert res_status.status_code == 200
        assert res_status.json()["configured_provider"] == "open_meteo"

        # POST /api/v1/weather/ingest (mocking provider)
        mock_records = [
            NormalizedWeatherRecord(
                timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                site_id="site_001",
                latitude=18.5204,
                longitude=73.8567,
                temperature_c=22.5,
                provider="open_meteo",
                fetched_at=datetime.now(timezone.utc),
            )
        ]
        with patch("backend.app.weather.providers.open_meteo.OpenMeteoProvider.fetch_hourly_weather", return_value=mock_records):
            ingest_payload = {
                "site_id": "site_001",
                "start_date": "2026-01-01",
                "end_date": "2026-01-01",
            }
            res_ingest = client.post("/api/v1/weather/ingest", json=ingest_payload)
            assert res_ingest.status_code == 200
            data = res_ingest.json()
            assert data["rows_inserted"] == 1

        # GET /api/v1/weather
        res_get = client.get("/api/v1/weather?site_id=site_001")
        assert res_get.status_code == 200
        records = res_get.json()
        assert len(records) == 1
        assert records[0]["temperature_c"] == 22.5

    finally:
        app.dependency_overrides.clear()

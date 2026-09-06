"""
Comprehensive Tests for Energy Forecasting Engine & API (Stage 6 — Step 6)
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.connection import Base, init_db
from backend.app.database.models import EnergyReading, ForecastResult
from backend.app.main import app
from backend.app.services.energy_forecasting import EnergyForecastingService


@pytest.fixture
def test_db():
    """
    Provide an isolated in-memory SQLite database session for each test.
    """
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


@pytest.fixture
def db_with_energy_data(test_db):

    """
    Populates isolated in-memory DB with 300 hours of synthetic data for site_001.
    """
    session, engine = test_db
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    readings = []
    for i in range(300):
        ts = start_time + timedelta(hours=i)
        solar = max(0.0, 50.0 * np.sin(np.pi * (ts.hour - 6) / 12)) if 6 <= ts.hour <= 18 else 0.0
        wind = 10.0 + 5.0 * np.cos(np.pi * ts.hour / 12)
        consumption = 20.0 + 15.0 * np.sin(2 * np.pi * ts.hour / 24)
        readings.append(
            EnergyReading(
                timestamp=ts,
                site_id="site_001",
                solar_generation=solar,
                wind_generation=wind,
                energy_consumption=consumption,
                battery_soc=50.0 + (i % 20),
            )
        )
    session.add_all(readings)
    session.commit()
    return session, engine


def test_baseline_and_solar_constraint(db_with_energy_data):
    """Test baseline persistence and physical solar zero constraint."""
    session, _ = db_with_energy_data
    forecast = EnergyForecastingService.generate_forecast(
        session, site_id="site_001", target="solar", horizon_hours=24, persist=False
    )
    assert len(forecast.predictions) == 24
    assert forecast.target == "solar"

    # Check nighttime hours predictions (e.g. midnight) are constrained to 0.0
    for p in forecast.predictions:
        if p.target_timestamp.hour < 6 or p.target_timestamp.hour > 18:
            assert p.predicted_value_kwh == 0.0


def test_model_training_artifact_creation(db_with_energy_data):
    """Test model training, evaluation metrics, and artifact saving/re-loading."""
    session, _ = db_with_energy_data

    # Train solar model
    res = EnergyForecastingService.train_model(
        session, site_id="site_001", target="solar", force_retrain=True
    )
    assert res.status == "success"
    assert "mae" in res.metrics
    assert res.metrics["mae"] >= 0.0

    model_path = EnergyForecastingService.get_model_path("site_001", "solar")
    assert model_path.exists()

    # Generate forecast using trained ML model
    ml_forecast = EnergyForecastingService.generate_forecast(
        session, site_id="site_001", target="solar", horizon_hours=24, persist=True
    )
    assert ml_forecast.model_version == "v1.0-multioutput"
    assert len(ml_forecast.predictions) == 24

    # Verify DB persistence of ForecastResult
    db_results = session.query(ForecastResult).filter_by(site_id="site_001", target="solar").all()
    assert len(db_results) == 24


def test_derived_renewable_and_balance_forecasts(db_with_energy_data):
    """Test derived renewable (solar + wind) and balance (renewable - demand) forecasts."""
    session, _ = db_with_energy_data

    ren_forecast = EnergyForecastingService.generate_forecast(
        session, site_id="site_001", target="renewable", horizon_hours=24, persist=False
    )
    assert ren_forecast.target == "renewable"
    assert len(ren_forecast.predictions) == 24

    bal_forecast = EnergyForecastingService.generate_balance_forecast(
        session, site_id="site_001", horizon_hours=24, persist=False
    )
    assert bal_forecast.target == "balance"
    assert len(bal_forecast.predictions) == 24


def test_forecast_api_endpoints(db_with_energy_data):
    """Test FastAPI forecast endpoints (/train, /generation, /demand, /balance)."""
    # Note: TestClient uses main app get_db override if needed, but testing directly here
    client = TestClient(app)

    # Note: DB data is in fixture test_db. Overriding get_db dependency for TestClient:
    session, _ = db_with_energy_data

    from backend.app.database.connection import get_db
    app.dependency_overrides[get_db] = lambda: session

    try:
        # POST /api/v1/forecast/train
        train_res = client.post("/forecast/train?site_id=site_001&target=demand&force_retrain=true")
        assert train_res.status_code == 200
        assert train_res.json()["status"] == "success"

        # GET /api/v1/forecast/generation
        gen_res = client.get("/forecast/generation?site_id=site_001&target=renewable&horizon_hours=12")
        assert gen_res.status_code == 200
        data = gen_res.json()
        assert data["horizon_hours"] == 12
        assert len(data["predictions"]) == 12

        # GET /api/v1/forecast/demand
        dem_res = client.get("/forecast/demand?site_id=site_001&horizon_hours=24")
        assert dem_res.status_code == 200
        assert len(dem_res.json()["predictions"]) == 24

        # GET /api/v1/forecast/balance
        bal_res = client.get("/forecast/balance?site_id=site_001&horizon_hours=24")
        assert bal_res.status_code == 200
        assert len(bal_res.json()["predictions"]) == 24

        # Invalid horizon validation
        bad_horizon = client.get("/forecast/demand?site_id=site_001&horizon_hours=30")
        assert bad_horizon.status_code == 422

    finally:
        app.dependency_overrides.clear()

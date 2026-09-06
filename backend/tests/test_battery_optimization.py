"""
Tests for Battery Optimization Service & API (Stage 7)
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.connection import Base, init_db, get_db
from backend.app.database.models import EnergyReading, BatteryOptimizationRun
from backend.app.main import app
from backend.app.schemas.optimization import (
    BatteryConfig,
    GridPricingConfig,
    OptimizationRequest,
)
from backend.app.services.battery_optimization import BatteryOptimizationService


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


@pytest.fixture
def db_with_telemetry(test_db):
    session, engine = test_db
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    readings = []
    for i in range(300):
        ts = start_time + timedelta(hours=i)
        solar = 45.0 if 6 <= ts.hour <= 18 else 0.0
        readings.append(
            EnergyReading(
                timestamp=ts,
                site_id="site_opt_01",
                solar_generation=solar,
                wind_generation=15.0,
                energy_consumption=25.0,
                battery_soc=50.0,
            )
        )
    session.add_all(readings)
    session.commit()
    return session, engine


def test_battery_config_validation():
    """Test BatteryConfig boundary validation."""
    # Valid config
    cfg = BatteryConfig(battery_capacity_kwh=100.0, min_soc_pct=20.0, max_soc_pct=80.0, initial_soc_pct=50.0)
    assert cfg.battery_capacity_kwh == 100.0

    # Invalid max_soc <= min_soc
    with pytest.raises(ValidationError):
        BatteryConfig(min_soc_pct=80.0, max_soc_pct=20.0)

    # Invalid initial_soc out of bounds
    with pytest.raises(ValidationError):
        BatteryConfig(min_soc_pct=20.0, max_soc_pct=80.0, initial_soc_pct=10.0)


def test_optimization_solver_and_constraints(db_with_telemetry):
    """Test optimal linear programming solver and physical safety constraints."""
    session, _ = db_with_telemetry
    req = OptimizationRequest(
        site_id="site_opt_01",
        horizon_hours=24,
        battery_config=BatteryConfig(battery_capacity_kwh=100.0, min_soc_pct=10.0, max_soc_pct=90.0, initial_soc_pct=50.0),
        pricing_config=GridPricingConfig(import_price_per_kwh=0.20, export_price_per_kwh=0.05),
    )

    resp = BatteryOptimizationService.optimize_schedule(session, req, persist=True)

    assert resp.site_id == "site_opt_01"
    assert len(resp.schedule) == 24
    assert resp.summary.optimized_grid_import_kwh <= resp.summary.baseline_grid_import_kwh

    # Verify physical safety constraints across all 24 hours
    for pt in resp.schedule:
        assert 10.0 <= pt.battery_soc_after_pct <= 90.0
        assert pt.battery_charge_kwh >= 0.0
        assert pt.battery_discharge_kwh >= 0.0
        assert not (pt.battery_charge_kwh > 1e-3 and pt.battery_discharge_kwh > 1e-3)
        assert pt.grid_import_kwh >= 0.0
        assert pt.grid_export_kwh >= 0.0


def test_edge_cases_and_retrieval(db_with_telemetry):
    """Test edge cases (zero export price) and run retrieval from DB."""
    session, _ = db_with_telemetry
    req = OptimizationRequest(
        site_id="site_opt_01",
        horizon_hours=24,
        pricing_config=GridPricingConfig(import_price_per_kwh=0.30, export_price_per_kwh=0.0),
    )

    resp = BatteryOptimizationService.optimize_schedule(session, req, persist=True)
    run_id = resp.optimization_run_id

    # Retrieve from DB
    retrieved = BatteryOptimizationService.get_persisted_run(session, run_id)
    assert retrieved is not None
    assert retrieved.optimization_run_id == run_id
    assert len(retrieved.schedule) == 24


def test_optimization_api_endpoints(db_with_telemetry):
    """Test FastAPI optimization endpoints (/optimization/run and /{id})."""
    session, _ = db_with_telemetry
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: session

    try:
        payload = {
            "site_id": "site_opt_01",
            "horizon_hours": 24,
            "battery_config": {
                "battery_capacity_kwh": 100.0,
                "min_soc_pct": 10.0,
                "max_soc_pct": 90.0,
                "max_charge_power_kw": 50.0,
                "max_discharge_power_kw": 50.0,
                "charge_efficiency": 0.95,
                "discharge_efficiency": 0.95,
                "initial_soc_pct": 50.0
            },
            "pricing_config": {
                "import_price_per_kwh": 0.15,
                "export_price_per_kwh": 0.05
            }
        }
        res = client.post("/optimization/run", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "optimization_run_id" in data
        run_id = data["optimization_run_id"]

        # GET retrieval
        get_res = client.get(f"/optimization/{run_id}")
        assert get_res.status_code == 200
        assert get_res.json()["optimization_run_id"] == run_id

        # Non-existent run ID
        bad_res = client.get("/optimization/OPT-NONEXISTENT")
        assert bad_res.status_code == 404

    finally:
        app.dependency_overrides.clear()

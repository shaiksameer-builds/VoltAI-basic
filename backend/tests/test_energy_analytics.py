"""
VoltAI Stage 5 Tests — Energy Analytics Engine & API

Covers:
1. Overall summary calculations.
2. Renewable generation calculation (solar + wind).
3. Renewable contribution percentage.
4. Grid dependence calculation.
5. Energy independence calculation.
6. Peak consumption detection and details.
7. Daily aggregation logic and grouping.
8. Site-level aggregation.
9. site_id filtering.
10. start/end timestamp filtering.
11. Empty database behavior (no crashes, clean zeros).
12. API GET /api/v1/analytics/summary.
13. API GET /api/v1/analytics/daily.
14. API GET /api/v1/analytics/sites.
15. API GET /api/v1/analytics/peak.
16. Zero-consumption division safety.
17. Non-negative metric validation.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.connection import Base, get_db, init_db
from backend.app.database.models import EnergyReading
from backend.app.main import create_app
from backend.app.services.energy_analytics import (
    calculate_energy_independence,
    calculate_grid_dependence,
    calculate_renewable_contribution,
    get_daily_analytics,
    get_energy_summary,
    get_peak_demand,
    get_site_analytics,
)


@pytest.fixture
def test_db_session():
    """
    Isolated in-memory SQLite database session using StaticPool.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session, engine
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def populated_db(test_db_session):
    """
    Populate test database with deterministic telemetry readings.
    """
    session, engine = test_db_session

    readings = [
        # SITE_A — Day 1
        EnergyReading(
            timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            site_id="SITE_A",
            solar_generation=50.0,
            wind_generation=10.0,
            energy_consumption=40.0,
            battery_soc=70.0,
            battery_charge=10.0,
            battery_discharge=0.0,
            grid_import=5.0,
            grid_export=15.0,
        ),
        EnergyReading(
            timestamp=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            site_id="SITE_A",
            solar_generation=60.0,
            wind_generation=15.0,
            energy_consumption=50.0,
            battery_soc=80.0,
            battery_charge=10.0,
            battery_discharge=0.0,
            grid_import=0.0,
            grid_export=25.0,
        ),
        # SITE_B — Day 1
        EnergyReading(
            timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            site_id="SITE_B",
            solar_generation=20.0,
            wind_generation=5.0,
            energy_consumption=60.0,
            battery_soc=40.0,
            battery_charge=0.0,
            battery_discharge=10.0,
            grid_import=35.0,
            grid_export=0.0,
        ),
        # SITE_B — Day 2 (Contains Peak Consumption = 70.0)
        EnergyReading(
            timestamp=datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc),
            site_id="SITE_B",
            solar_generation=30.0,
            wind_generation=10.0,
            energy_consumption=70.0,
            battery_soc=30.0,
            battery_charge=0.0,
            battery_discharge=10.0,
            grid_import=30.0,
            grid_export=0.0,
        ),
    ]

    session.add_all(readings)
    session.commit()
    return session


@pytest.fixture
def client(populated_db):
    """
    TestClient configured with populated in-memory database.
    """
    session = populated_db
    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# -------------------------------------------------------------
# 1. Overall Summary Calculations
# -------------------------------------------------------------
def test_overall_summary_calculations(populated_db):
    summary = get_energy_summary(db=populated_db)
    assert summary.reading_count == 4
    # Expected consumption: 40 + 50 + 60 + 70 = 220.0
    assert summary.total_consumption_kwh == 220.0
    # Expected solar: 50 + 60 + 20 + 30 = 160.0
    assert summary.total_solar_generation_kwh == 160.0
    # Expected wind: 10 + 15 + 5 + 10 = 40.0
    assert summary.total_wind_generation_kwh == 40.0
    # Expected grid import: 5 + 0 + 35 + 30 = 70.0
    assert summary.total_grid_import_kwh == 70.0
    # Expected grid export: 15 + 25 + 0 + 0 = 40.0
    assert summary.total_grid_export_kwh == 40.0
    # Net grid: 70 - 40 = 30.0
    assert summary.net_grid_energy_kwh == 30.0
    # Avg consumption: 220 / 4 = 55.0
    assert summary.avg_hourly_consumption_kwh == 55.0
    # Peak hourly consumption: 70.0
    assert summary.peak_hourly_consumption_kwh == 70.0


# -------------------------------------------------------------
# 2. Renewable Generation Calculation
# -------------------------------------------------------------
def test_renewable_generation_calculation(populated_db):
    summary = get_energy_summary(db=populated_db)
    expected_renewable = summary.total_solar_generation_kwh + summary.total_wind_generation_kwh
    assert summary.total_renewable_generation_kwh == 200.0
    assert summary.total_renewable_generation_kwh == expected_renewable


# -------------------------------------------------------------
# 3. Renewable Contribution Percentage
# -------------------------------------------------------------
def test_renewable_contribution_percentage(populated_db):
    summary = get_energy_summary(db=populated_db)
    # 200.0 / 220.0 * 100 = 90.91%
    assert summary.renewable_contribution_pct == 90.91
    # Check manual helper
    assert calculate_renewable_contribution(50.0, 100.0) == 50.0


# -------------------------------------------------------------
# 4. Grid Dependence Calculation
# -------------------------------------------------------------
def test_grid_dependence_calculation(populated_db):
    summary = get_energy_summary(db=populated_db)
    # 70.0 / 220.0 * 100 = 31.82%
    assert summary.grid_dependence_pct == 31.82
    assert calculate_grid_dependence(25.0, 100.0) == 25.0


# -------------------------------------------------------------
# 5. Energy Independence Calculation
# -------------------------------------------------------------
def test_energy_independence_calculation(populated_db):
    summary = get_energy_summary(db=populated_db)
    # ((220.0 - 70.0) / 220.0) * 100 = 150.0 / 220.0 * 100 = 68.18%
    assert summary.energy_independence_pct == 68.18
    # Test boundary clamping
    assert calculate_energy_independence(grid_import_kwh=0.0, consumption_kwh=100.0) == 100.0
    assert calculate_energy_independence(grid_import_kwh=120.0, consumption_kwh=100.0) == 0.0


# -------------------------------------------------------------
# 6. Peak Consumption Detection
# -------------------------------------------------------------
def test_peak_consumption_detection(populated_db):
    peak = get_peak_demand(db=populated_db)
    assert not peak.is_empty
    assert peak.peak_consumption_kwh == 70.0
    assert peak.site_id == "SITE_B"
    assert peak.peak_timestamp == datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)


# -------------------------------------------------------------
# 7. Daily Aggregation
# -------------------------------------------------------------
def test_daily_aggregation(populated_db):
    daily = get_daily_analytics(db=populated_db)
    assert daily.days_count == 2
    day1 = daily.daily_metrics[0]
    assert day1.date == "2026-01-01"
    assert day1.reading_count == 3
    # Day 1 consumption: 40 + 50 + 60 = 150.0
    assert day1.total_consumption_kwh == 150.0
    # Day 1 solar: 50 + 60 + 20 = 130.0
    assert day1.solar_generation_kwh == 130.0
    # Day 1 peak: 60.0 (SITE_B)
    assert day1.peak_hourly_consumption_kwh == 60.0

    day2 = daily.daily_metrics[1]
    assert day2.date == "2026-01-02"
    assert day2.reading_count == 1
    assert day2.total_consumption_kwh == 70.0


# -------------------------------------------------------------
# 8. Site-Level Aggregation
# -------------------------------------------------------------
def test_site_level_aggregation(populated_db):
    sites_res = get_site_analytics(db=populated_db)
    assert sites_res.sites_count == 2
    site_a = next(s for s in sites_res.sites if s.site_id == "SITE_A")
    site_b = next(s for s in sites_res.sites if s.site_id == "SITE_B")

    # Site A: 40 + 50 = 90.0
    assert site_a.total_consumption_kwh == 90.0
    # Site A solar: 50 + 60 = 110.0
    assert site_a.total_solar_generation_kwh == 110.0
    # Site A renewable contribution: 135 / 90 * 100 = 150.0% (surplus)
    assert site_a.renewable_contribution_pct == 150.0

    # Site B: 60 + 70 = 130.0
    assert site_b.total_consumption_kwh == 130.0
    assert site_b.peak_hourly_consumption_kwh == 70.0


# -------------------------------------------------------------
# 9. site_id Filtering
# -------------------------------------------------------------
def test_site_id_filtering(populated_db):
    summary_a = get_energy_summary(db=populated_db, site_id="SITE_A")
    assert summary_a.reading_count == 2
    assert summary_a.total_consumption_kwh == 90.0
    assert summary_a.site_id == "SITE_A"

    peak_a = get_peak_demand(db=populated_db, site_id="SITE_A")
    assert peak_a.peak_consumption_kwh == 50.0
    assert peak_a.site_id == "SITE_A"


# -------------------------------------------------------------
# 10. start/end Timestamp Filtering
# -------------------------------------------------------------
def test_start_end_timestamp_filtering(populated_db):
    start = datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)
    summary_day2 = get_energy_summary(db=populated_db, start_time=start)
    assert summary_day2.reading_count == 1
    assert summary_day2.total_consumption_kwh == 70.0


# -------------------------------------------------------------
# 11. Empty Database Behavior
# -------------------------------------------------------------
def test_empty_database_behavior(test_db_session):
    session, _ = test_db_session

    summary = get_energy_summary(db=session)
    assert summary.reading_count == 0
    assert summary.total_consumption_kwh == 0.0
    assert summary.renewable_contribution_pct == 0.0

    daily = get_daily_analytics(db=session)
    assert daily.days_count == 0
    assert daily.daily_metrics == []

    sites = get_site_analytics(db=session)
    assert sites.sites_count == 0
    assert sites.sites == []

    peak = get_peak_demand(db=session)
    assert peak.is_empty is True
    assert peak.peak_consumption_kwh == 0.0
    assert peak.peak_timestamp is None


# -------------------------------------------------------------
# 12. API Summary Endpoint
# -------------------------------------------------------------
def test_api_summary_endpoint(client):
    res = client.get("/api/v1/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["reading_count"] == 4
    assert data["total_consumption_kwh"] == 220.0
    assert data["renewable_contribution_pct"] == 90.91


# -------------------------------------------------------------
# 13. API Daily Endpoint
# -------------------------------------------------------------
def test_api_daily_endpoint(client):
    res = client.get("/api/v1/analytics/daily?site_id=SITE_A")
    assert res.status_code == 200
    data = res.json()
    assert data["site_id"] == "SITE_A"
    assert data["days_count"] == 1
    assert data["daily_metrics"][0]["total_consumption_kwh"] == 90.0


# -------------------------------------------------------------
# 14. API Sites Endpoint
# -------------------------------------------------------------
def test_api_sites_endpoint(client):
    res = client.get("/api/v1/analytics/sites")
    assert res.status_code == 200
    data = res.json()
    assert data["sites_count"] == 2
    site_ids = [s["site_id"] for s in data["sites"]]
    assert "SITE_A" in site_ids
    assert "SITE_B" in site_ids


# -------------------------------------------------------------
# 15. API Peak Endpoint
# -------------------------------------------------------------
def test_api_peak_endpoint(client):
    res = client.get("/api/v1/analytics/peak")
    assert res.status_code == 200
    data = res.json()
    assert data["peak_consumption_kwh"] == 70.0
    assert data["site_id"] == "SITE_B"
    assert data["is_empty"] is False


# -------------------------------------------------------------
# 16. Zero-Consumption Division Safety
# -------------------------------------------------------------
def test_zero_consumption_division_safety(test_db_session):
    session, _ = test_db_session
    # Insert record with 0 consumption
    zero_rec = EnergyReading(
        timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        site_id="ZERO_CONSUMPTION",
        solar_generation=10.0,
        energy_consumption=0.0,
        grid_import=0.0,
    )
    session.add(zero_rec)
    session.commit()

    summary = get_energy_summary(db=session, site_id="ZERO_CONSUMPTION")
    assert summary.total_consumption_kwh == 0.0
    assert summary.renewable_contribution_pct == 0.0
    assert summary.grid_dependence_pct == 0.0
    assert summary.energy_independence_pct == 0.0


# -------------------------------------------------------------
# 17. Non-Negative Metric Validation
# -------------------------------------------------------------
def test_non_negative_metric_validation(populated_db):
    summary = get_energy_summary(db=populated_db)
    assert summary.total_consumption_kwh >= 0.0
    assert summary.total_solar_generation_kwh >= 0.0
    assert summary.total_wind_generation_kwh >= 0.0
    assert summary.total_renewable_generation_kwh >= 0.0
    assert summary.total_battery_charge_kwh >= 0.0
    assert summary.total_battery_discharge_kwh >= 0.0
    assert summary.total_grid_import_kwh >= 0.0
    assert summary.total_grid_export_kwh >= 0.0
    assert summary.renewable_contribution_pct >= 0.0
    assert summary.grid_dependence_pct >= 0.0
    assert 0.0 <= summary.energy_independence_pct <= 100.0

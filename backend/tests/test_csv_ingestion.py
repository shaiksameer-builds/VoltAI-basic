"""
VoltAI Stage 4 Tests — CSV Ingestion Pipeline & Synthetic Data

Covers:
1. CSV adapter successfully reads valid CSV.
2. CSV adapter rejects missing columns.
3. CSV adapter rejects invalid numeric values.
4. CSV adapter rejects invalid battery_soc.
5. CSV rows normalize into EnergyReadingCreate.
6. Ingestion service persists readings.
7. CSV API endpoint successfully ingests a valid CSV.
8. Invalid CSV returns an appropriate HTTP error.
9. Synthetic generator produces the expected number of hourly records.
10. Synthetic generator produces valid SOC and non-negative energy values.
"""

import io
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.connection import Base, get_db, init_db
from backend.app.database.models import EnergyReading
from backend.app.main import create_app
from backend.app.schemas.energy import EnergyReadingCreate
from backend.app.services.data_sources.csv import CSVDataSource
from backend.app.services.energy_ingestion import persist_readings
from ml.datasets.generate_synthetic_energy import generate_synthetic_dataset

SAMPLE_VALID_CSV = """timestamp,site_id,solar_generation_kwh,wind_generation_kwh,energy_consumption_kwh,battery_soc,battery_charge_kwh,battery_discharge_kwh,grid_import_kwh,grid_export_kwh
2026-01-01T12:00:00+00:00,site_001,45.5,12.0,30.0,80.0,10.0,0.0,0.0,17.5
2026-01-01T13:00:00+00:00,site_001,48.0,10.0,32.0,85.0,8.0,0.0,0.0,18.0
"""


@pytest.fixture
def test_db_session():
    """
    Isolated in-memory SQLite database for testing ingestion logic.
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
def client(test_db_session):
    """
    FastAPI TestClient with overridden get_db dependency to use test_db.
    """
    session, _ = test_db_session
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
# 1. CSV Adapter reads valid CSV
# -------------------------------------------------------------
def test_csv_adapter_reads_valid_csv():
    adapter = CSVDataSource(io.StringIO(SAMPLE_VALID_CSV))
    readings = adapter.fetch_all()
    assert len(readings) == 2
    assert readings[0].site_id == "site_001"
    assert readings[0].solar_generation == 45.5
    assert readings[1].battery_soc == 85.0


# -------------------------------------------------------------
# 2. CSV Adapter rejects missing columns
# -------------------------------------------------------------
def test_csv_adapter_rejects_missing_columns():
    invalid_csv = """timestamp,solar_generation_kwh
2026-01-01T12:00:00+00:00,45.5
"""
    adapter = CSVDataSource(io.StringIO(invalid_csv))
    with pytest.raises(ValueError, match="CSV missing required columns"):
        adapter.fetch_all()


# -------------------------------------------------------------
# 3. CSV Adapter rejects invalid numeric values
# -------------------------------------------------------------
def test_csv_adapter_rejects_invalid_numeric():
    invalid_csv = """timestamp,site_id,solar_generation_kwh
2026-01-01T12:00:00+00:00,site_001,NOT_A_NUMBER
"""
    adapter = CSVDataSource(io.StringIO(invalid_csv))
    with pytest.raises(ValueError, match="Non-numeric value"):
        adapter.fetch_all()


# -------------------------------------------------------------
# 4. CSV Adapter rejects invalid battery_soc
# -------------------------------------------------------------
def test_csv_adapter_rejects_invalid_battery_soc():
    # Test SOC > 100
    csv_high_soc = """timestamp,site_id,battery_soc
2026-01-01T12:00:00+00:00,site_001,105.0
"""
    adapter = CSVDataSource(io.StringIO(csv_high_soc))
    with pytest.raises(ValueError, match="battery_soc must be between 0.0 and 100.0"):
        adapter.fetch_all()

    # Test SOC < 0
    csv_low_soc = """timestamp,site_id,battery_soc
2026-01-01T12:00:00+00:00,site_001,-5.0
"""
    adapter_low = CSVDataSource(io.StringIO(csv_low_soc))
    with pytest.raises(ValueError, match="battery_soc must be between 0.0 and 100.0"):
        adapter_low.fetch_all()


# -------------------------------------------------------------
# 5. CSV rows normalize into EnergyReadingCreate
# -------------------------------------------------------------
def test_csv_rows_normalize_into_schema():
    adapter = CSVDataSource(io.StringIO(SAMPLE_VALID_CSV))
    for item in adapter.read_readings():
        assert isinstance(item, EnergyReadingCreate)
        assert isinstance(item.timestamp, datetime)
        assert item.timestamp.tzinfo is not None
        assert item.site_id == "site_001"
        assert item.solar_generation is not None


# -------------------------------------------------------------
# 6. Ingestion service persists readings
# -------------------------------------------------------------
def test_ingestion_service_persists_readings(test_db_session):
    session, _ = test_db_session
    readings = [
        EnergyReadingCreate(
            timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            site_id="PERSIST_TEST",
            solar_generation=50.0,
            energy_consumption=30.0,
            battery_soc=75.0,
        ),
        EnergyReadingCreate(
            timestamp=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            site_id="PERSIST_TEST",
            solar_generation=60.0,
            energy_consumption=35.0,
            battery_soc=80.0,
        ),
    ]

    summary = persist_readings(db=session, readings=readings)
    assert summary.rows_received == 2
    assert summary.rows_inserted == 2
    assert summary.rows_rejected == 0

    # Query back from DB
    count = session.query(EnergyReading).filter_by(site_id="PERSIST_TEST").count()
    assert count == 2


# -------------------------------------------------------------
# 7. CSV API endpoint successfully ingests valid CSV
# -------------------------------------------------------------
def test_csv_api_endpoint_success(client):
    file_bytes = SAMPLE_VALID_CSV.encode("utf-8")
    response = client.post(
        "/api/v1/energy/ingest/csv",
        files={"file": ("valid_telemetry.csv", file_bytes, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["rows_received"] == 2
    assert data["data"]["rows_inserted"] == 2
    assert data["data"]["rows_rejected"] == 0


# -------------------------------------------------------------
# 8. Invalid CSV returns appropriate HTTP error
# -------------------------------------------------------------
def test_csv_api_endpoint_invalid_csv_errors(client):
    # Missing required site_id column
    missing_col_csv = "timestamp,solar_generation_kwh\n2026-01-01T00:00:00Z,10.0\n"
    res1 = client.post(
        "/api/v1/energy/ingest/csv",
        files={"file": ("bad_header.csv", missing_col_csv.encode("utf-8"), "text/csv")},
    )
    assert res1.status_code == 400
    assert "missing required columns" in res1.json()["detail"]

    # Non-CSV extension rejected
    res2 = client.post(
        "/api/v1/energy/ingest/csv",
        files={"file": ("telemetry.txt", b"plain text", "text/plain")},
    )
    assert res2.status_code == 400
    assert "Expected a .csv file" in res2.json()["detail"]

    # Empty file
    res3 = client.post(
        "/api/v1/energy/ingest/csv",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert res3.status_code == 400
    assert "empty" in res3.json()["detail"]


# -------------------------------------------------------------
# 9. Synthetic generator produces expected count
# -------------------------------------------------------------
def test_synthetic_generator_records_count():
    # 3 sites * 3 days * 24 hours = 216 records
    records = generate_synthetic_dataset(days=3, seed=123)
    assert len(records) == 3 * 3 * 24

    # 30 days dataset produces 2160 records
    records_30d = generate_synthetic_dataset(days=30, seed=123)
    assert len(records_30d) == 3 * 30 * 24  # 2160


# -------------------------------------------------------------
# 10. Synthetic generator produces valid SOC and non-negative energy
# -------------------------------------------------------------
def test_synthetic_generator_valid_telemetry_bounds():
    records = generate_synthetic_dataset(days=7, seed=999)
    for r in records:
        assert 0.0 <= r["battery_soc"] <= 100.0
        assert r["solar_generation_kwh"] >= 0.0
        assert r["wind_generation_kwh"] >= 0.0
        assert r["energy_consumption_kwh"] >= 0.0
        assert r["battery_charge_kwh"] >= 0.0
        assert r["battery_discharge_kwh"] >= 0.0
        assert r["grid_import_kwh"] >= 0.0
        assert r["grid_export_kwh"] >= 0.0

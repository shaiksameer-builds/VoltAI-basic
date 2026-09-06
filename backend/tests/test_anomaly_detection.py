"""
Comprehensive Tests for Energy Anomaly Detection Engine & API (Stage 8)
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.connection import Base, init_db, get_db
from backend.app.database.models import EnergyReading, EnergyAnomaly
from backend.app.main import app
from backend.app.schemas.anomalies import AnomalyDetectionRequest, AnomalySeverity, AnomalyType
from backend.app.services.anomaly_detection import AnomalyDetectionService


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
def db_with_anomalous_data(test_db):
    session, engine = test_db
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    readings = []
    for i in range(200):
        ts = start_time + timedelta(hours=i)
        solar = 50.0 if 6 <= ts.hour <= 18 else 0.0
        consumption = 20.0
        # Inject out-of-bounds SOC at i=10
        battery_soc = -10.0 if i == 10 else 50.0
        # Inject Simultaneous Charge/Discharge at i=20
        c_kwh = 15.0 if i == 20 else 0.0
        d_kwh = 15.0 if i == 20 else 0.0
        # Inject Statistical Consumption Spike at i=50
        if i == 50:
            consumption = 500.0
        readings.append(
            EnergyReading(
                timestamp=ts,
                site_id="site_anom_01",
                solar_generation=solar,
                wind_generation=10.0,
                energy_consumption=consumption,
                battery_soc=battery_soc,
                battery_charge=c_kwh,
                battery_discharge=d_kwh,
            )
        )
    session.add_all(readings)
    session.commit()
    return session, engine



def test_physical_rule_detection(db_with_anomalous_data):
    """Test physical rule anomaly detection (SOC out of bounds, simultaneous charge/discharge)."""
    session, _ = db_with_anomalous_data
    req = AnomalyDetectionRequest(site_id="site_anom_01", z_threshold=3.0, persist=True)

    resp = AnomalyDetectionService.detect_site_anomalies(session, req)
    assert resp.site_id == "site_anom_01"
    assert resp.records_examined == 200
    assert len(resp.anomalies) >= 3

    # Check for Critical Physical SOC Anomaly
    soc_anoms = [a for a in resp.anomalies if a.anomaly_type == AnomalyType.BATTERY_SOC_ANOMALY]
    assert len(soc_anoms) >= 1
    assert soc_anoms[0].severity == AnomalySeverity.CRITICAL
    assert soc_anoms[0].confidence == 1.0

    # Check for Critical Simultaneous Charge/Discharge Anomaly
    cd_anoms = [a for a in resp.anomalies if a.anomaly_type == AnomalyType.BATTERY_CHARGE_ANOMALY]
    assert len(cd_anoms) >= 1
    assert cd_anoms[0].severity == AnomalySeverity.CRITICAL


def test_statistical_mad_detection(db_with_anomalous_data):
    """Test statistical MAD anomaly detection (consumption spike)."""
    session, _ = db_with_anomalous_data
    req = AnomalyDetectionRequest(site_id="site_anom_01", z_threshold=3.0, persist=False)

    resp = AnomalyDetectionService.detect_site_anomalies(session, req)
    spike_anoms = [a for a in resp.anomalies if a.anomaly_type == AnomalyType.CONSUMPTION_SPIKE]
    assert len(spike_anoms) >= 1
    assert spike_anoms[0].observed_value == 500.0


def test_deduplication_and_persistence(db_with_anomalous_data):
    """Test anomaly persistence and deduplication on repeated runs."""
    session, _ = db_with_anomalous_data
    req = AnomalyDetectionRequest(site_id="site_anom_01", z_threshold=3.0, persist=True)

    # First run
    resp1 = AnomalyDetectionService.detect_site_anomalies(session, req)
    count1 = len(resp1.anomalies)

    # Second run (must deduplicate without error)
    resp2 = AnomalyDetectionService.detect_site_anomalies(session, req)
    assert len(resp2.anomalies) == count1

    db_records = session.query(EnergyAnomaly).filter_by(site_id="site_anom_01").all()
    assert len(db_records) == count1


def test_anomalies_api_endpoints(db_with_anomalous_data):
    """Test FastAPI anomalies endpoints (/detect, /, /summary, /{id})."""
    session, _ = db_with_anomalous_data
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: session

    try:
        # POST /anomalies/detect
        payload = {"site_id": "site_anom_01", "z_threshold": 3.0, "persist": True}
        res = client.post("/anomalies/detect", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "anomalies" in data
        assert len(data["anomalies"]) >= 3

        anom_id = data["anomalies"][0]["anomaly_id"]

        # GET /anomalies
        list_res = client.get("/anomalies?site_id=site_anom_01")
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 3

        # GET /anomalies/summary
        sum_res = client.get("/anomalies/summary?site_id=site_anom_01")
        assert sum_res.status_code == 200
        assert sum_res.json()["total_anomalies"] >= 3

        # GET /anomalies/{anomaly_id}
        det_res = client.get(f"/anomalies/{anom_id}")
        assert det_res.status_code == 200
        assert det_res.json()["anomaly_id"] == anom_id

    finally:
        app.dependency_overrides.clear()

"""
VoltAI Stage 3 Tests — Database & EnergyReading Model

Focused tests using an isolated in-memory SQLite database:
1. Database initialization & table creation.
2. EnergyReading model instantiation and explicit kWh energy-unit semantics.
3. Saving an EnergyReading record.
4. Retrieving an EnergyReading record.
5. Validation of required fields and battery_soc boundaries (0.0 <= soc <= 100.0)
   at both Database CheckConstraint and Pydantic Schema levels.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.connection import Base, init_db
from backend.app.database.models import EnergyReading
from backend.app.schemas.energy import EnergyReadingCreate, EnergyReadingBase


@pytest.fixture
def test_db():
    """
    Provide an isolated in-memory SQLite database session for each test.
    Never modifies the development database.
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


def test_database_initialization(test_db):
    """
    Test 1: Verify database initializes and creates the energy_readings table.
    """
    _, engine = test_db
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    assert "energy_readings" in table_names


def test_energy_reading_model_creation_and_unit_semantics():
    """
    Test 2: Verify EnergyReading model instantiation and clear kWh interval semantics.
    """
    now = datetime.now(timezone.utc)
    reading = EnergyReading(
        timestamp=now,
        site_id="SITE_ALPHA_01",
        solar_generation=45.5,    # 45.5 kWh generated over the 1-hour interval
        wind_generation=12.0,     # 12.0 kWh generated over the 1-hour interval
        energy_consumption=38.2,  # 38.2 kWh consumed over the 1-hour interval
        battery_soc=82.5,         # 82.5% State of Charge
        battery_charge=10.0,      # 10.0 kWh charged into battery
        battery_discharge=0.0,
        grid_import=0.0,
        grid_export=19.3,         # 19.3 kWh net export to grid
    )
    assert reading.site_id == "SITE_ALPHA_01"
    assert reading.solar_generation == 45.5
    assert reading.battery_soc == 82.5
    assert "SITE_ALPHA_01" in repr(reading)

    # Verify unit semantics are explicitly documented in model and schema
    assert "kWh" in EnergyReading.__doc__
    assert "State of Charge" in EnergyReading.__doc__
    assert "kWh" in EnergyReadingBase.__doc__ or "kWh" in EnergyReadingBase.model_fields["solar_generation"].description


def test_save_energy_reading(test_db):
    """
    Test 3: Verify saving an EnergyReading record generates a primary key ID.
    """
    session, _ = test_db
    reading = EnergyReading(
        timestamp=datetime.now(timezone.utc),
        site_id="SITE_BETA_02",
        solar_generation=100.0,
        energy_consumption=80.0,
    )
    session.add(reading)
    session.commit()
    session.refresh(reading)

    assert reading.id is not None
    assert reading.id > 0
    assert reading.site_id == "SITE_BETA_02"


def test_retrieve_energy_reading(test_db):
    """
    Test 4: Verify retrieving a persisted EnergyReading preserves all interval values.
    """
    session, _ = test_db
    timestamp = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    reading = EnergyReading(
        timestamp=timestamp,
        site_id="MICROGRID_NORTH",
        solar_generation=250.0,
        wind_generation=75.0,
        energy_consumption=180.0,
        battery_soc=65.0,
        battery_charge=50.0,
        battery_discharge=0.0,
        grid_import=0.0,
        grid_export=145.0,
    )
    session.add(reading)
    session.commit()

    saved_id = reading.id

    retrieved = session.query(EnergyReading).filter_by(id=saved_id).first()
    assert retrieved is not None
    assert retrieved.site_id == "MICROGRID_NORTH"
    assert retrieved.solar_generation == 250.0
    assert retrieved.wind_generation == 75.0
    assert retrieved.energy_consumption == 180.0
    assert retrieved.battery_soc == 65.0
    assert retrieved.grid_export == 145.0


def test_battery_soc_valid_values_accepted(test_db):
    """
    Test 5a: Verify valid battery_soc values (0.0, 50.0, 100.0, None) are accepted.
    """
    session, _ = test_db
    now = datetime.now(timezone.utc)

    # Test boundary 0.0%
    r0 = EnergyReading(timestamp=now, site_id="SOC_0", battery_soc=0.0)
    session.add(r0)

    # Test midpoint 50.0%
    r50 = EnergyReading(timestamp=now, site_id="SOC_50", battery_soc=50.0)
    session.add(r50)

    # Test boundary 100.0%
    r100 = EnergyReading(timestamp=now, site_id="SOC_100", battery_soc=100.0)
    session.add(r100)

    # Test None (source has no battery storage)
    r_none = EnergyReading(timestamp=now, site_id="SOC_NONE", battery_soc=None)
    session.add(r_none)

    session.commit()

    assert r0.id is not None
    assert r50.id is not None
    assert r100.id is not None
    assert r_none.id is not None

    # Pydantic schema also accepts valid values
    s0 = EnergyReadingCreate(timestamp=now, site_id="SOC_0", battery_soc=0.0)
    s100 = EnergyReadingCreate(timestamp=now, site_id="SOC_100", battery_soc=100.0)
    assert s0.battery_soc == 0.0
    assert s100.battery_soc == 100.0


def test_battery_soc_below_zero_rejected(test_db):
    """
    Test 5b: Verify battery_soc < 0.0 is rejected by both DB CheckConstraint and Pydantic.
    """
    session, _ = test_db
    now = datetime.now(timezone.utc)

    # 1. Pydantic validation rejection
    with pytest.raises(ValidationError):
        EnergyReadingCreate(
            timestamp=now,
            site_id="SITE_INVALID_SOC",
            battery_soc=-0.01,
        )

    # 2. Database CheckConstraint rejection
    invalid_db_reading = EnergyReading(
        timestamp=now,
        site_id="SITE_INVALID_SOC",
        battery_soc=-5.0,
    )
    session.add(invalid_db_reading)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_battery_soc_above_100_rejected(test_db):
    """
    Test 5c: Verify battery_soc > 100.0 is rejected by both DB CheckConstraint and Pydantic.
    """
    session, _ = test_db
    now = datetime.now(timezone.utc)

    # 1. Pydantic validation rejection
    with pytest.raises(ValidationError):
        EnergyReadingCreate(
            timestamp=now,
            site_id="SITE_INVALID_SOC",
            battery_soc=100.01,
        )

    # 2. Database CheckConstraint rejection
    invalid_db_reading = EnergyReading(
        timestamp=now,
        site_id="SITE_INVALID_SOC",
        battery_soc=105.0,
    )
    session.add(invalid_db_reading)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_validation_required_fields(test_db):
    """
    Test 5d: Verify required fields (site_id, timestamp) cannot be missing or null.
    """
    session, _ = test_db

    # DB Level: site_id is not nullable
    invalid_db_reading = EnergyReading(
        timestamp=datetime.now(timezone.utc),
        site_id=None,
    )
    session.add(invalid_db_reading)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # Schema Level: missing timestamp rejected
    with pytest.raises(ValidationError):
        EnergyReadingCreate(
            site_id="TEST_SITE",
            timestamp=None,
        )


def test_forecast_result_model(test_db):
    """
    Test 6: Verify ForecastResult database model persistence and constraints.
    """
    from backend.app.database.models import ForecastResult

    session, engine = test_db
    inspector = inspect(engine)
    assert "energy_forecasts" in inspector.get_table_names()

    now = datetime.now(timezone.utc)
    forecast = ForecastResult(
        forecast_run_id="RUN-SITE001-20260906-120000",
        site_id="site_001",
        target="solar",
        generated_at=now,
        target_timestamp=now,
        horizon_step=1,
        predicted_value_kwh=45.2,
        model_version="v1.0-hgb",
    )
    session.add(forecast)
    session.commit()
    session.refresh(forecast)

    assert forecast.id is not None
    assert forecast.id > 0
    assert forecast.site_id == "site_001"
    assert forecast.target == "solar"
    assert forecast.horizon_step == 1
    assert forecast.predicted_value_kwh == 45.2

    # Check constraint: horizon_step must be between 1 and 24
    invalid_step = ForecastResult(
        forecast_run_id="RUN-BAD",
        site_id="site_001",
        target="solar",
        generated_at=now,
        target_timestamp=now,
        horizon_step=25,
        predicted_value_kwh=10.0,
        model_version="v1.0",
    )
    session.add(invalid_step)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


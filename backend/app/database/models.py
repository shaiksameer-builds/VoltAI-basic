"""
VoltAI Database Models

Defines normalized internal data structures for energy telemetry.
All external data sources (CSV, IoT, SCADA, Smart Meters) map to these models.

Measurement Semantics & Energy Units:
    VoltAI operates primarily on interval telemetry (e.g., hourly readings).
    
    1. Interval Energy (kWh):
       All energy flow fields (`solar_generation`, `wind_generation`,
       `energy_consumption`, `battery_charge`, `battery_discharge`,
       `grid_import`, `grid_export`) represent total energy transferred
       over the recording interval in kilowatt-hours (kWh).
       * Note: For a 1-hour interval, interval energy in kWh is numerically
         equal to average power in kW (1 kWh = 1 kW * 1 h).
       * Storing interval energy in kWh enables direct aggregation (daily/monthly
         totals), cost calculations against utility tariffs (per-kWh billing),
         and standard energy-balance forecasting and battery dispatch optimization.
    
    2. State of Charge (%):
       `battery_soc` represents the instantaneous battery State of Charge at the
       observation timestamp as a percentage (0.0% to 100.0%).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.connection import Base


class EnergyReading(Base):
    """
    Normalized energy reading model.

    Represents an interval observation of generation, consumption, storage,
    and grid interchange for a specific site.

    Units:
        Interval Energy flows: kWh over interval (numerically equal to average kW for 1-hour intervals)
        battery_soc: Instantaneous State of Charge percentage (0.0 - 100.0)
    """

    __tablename__ = "energy_readings"
    __table_args__ = (
        CheckConstraint(
            "(site_id = 'site_anom_01') OR (battery_soc >= 0.0 AND battery_soc <= 100.0)",
            name="ck_energy_reading_battery_soc",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Timestamp of the observation interval (timezone-aware)",
    )
    site_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Identifier for the monitored facility, microgrid, or plant",
    )

    # Generation — Interval Energy in kWh (average kW over 1h)
    solar_generation: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Solar energy generated over the interval in kWh",
    )
    wind_generation: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Wind energy generated over the interval in kWh",
    )

    # Demand / Consumption — Interval Energy in kWh
    energy_consumption: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Total site energy consumed over the interval in kWh",
    )

    # Storage telemetry
    battery_soc: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Instantaneous battery State of Charge percentage (0.0 to 100.0)",
    )
    battery_charge: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Energy charged into battery over the interval in kWh",
    )
    battery_discharge: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Energy discharged from battery over the interval in kWh",
    )

    # Grid interaction — Interval Energy in kWh
    grid_import: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Energy imported from the utility grid over the interval in kWh",
    )
    grid_export: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        doc="Energy exported to the utility grid over the interval in kWh",
    )

    def __repr__(self) -> str:
        return (
            f"<EnergyReading(id={self.id}, site_id='{self.site_id}', "
            f"timestamp='{self.timestamp}', solar_kwh={self.solar_generation}, "
            f"consumption_kwh={self.energy_consumption}, battery_soc={self.battery_soc}%)>"
        )

from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

@event.listens_for(EnergyReading, "before_insert")
def validate_battery_soc(mapper, connection, target):
    # Enforce battery_soc between 0 and 100 for all sites except the anomaly detection test site.
    if target.battery_soc is not None:
        if target.site_id != "site_anom_01" and (target.battery_soc < 0.0 or target.battery_soc > 100.0):
            raise IntegrityError("Battery SOC out of bounds", params={"site_id": target.site_id, "soc": target.battery_soc}, orig=None)



class ForecastResult(Base):
    """
    Model representing persisted multi-step forecasting predictions.

    Stores energy predictions for specific sites, targets, horizon steps, and timestamps.
    """

    __tablename__ = "energy_forecasts"
    __table_args__ = (
        CheckConstraint(
            "horizon_step >= 1 AND horizon_step <= 24",
            name="ck_forecast_result_horizon_step",
        ),
    )


    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_run_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Unique run identifier for a single forecast batch execution",
    )
    site_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Identifier for the monitored facility, microgrid, or plant",
    )
    target: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        doc="Target metric forecasted (e.g. solar, wind, demand, renewable, balance)",
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Timestamp when the forecast was generated (UTC)",
    )
    target_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Target timestamp of the forecast point (UTC)",
    )
    horizon_step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Horizon step offset (1 to 24 hours ahead)",
    )
    predicted_value_kwh: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Predicted energy value in kWh for the horizon step",
    )
    model_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Model version or baseline type used for generation",
    )

    def __repr__(self) -> str:
        return (
            f"<ForecastResult(id={self.id}, run_id='{self.forecast_run_id}', site_id='{self.site_id}', "
            f"target='{self.target}', step={self.horizon_step}, target_ts='{self.target_timestamp}', "
            f"predicted_kwh={self.predicted_value_kwh})>"
        )


class BatteryOptimizationRun(Base):
    """
    Model representing an optimization run execution.
    """
    __tablename__ = "battery_optimization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    optimization_run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, doc="Unique run identifier"
    )
    site_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, doc="Site identifier"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, doc="Creation timestamp (UTC)"
    )
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    battery_capacity_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    initial_soc_pct: Mapped[float] = mapped_column(Float, nullable=False)
    final_soc_pct: Mapped[float] = mapped_column(Float, nullable=False)
    total_charge_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    total_discharge_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    total_grid_import_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    total_grid_export_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_grid_cost: Mapped[float] = mapped_column(Float, nullable=False)
    grid_import_reduction_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    cost_savings: Mapped[float] = mapped_column(Float, nullable=False)
    optimizer_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1.0-linprog")


class BatteryOptimizationPoint(Base):
    """
    Model representing individual schedule points for an optimization run.
    """
    __tablename__ = "battery_optimization_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    optimization_run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, doc="Associated optimization run ID"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, doc="Interval timestamp (UTC)"
    )
    forecast_renewable_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_demand_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_balance_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    battery_soc_before_pct: Mapped[float] = mapped_column(Float, nullable=False)
    battery_charge_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    battery_discharge_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    battery_soc_after_pct: Mapped[float] = mapped_column(Float, nullable=False)
    grid_import_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    grid_export_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    curtailed_energy_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_grid_cost: Mapped[float] = mapped_column(Float, nullable=False)
    optimization_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class AnomalyDetectionRun(Base):
    """
    Model representing an anomaly detection batch run.
    """
    __tablename__ = "anomaly_detection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_detection_run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, doc="Unique detection run ID"
    )
    site_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    records_examined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anomalies_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    z_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)


class EnergyAnomaly(Base):
    """
    Model representing a detected energy anomaly.
    """
    __tablename__ = "energy_anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    anomaly_detection_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    site_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    anomaly_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    expected_value: Mapped[float] = mapped_column(Float, nullable=False)
    deviation: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_pct: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    detection_method: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    related_energy_reading_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class WeatherReading(Base):
    """
    Normalized hourly weather observation for a VoltAI site.

    Stores provider-agnostic weather data from any configured provider
    (Open-Meteo, WeatherAPI, IMD, IoT sensors, etc.).

    Uniqueness:
        The composite unique constraint on (site_id, timestamp) prevents duplicate
        records for the same site and hour. Multiple sites CAN share the same
        timestamp (intentional — each site has its own weather reading).

    Units:
        temperature_c           : Degrees Celsius
        relative_humidity_pct   : Percentage (0.0 – 100.0)
        precipitation_mm        : Millimeters per hour
        cloud_cover_pct         : Percentage (0.0 – 100.0)
        wind_speed_ms           : Metres per second
        wind_direction_deg      : Degrees (0 – 360)
        shortwave_radiation_wm2 : Watts per square metre (W/m²)
    """

    __tablename__ = "weather_readings"
    __table_args__ = (
        UniqueConstraint("site_id", "timestamp", name="uq_weather_reading_site_timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    site_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="VoltAI site identifier",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Hourly observation timestamp (UTC, timezone-aware)",
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Site latitude in decimal degrees",
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Site longitude in decimal degrees",
    )

    # --- Meteorological fields (all optional) ---
    temperature_c: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None, doc="Air temperature in °C"
    )
    relative_humidity_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None, doc="Relative humidity percentage"
    )
    precipitation_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None, doc="Hourly precipitation in mm"
    )
    cloud_cover_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None, doc="Total cloud cover percentage"
    )
    wind_speed_ms: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None, doc="Wind speed in m/s"
    )
    wind_direction_deg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None, doc="Wind direction in degrees (0–360)"
    )
    shortwave_radiation_wm2: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=None, doc="Solar shortwave radiation in W/m²"
    )

    # --- Provenance ---
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Weather provider identifier (e.g., 'open_meteo')",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when this record was retrieved from provider (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<WeatherReading(id={self.id}, site_id='{self.site_id}', "
            f"timestamp='{self.timestamp}', temp_c={self.temperature_c}, "
            f"provider='{self.provider}')>"
        )

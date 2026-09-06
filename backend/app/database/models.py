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

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String
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
            "battery_soc >= 0.0 AND battery_soc <= 100.0",
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

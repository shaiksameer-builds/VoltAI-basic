"""
VoltAI Pydantic Schemas for Energy Readings

Provides input validation, serialization, and type checking for normalized
energy readings across all ingestion adapters (CSV, IoT, Smart Meter, SCADA)
and future API endpoints.

Measurement Semantics:
    Interval Energy flows (generation, consumption, storage, grid) are measured
    in kilowatt-hours (kWh) over the observation interval. For 1-hour intervals,
    this corresponds directly to average power in kW.
    Battery State of Charge (battery_soc) is an instantaneous percentage (0.0 - 100.0%).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EnergyReadingBase(BaseModel):
    """
    Base schema containing all normalized energy telemetry fields.
    """

    timestamp: datetime = Field(
        ...,
        description="Observation interval timestamp (ISO 8601, timezone-aware recommended)",
    )
    site_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier for the site or facility",
    )
    solar_generation: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Solar energy generated over the interval in kWh",
    )
    wind_generation: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Wind energy generated over the interval in kWh",
    )
    energy_consumption: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Total site energy consumed over the interval in kWh",
    )
    battery_soc: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Battery State of Charge percentage (0.0 to 100.0)",
    )
    battery_charge: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Energy charged into battery over the interval in kWh",
    )
    battery_discharge: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Energy discharged from battery over the interval in kWh",
    )
    grid_import: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Energy imported from utility grid over the interval in kWh",
    )
    grid_export: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Energy exported to utility grid over the interval in kWh",
    )


class EnergyReadingCreate(EnergyReadingBase):
    """
    Schema used for validating and ingesting new energy readings.
    """
    pass


class EnergyReadingResponse(EnergyReadingBase):
    """
    Schema returned when querying energy readings from the API/database.
    Includes the database primary key.
    """

    id: int = Field(..., description="Unique database record identifier")

    model_config = ConfigDict(from_attributes=True)

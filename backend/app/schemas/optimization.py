"""
VoltAI Battery Optimization Schemas (Stage 7)

Defines Pydantic models for battery configuration, optimization schedules, and responses.
"""

from datetime import datetime
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BatteryConfig(BaseModel):
    """
    Configuration and physical constraints of a battery storage system.
    """
    model_config = ConfigDict(from_attributes=True)

    battery_capacity_kwh: float = Field(100.0, gt=0.0, description="Total usable battery energy capacity in kWh")
    min_soc_pct: float = Field(10.0, ge=0.0, le=100.0, description="Minimum allowed State of Charge percentage")
    max_soc_pct: float = Field(90.0, ge=0.0, le=100.0, description="Maximum allowed State of Charge percentage")
    max_charge_power_kw: float = Field(50.0, ge=0.0, description="Maximum charging power rating in kW")
    max_discharge_power_kw: float = Field(50.0, ge=0.0, description="Maximum discharging power rating in kW")
    charge_efficiency: float = Field(0.95, gt=0.0, le=1.0, description="Charging round-trip/one-way efficiency ratio")
    discharge_efficiency: float = Field(0.95, gt=0.0, le=1.0, description="Discharging round-trip/one-way efficiency ratio")
    initial_soc_pct: float = Field(50.0, ge=0.0, le=100.0, description="Initial State of Charge percentage at start")

    @field_validator("max_soc_pct")
    @classmethod
    def validate_soc_bounds(cls, v: float, info) -> float:
        min_soc = info.data.get("min_soc_pct", 10.0)
        if v <= min_soc:
            raise ValueError(f"max_soc_pct ({v}%) must be strictly greater than min_soc_pct ({min_soc}%)")
        return v

    @field_validator("initial_soc_pct")
    @classmethod
    def validate_initial_soc(cls, v: float, info) -> float:
        min_soc = info.data.get("min_soc_pct", 0.0)
        max_soc = info.data.get("max_soc_pct", 100.0)
        if not (min_soc <= v <= max_soc):
            raise ValueError(f"initial_soc_pct ({v}%) must be between min_soc_pct ({min_soc}%) and max_soc_pct ({max_soc}%)")
        return v


class GridPricingConfig(BaseModel):
    """
    Utility grid import and export pricing structure per kWh.
    """
    model_config = ConfigDict(from_attributes=True)

    import_price_per_kwh: float = Field(0.15, ge=0.0, description="Grid energy import cost per kWh ($/kWh)")
    export_price_per_kwh: float = Field(0.05, ge=0.0, description="Grid energy export feed-in credit per kWh ($/kWh)")


class OptimizationPoint(BaseModel):
    """
    Detailed dispatch state for a single hourly interval.
    """
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime = Field(..., description="Interval target timestamp (UTC)")
    forecast_renewable_kwh: float = Field(..., ge=0.0, description="Predicted renewable generation in kWh")
    forecast_demand_kwh: float = Field(..., ge=0.0, description="Predicted energy demand in kWh")
    forecast_balance_kwh: float = Field(..., description="Predicted net balance in kWh (renewable - demand)")
    battery_soc_before_pct: float = Field(..., ge=0.0, le=100.0, description="SOC percentage before interval dispatch")
    battery_charge_kwh: float = Field(..., ge=0.0, description="Energy charged into battery over interval in kWh")
    battery_discharge_kwh: float = Field(..., ge=0.0, description="Energy discharged from battery over interval in kWh")
    battery_soc_after_pct: float = Field(..., ge=0.0, le=100.0, description="SOC percentage after interval dispatch")
    grid_import_kwh: float = Field(..., ge=0.0, description="Grid energy imported over interval in kWh")
    grid_export_kwh: float = Field(..., ge=0.0, description="Grid energy exported over interval in kWh")
    curtailed_energy_kwh: float = Field(0.0, ge=0.0, description="Renewable energy curtailed over interval in kWh")
    estimated_grid_cost: float = Field(..., description="Net estimated grid energy cost ($) for interval")
    optimization_reason: Optional[str] = Field(None, description="Explanation for dispatch action")

    @field_validator("battery_discharge_kwh")
    @classmethod
    def validate_no_simultaneous_charge_discharge(cls, v: float, info) -> float:
        charge = info.data.get("battery_charge_kwh", 0.0)
        if charge > 1e-4 and v > 1e-4:
            raise ValueError(f"Simultaneous charging ({charge} kWh) and discharging ({v} kWh) is physically invalid.")
        return v


class OptimizationSummary(BaseModel):
    """
    Summary metrics comparing baseline vs optimized dispatch schedules.
    """
    model_config = ConfigDict(from_attributes=True)

    total_renewable_kwh: float = Field(..., ge=0.0)
    total_demand_kwh: float = Field(..., ge=0.0)
    baseline_grid_import_kwh: float = Field(..., ge=0.0)
    optimized_grid_import_kwh: float = Field(..., ge=0.0)
    grid_import_reduction_kwh: float = Field(..., description="Grid import reduction achieved in kWh")
    grid_import_reduction_pct: float = Field(..., description="Percentage reduction in grid import")
    baseline_grid_cost: float = Field(..., description="Estimated cost without battery optimization ($)")
    optimized_grid_cost: float = Field(..., description="Estimated cost with battery optimization ($)")
    cost_savings: float = Field(..., description="Net financial savings ($)")
    cost_savings_pct: float = Field(..., description="Percentage savings in grid energy cost")


class OptimizationRequest(BaseModel):
    """
    Request schema to trigger a 24-step battery optimization schedule run.
    """
    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., min_length=1, description="Site identifier")
    horizon_hours: int = Field(24, ge=1, le=24, description="Optimization horizon in hours")
    battery_config: BatteryConfig = Field(default_factory=BatteryConfig)
    pricing_config: GridPricingConfig = Field(default_factory=GridPricingConfig)
    cycling_penalty_per_kwh: float = Field(0.001, ge=0.0, description="Battery wear penalty per kWh cycled ($/kWh)")


class OptimizationResponse(BaseModel):
    """
    Complete response containing optimal dispatch schedule and summary performance metrics.
    """
    model_config = ConfigDict(from_attributes=True)

    optimization_run_id: str = Field(..., min_length=1, description="Unique optimization execution run identifier")
    site_id: str = Field(..., min_length=1)
    horizon_hours: int = Field(..., ge=1, le=24)
    created_at: datetime = Field(..., description="Run generation timestamp (UTC)")
    battery_config: BatteryConfig
    pricing_config: GridPricingConfig
    summary: OptimizationSummary
    schedule: List[OptimizationPoint]

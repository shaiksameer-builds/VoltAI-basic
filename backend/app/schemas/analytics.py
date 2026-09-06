"""
VoltAI Analytics Schemas

Pydantic models for energy analytics queries and aggregations.
Field names explicitly include measurement units (_kwh, _pct).
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EnergySummaryResponse(BaseModel):
    """
    Overall energy intelligence summary across an observation window.
    """

    site_id: Optional[str] = Field(
        default=None,
        description="Filter applied for a specific site, or null for all sites aggregate",
    )
    start_time: Optional[datetime] = Field(
        default=None,
        description="Start of evaluation window",
    )
    end_time: Optional[datetime] = Field(
        default=None,
        description="End of evaluation window",
    )
    reading_count: int = Field(
        ...,
        description="Total number of hourly interval observations evaluated",
    )
    total_consumption_kwh: float = Field(
        ...,
        description="Total energy consumed across all evaluated hours in kWh",
    )
    total_solar_generation_kwh: float = Field(
        ...,
        description="Total solar energy generated in kWh",
    )
    total_wind_generation_kwh: float = Field(
        ...,
        description="Total wind energy generated in kWh",
    )
    total_renewable_generation_kwh: float = Field(
        ...,
        description="Total renewable generation (solar + wind) in kWh",
    )
    renewable_contribution_pct: float = Field(
        ...,
        description="Percentage of consumption matched by on-site renewable generation (%)",
    )
    total_battery_charge_kwh: float = Field(
        ...,
        description="Total energy stored into battery storage in kWh",
    )
    total_battery_discharge_kwh: float = Field(
        ...,
        description="Total energy drawn from battery storage in kWh",
    )
    total_grid_import_kwh: float = Field(
        ...,
        description="Total energy imported from utility grid in kWh",
    )
    total_grid_export_kwh: float = Field(
        ...,
        description="Total energy exported to utility grid in kWh",
    )
    net_grid_energy_kwh: float = Field(
        ...,
        description="Net grid energy: grid_import - grid_export in kWh",
    )
    grid_dependence_pct: float = Field(
        ...,
        description="Ratio of grid import to total site consumption (%)",
    )
    energy_independence_pct: float = Field(
        ...,
        description="Percentage of consumption met without utility grid import (%)",
    )
    avg_hourly_consumption_kwh: float = Field(
        ...,
        description="Average hourly consumption rate in kWh/h (average kW)",
    )
    peak_hourly_consumption_kwh: float = Field(
        ...,
        description="Maximum single-hour consumption observed in kWh",
    )

    model_config = ConfigDict(from_attributes=True)


class DailyAnalyticsItem(BaseModel):
    """
    Daily aggregated energy telemetry metrics for a calendar date.
    """

    date: str = Field(..., description="Calendar date in YYYY-MM-DD format")
    reading_count: int = Field(..., description="Number of hourly intervals in this date")
    total_consumption_kwh: float = Field(..., description="Total consumption for the day in kWh")
    solar_generation_kwh: float = Field(..., description="Solar generation for the day in kWh")
    wind_generation_kwh: float = Field(..., description="Wind generation for the day in kWh")
    renewable_generation_kwh: float = Field(..., description="Total renewable generation for the day in kWh")
    renewable_contribution_pct: float = Field(..., description="Daily renewable contribution percentage (%)")
    grid_import_kwh: float = Field(..., description="Daily grid import in kWh")
    grid_export_kwh: float = Field(..., description="Daily grid export in kWh")
    net_grid_energy_kwh: float = Field(..., description="Daily net grid energy in kWh (import - export)")
    battery_charge_kwh: float = Field(..., description="Daily battery charging energy in kWh")
    battery_discharge_kwh: float = Field(..., description="Daily battery discharging energy in kWh")
    avg_hourly_consumption_kwh: float = Field(..., description="Average hourly consumption for the day in kWh")
    peak_hourly_consumption_kwh: float = Field(..., description="Peak single-hour consumption for the day in kWh")
    peak_timestamp: Optional[datetime] = Field(default=None, description="Timestamp when peak occurred")

    model_config = ConfigDict(from_attributes=True)


class DailyAnalyticsResponse(BaseModel):
    """
    Collection of daily aggregated records.
    """

    site_id: Optional[str] = Field(default=None, description="Site filter if applied")
    days_count: int = Field(..., description="Total number of days returned")
    daily_metrics: List[DailyAnalyticsItem] = Field(default_factory=list)


class SiteAnalyticsItem(BaseModel):
    """
    Facility / Site-level energy telemetry summary.
    """

    site_id: str = Field(..., description="Unique facility/site identifier")
    reading_count: int = Field(..., description="Number of hourly intervals recorded for this site")
    total_consumption_kwh: float = Field(..., description="Total site consumption in kWh")
    total_solar_generation_kwh: float = Field(..., description="Total site solar generation in kWh")
    total_wind_generation_kwh: float = Field(..., description="Total site wind generation in kWh")
    total_renewable_generation_kwh: float = Field(..., description="Total site renewable generation in kWh")
    renewable_contribution_pct: float = Field(..., description="Site renewable contribution percentage (%)")
    total_grid_import_kwh: float = Field(..., description="Total site grid import in kWh")
    total_grid_export_kwh: float = Field(..., description="Total site grid export in kWh")
    net_grid_energy_kwh: float = Field(..., description="Site net grid energy in kWh (import - export)")
    total_battery_charge_kwh: float = Field(..., description="Total site battery charge in kWh")
    total_battery_discharge_kwh: float = Field(..., description="Total site battery discharge in kWh")
    avg_hourly_consumption_kwh: float = Field(..., description="Average hourly consumption rate in kWh")
    peak_hourly_consumption_kwh: float = Field(..., description="Peak single-hour consumption in kWh")

    model_config = ConfigDict(from_attributes=True)


class SiteAnalyticsResponse(BaseModel):
    """
    Collection of site comparison analytics.
    """

    sites_count: int = Field(..., description="Number of distinct monitored sites")
    sites: List[SiteAnalyticsItem] = Field(default_factory=list)


class PeakDemandResponse(BaseModel):
    """
    Peak hourly demand observation details.
    """

    peak_consumption_kwh: float = Field(..., description="Peak single-hour consumption in kWh")
    peak_timestamp: Optional[datetime] = Field(default=None, description="Observation timestamp of the peak hour")
    site_id: Optional[str] = Field(default=None, description="Site identifier where peak occurred")
    is_empty: bool = Field(default=False, description="True if no telemetry records exist")

    model_config = ConfigDict(from_attributes=True)

"""
VoltAI Energy Analytics Service

Provides deterministic energy analytics, aggregation, and efficiency metrics
derived from normalized EnergyReading database records.

Formulas & Semantics:
    1. Interval Energy:
       All flows are measured in kilowatt-hours (kWh) over hourly intervals.
    2. Renewable Generation:
       renewable_generation = solar_generation + wind_generation
    3. Renewable Contribution (%):
       renewable_contribution_pct = (renewable_generation / energy_consumption) * 100
       (Returns 0.0% if energy_consumption is 0.0 to prevent division by zero).
    4. Grid Dependence (%):
       grid_dependence_pct = (grid_import / energy_consumption) * 100
       (Returns 0.0% if energy_consumption is 0.0).
    5. Energy Independence (%):
       Percentage of facility consumption fulfilled without utility grid imports:
       energy_independence_pct = clamp(0.0, 100.0, ((consumption - grid_import) / consumption) * 100)
       (Returns 0.0% if energy_consumption is 0.0).
    6. Net Grid Energy:
       net_grid_energy = grid_import - grid_export
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database.models import EnergyReading
from backend.app.schemas.analytics import (
    DailyAnalyticsItem,
    DailyAnalyticsResponse,
    EnergySummaryResponse,
    PeakDemandResponse,
    SiteAnalyticsItem,
    SiteAnalyticsResponse,
)


def _safe_round(val: float | None, digits: int = 2) -> float:
    if val is None:
        return 0.0
    return round(float(val), digits)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime has timezone info (defaults to UTC if naive, as in SQLite).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def calculate_renewable_contribution(renewable_kwh: float, consumption_kwh: float) -> float:
    """
    Calculate renewable contribution percentage, safe against zero consumption.
    """
    if consumption_kwh <= 0.0:
        return 0.0
    return _safe_round((renewable_kwh / consumption_kwh) * 100.0, 2)


def calculate_grid_dependence(grid_import_kwh: float, consumption_kwh: float) -> float:
    """
    Calculate grid dependence ratio (grid_import / consumption * 100), safe against zero consumption.
    """
    if consumption_kwh <= 0.0:
        return 0.0
    return _safe_round((grid_import_kwh / consumption_kwh) * 100.0, 2)


def calculate_energy_independence(grid_import_kwh: float, consumption_kwh: float) -> float:
    """
    Calculate energy independence percentage: portion of consumption met without grid imports.
    Clamped strictly between 0.0% and 100.0%.
    """
    if consumption_kwh <= 0.0:
        return 0.0
    net_self_supplied = consumption_kwh - grid_import_kwh
    ratio = (net_self_supplied / consumption_kwh) * 100.0
    return _safe_round(max(0.0, min(100.0, ratio)), 2)


def get_energy_summary(
    db: Session,
    site_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> EnergySummaryResponse:
    """
    Aggregate overall energy metrics across the specified window and site filter.
    Handles empty database states gracefully without errors.
    """
    query = db.query(
        func.count(EnergyReading.id).label("count"),
        func.coalesce(func.sum(EnergyReading.energy_consumption), 0.0).label("consumption"),
        func.coalesce(func.sum(EnergyReading.solar_generation), 0.0).label("solar"),
        func.coalesce(func.sum(EnergyReading.wind_generation), 0.0).label("wind"),
        func.coalesce(func.sum(EnergyReading.battery_charge), 0.0).label("battery_charge"),
        func.coalesce(func.sum(EnergyReading.battery_discharge), 0.0).label("battery_discharge"),
        func.coalesce(func.sum(EnergyReading.grid_import), 0.0).label("grid_import"),
        func.coalesce(func.sum(EnergyReading.grid_export), 0.0).label("grid_export"),
        func.coalesce(func.avg(EnergyReading.energy_consumption), 0.0).label("avg_consumption"),
        func.coalesce(func.max(EnergyReading.energy_consumption), 0.0).label("max_consumption"),
    )

    if site_id:
        query = query.filter(EnergyReading.site_id == site_id)
    if start_time:
        query = query.filter(EnergyReading.timestamp >= start_time)
    if end_time:
        query = query.filter(EnergyReading.timestamp <= end_time)

    row = query.one()
    count = row.count or 0

    if count == 0:
        return EnergySummaryResponse(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            reading_count=0,
            total_consumption_kwh=0.0,
            total_solar_generation_kwh=0.0,
            total_wind_generation_kwh=0.0,
            total_renewable_generation_kwh=0.0,
            renewable_contribution_pct=0.0,
            total_battery_charge_kwh=0.0,
            total_battery_discharge_kwh=0.0,
            total_grid_import_kwh=0.0,
            total_grid_export_kwh=0.0,
            net_grid_energy_kwh=0.0,
            grid_dependence_pct=0.0,
            energy_independence_pct=0.0,
            avg_hourly_consumption_kwh=0.0,
            peak_hourly_consumption_kwh=0.0,
        )

    tot_consumption = _safe_round(row.consumption)
    tot_solar = _safe_round(row.solar)
    tot_wind = _safe_round(row.wind)
    tot_renewable = _safe_round(tot_solar + tot_wind)
    tot_grid_import = _safe_round(row.grid_import)
    tot_grid_export = _safe_round(row.grid_export)
    tot_bat_charge = _safe_round(row.battery_charge)
    tot_bat_discharge = _safe_round(row.battery_discharge)
    net_grid = _safe_round(tot_grid_import - tot_grid_export)

    return EnergySummaryResponse(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        reading_count=count,
        total_consumption_kwh=tot_consumption,
        total_solar_generation_kwh=tot_solar,
        total_wind_generation_kwh=tot_wind,
        total_renewable_generation_kwh=tot_renewable,
        renewable_contribution_pct=calculate_renewable_contribution(tot_renewable, tot_consumption),
        total_battery_charge_kwh=tot_bat_charge,
        total_battery_discharge_kwh=tot_bat_discharge,
        total_grid_import_kwh=tot_grid_import,
        total_grid_export_kwh=tot_grid_export,
        net_grid_energy_kwh=net_grid,
        grid_dependence_pct=calculate_grid_dependence(tot_grid_import, tot_consumption),
        energy_independence_pct=calculate_energy_independence(tot_grid_import, tot_consumption),
        avg_hourly_consumption_kwh=_safe_round(row.avg_consumption),
        peak_hourly_consumption_kwh=_safe_round(row.max_consumption),
    )


def get_peak_demand(
    db: Session,
    site_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> PeakDemandResponse:
    """
    Retrieve single highest hourly energy consumption observation and its details.
    """
    query = db.query(EnergyReading).filter(EnergyReading.energy_consumption.is_not(None))

    if site_id:
        query = query.filter(EnergyReading.site_id == site_id)
    if start_time:
        query = query.filter(EnergyReading.timestamp >= start_time)
    if end_time:
        query = query.filter(EnergyReading.timestamp <= end_time)

    peak_row = (
        query.order_by(
            EnergyReading.energy_consumption.desc(),
            EnergyReading.timestamp.asc(),
        )
        .first()
    )

    if not peak_row:
        return PeakDemandResponse(
            peak_consumption_kwh=0.0,
            peak_timestamp=None,
            site_id=site_id,
            is_empty=True,
        )

    return PeakDemandResponse(
        peak_consumption_kwh=_safe_round(peak_row.energy_consumption),
        peak_timestamp=_ensure_utc(peak_row.timestamp),
        site_id=peak_row.site_id,
        is_empty=False,
    )


def get_daily_analytics(
    db: Session,
    site_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> DailyAnalyticsResponse:
    """
    Aggregate hourly telemetry grouped by calendar date (YYYY-MM-DD).
    """
    # Group by calendar date string
    date_expr = func.date(EnergyReading.timestamp)

    query = db.query(
        date_expr.label("date_str"),
        func.count(EnergyReading.id).label("count"),
        func.coalesce(func.sum(EnergyReading.energy_consumption), 0.0).label("consumption"),
        func.coalesce(func.sum(EnergyReading.solar_generation), 0.0).label("solar"),
        func.coalesce(func.sum(EnergyReading.wind_generation), 0.0).label("wind"),
        func.coalesce(func.sum(EnergyReading.grid_import), 0.0).label("grid_import"),
        func.coalesce(func.sum(EnergyReading.grid_export), 0.0).label("grid_export"),
        func.coalesce(func.sum(EnergyReading.battery_charge), 0.0).label("battery_charge"),
        func.coalesce(func.sum(EnergyReading.battery_discharge), 0.0).label("battery_discharge"),
        func.coalesce(func.avg(EnergyReading.energy_consumption), 0.0).label("avg_consumption"),
        func.coalesce(func.max(EnergyReading.energy_consumption), 0.0).label("max_consumption"),
    )

    if site_id:
        query = query.filter(EnergyReading.site_id == site_id)
    if start_time:
        query = query.filter(EnergyReading.timestamp >= start_time)
    if end_time:
        query = query.filter(EnergyReading.timestamp <= end_time)

    rows = query.group_by(date_expr).order_by(date_expr.asc()).all()

    if not rows:
        return DailyAnalyticsResponse(site_id=site_id, days_count=0, daily_metrics=[])

    # To fetch peak timestamps per date cleanly in a single secondary pass if needed
    daily_items = []
    for row in rows:
        tot_cons = _safe_round(row.consumption)
        tot_sol = _safe_round(row.solar)
        tot_win = _safe_round(row.wind)
        tot_ren = _safe_round(tot_sol + tot_win)
        tot_imp = _safe_round(row.grid_import)
        tot_exp = _safe_round(row.grid_export)
        tot_chg = _safe_round(row.battery_charge)
        tot_dis = _safe_round(row.battery_discharge)
        peak_cons = _safe_round(row.max_consumption)

        # Query the exact peak timestamp for this date
        peak_reading_query = db.query(EnergyReading.timestamp).filter(
            date_expr == row.date_str,
            EnergyReading.energy_consumption == row.max_consumption,
        )
        if site_id:
            peak_reading_query = peak_reading_query.filter(EnergyReading.site_id == site_id)

        peak_ts_row = peak_reading_query.order_by(EnergyReading.timestamp.asc()).first()
        peak_ts = peak_ts_row[0] if peak_ts_row else None

        daily_items.append(
            DailyAnalyticsItem(
                date=str(row.date_str),
                reading_count=row.count,
                total_consumption_kwh=tot_cons,
                solar_generation_kwh=tot_sol,
                wind_generation_kwh=tot_win,
                renewable_generation_kwh=tot_ren,
                renewable_contribution_pct=calculate_renewable_contribution(tot_ren, tot_cons),
                grid_import_kwh=tot_imp,
                grid_export_kwh=tot_exp,
                net_grid_energy_kwh=_safe_round(tot_imp - tot_exp),
                battery_charge_kwh=tot_chg,
                battery_discharge_kwh=tot_dis,
                avg_hourly_consumption_kwh=_safe_round(row.avg_consumption),
                peak_hourly_consumption_kwh=peak_cons,
                peak_timestamp=_ensure_utc(peak_ts),
            )
        )

    return DailyAnalyticsResponse(
        site_id=site_id,
        days_count=len(daily_items),
        daily_metrics=daily_items,
    )


def get_site_analytics(
    db: Session,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> SiteAnalyticsResponse:
    """
    Summarize energy metrics grouped by site identifier for facility comparisons.
    """
    query = db.query(
        EnergyReading.site_id,
        func.count(EnergyReading.id).label("count"),
        func.coalesce(func.sum(EnergyReading.energy_consumption), 0.0).label("consumption"),
        func.coalesce(func.sum(EnergyReading.solar_generation), 0.0).label("solar"),
        func.coalesce(func.sum(EnergyReading.wind_generation), 0.0).label("wind"),
        func.coalesce(func.sum(EnergyReading.grid_import), 0.0).label("grid_import"),
        func.coalesce(func.sum(EnergyReading.grid_export), 0.0).label("grid_export"),
        func.coalesce(func.sum(EnergyReading.battery_charge), 0.0).label("battery_charge"),
        func.coalesce(func.sum(EnergyReading.battery_discharge), 0.0).label("battery_discharge"),
        func.coalesce(func.avg(EnergyReading.energy_consumption), 0.0).label("avg_consumption"),
        func.coalesce(func.max(EnergyReading.energy_consumption), 0.0).label("max_consumption"),
    )

    if start_time:
        query = query.filter(EnergyReading.timestamp >= start_time)
    if end_time:
        query = query.filter(EnergyReading.timestamp <= end_time)

    rows = query.group_by(EnergyReading.site_id).order_by(EnergyReading.site_id.asc()).all()

    if not rows:
        return SiteAnalyticsResponse(sites_count=0, sites=[])

    site_items = []
    for row in rows:
        tot_cons = _safe_round(row.consumption)
        tot_sol = _safe_round(row.solar)
        tot_win = _safe_round(row.wind)
        tot_ren = _safe_round(tot_sol + tot_win)
        tot_imp = _safe_round(row.grid_import)
        tot_exp = _safe_round(row.grid_export)
        tot_chg = _safe_round(row.battery_charge)
        tot_dis = _safe_round(row.battery_discharge)

        site_items.append(
            SiteAnalyticsItem(
                site_id=row.site_id,
                reading_count=row.count,
                total_consumption_kwh=tot_cons,
                total_solar_generation_kwh=tot_sol,
                total_wind_generation_kwh=tot_win,
                total_renewable_generation_kwh=tot_ren,
                renewable_contribution_pct=calculate_renewable_contribution(tot_ren, tot_cons),
                total_grid_import_kwh=tot_imp,
                total_grid_export_kwh=tot_exp,
                net_grid_energy_kwh=_safe_round(tot_imp - tot_exp),
                total_battery_charge_kwh=tot_chg,
                total_battery_discharge_kwh=tot_dis,
                avg_hourly_consumption_kwh=_safe_round(row.avg_consumption),
                peak_hourly_consumption_kwh=_safe_round(row.max_consumption),
            )
        )

    return SiteAnalyticsResponse(
        sites_count=len(site_items),
        sites=site_items,
    )

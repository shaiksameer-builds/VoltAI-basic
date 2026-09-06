"""
VoltAI Energy Analytics API Router

Exposes REST endpoints for summary, daily, site comparison, and peak demand metrics.
Keeps routing thin: validates parameters and delegates to the EnergyAnalyticsService.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.schemas.analytics import (
    DailyAnalyticsResponse,
    EnergySummaryResponse,
    PeakDemandResponse,
    SiteAnalyticsResponse,
)
from backend.app.services.energy_analytics import (
    get_daily_analytics,
    get_energy_summary,
    get_peak_demand,
    get_site_analytics,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["Energy Analytics"])


@router.get(
    "/summary",
    response_model=EnergySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get overall energy metrics summary",
    description="Calculates consumption, generation, storage, grid interchange, and efficiency percentages across an optional filter window.",
)
def read_energy_summary(
    site_id: Optional[str] = Query(default=None, description="Optional site identifier filter"),
    start: Optional[datetime] = Query(default=None, description="Optional start datetime filter (ISO 8601)"),
    end: Optional[datetime] = Query(default=None, description="Optional end datetime filter (ISO 8601)"),
    db: Session = Depends(get_db),
) -> EnergySummaryResponse:
    return get_energy_summary(db=db, site_id=site_id, start_time=start, end_time=end)


@router.get(
    "/daily",
    response_model=DailyAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get daily aggregated energy telemetry",
    description="Aggregates hourly interval energy records into daily calendar date totals and peaks.",
)
def read_daily_analytics(
    site_id: Optional[str] = Query(default=None, description="Optional site identifier filter"),
    start: Optional[datetime] = Query(default=None, description="Optional start datetime filter (ISO 8601)"),
    end: Optional[datetime] = Query(default=None, description="Optional end datetime filter (ISO 8601)"),
    db: Session = Depends(get_db),
) -> DailyAnalyticsResponse:
    return get_daily_analytics(db=db, site_id=site_id, start_time=start, end_time=end)


@router.get(
    "/sites",
    response_model=SiteAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get site-level energy comparison summaries",
    description="Summarizes total consumption, generation, storage, and peaks grouped by site.",
)
def read_site_analytics(
    start: Optional[datetime] = Query(default=None, description="Optional start datetime filter (ISO 8601)"),
    end: Optional[datetime] = Query(default=None, description="Optional end datetime filter (ISO 8601)"),
    db: Session = Depends(get_db),
) -> SiteAnalyticsResponse:
    return get_site_analytics(db=db, start_time=start, end_time=end)


@router.get(
    "/peak",
    response_model=PeakDemandResponse,
    status_code=status.HTTP_200_OK,
    summary="Get peak hourly demand observation",
    description="Retrieves the single highest hourly consumption event, its timestamp, and associated facility.",
)
def read_peak_demand(
    site_id: Optional[str] = Query(default=None, description="Optional site identifier filter"),
    start: Optional[datetime] = Query(default=None, description="Optional start datetime filter (ISO 8601)"),
    end: Optional[datetime] = Query(default=None, description="Optional end datetime filter (ISO 8601)"),
    db: Session = Depends(get_db),
) -> PeakDemandResponse:
    return get_peak_demand(db=db, site_id=site_id, start_time=start, end_time=end)

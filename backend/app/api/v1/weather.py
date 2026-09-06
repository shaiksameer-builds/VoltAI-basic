"""
VoltAI Weather Integration API Endpoints

Provides endpoints for fetching/ingesting weather telemetry and retrieving stored weather data.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.weather.ingestion import WeatherIngestionService
from backend.app.weather.schemas import (
    WeatherIngestRequest,
    WeatherIngestSummary,
    WeatherRecord,
    WeatherStatusResponse,
)
from backend.app.weather.service import WeatherService

router = APIRouter(prefix="/api/v1/weather", tags=["Weather Integration"])


@router.post(
    "/ingest",
    response_model=WeatherIngestSummary,
    status_code=status.HTTP_200_OK,
    summary="Fetch and ingest weather telemetry",
    description=(
        "Triggers a weather data fetch from the configured (or specified) provider "
        "for a given site and date range, then ingests normalized weather records into the database."
    ),
)
async def ingest_weather(
    request: WeatherIngestRequest,
    db: Session = Depends(get_db),
):
    """
    Fetch weather telemetry from provider and persist to database.
    """
    if request.start_date > request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be less than or equal to end_date",
        )

    summary = WeatherService.fetch_and_ingest(
        db=db,
        site_id=request.site_id,
        start_date=request.start_date,
        end_date=request.end_date,
        provider_name=request.provider,
    )
    return summary


@router.get(
    "",
    response_model=List[WeatherRecord],
    status_code=status.HTTP_200_OK,
    summary="Retrieve stored weather records for a site",
    description="Query historical weather records stored in the database for a specific site and time range.",
)
async def get_weather(
    site_id: str = Query(..., description="Site ID (e.g. site_001)"),
    start_date: Optional[datetime] = Query(None, description="Filter records on or after start date"),
    end_date: Optional[datetime] = Query(None, description="Filter records on or before end date"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of records to return"),
    db: Session = Depends(get_db),
):
    """
    Retrieve stored weather records.
    """
    records = WeatherIngestionService.get_weather_for_site(
        db=db,
        site_id=site_id,
        start_ts=start_date,
        end_ts=end_date,
        limit=limit,
    )
    return records


@router.get(
    "/status",
    response_model=WeatherStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get weather integration system status",
    description="Check active weather provider configuration and total stored weather record count.",
)
async def get_weather_status(
    db: Session = Depends(get_db),
):
    """
    Get weather integration system status.
    """
    return WeatherService.get_status(db=db)

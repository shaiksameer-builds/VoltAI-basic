"""
Weather service orchestrator for VoltAI.

Coordinates fetching weather data from weather providers and ingesting it into
the database via WeatherIngestionService.
"""

import logging
from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Session

from backend.app.weather.config import WeatherConfig, WeatherConfigurationError
from backend.app.weather.factory import get_provider
from backend.app.weather.ingestion import WeatherIngestionService
from backend.app.weather.providers import WeatherProviderError
from backend.app.weather.schemas import (
    WeatherIngestSummary,
    WeatherStatusResponse,
)
from backend.app.weather.sites import get_site_location, SITE_LOCATIONS

logger = logging.getLogger(__name__)


class WeatherService:
    """
    High-level orchestrator service for weather fetch, ingestion, and reporting.
    """

    @classmethod
    def fetch_and_ingest(
        cls,
        db: Session,
        site_id: str,
        start_date: str,
        end_date: str,
        provider_name: Optional[str] = None,
    ) -> WeatherIngestSummary:
        """
        Fetch weather data for a site and date range, then ingest into the database.

        Args:
            db: Database session.
            site_id: Site identifier.
            start_date: Start date string (YYYY-MM-DD).
            end_date: End date string (YYYY-MM-DD).
            provider_name: Provider name or None to use default configured provider.

        Returns:
            WeatherIngestSummary detailing records processed, inserted, skipped, and rejected.
        """
        location = get_site_location(site_id)
        
        try:
            provider = get_provider(provider_name)
        except WeatherConfigurationError as e:
            logger.error("Weather configuration error: %s", e)
            return WeatherIngestSummary(
                site_id=site_id,
                provider=provider_name or WeatherConfig.PROVIDER,
                start_date=start_date,
                end_date=end_date,
                rows_received=0,
                rows_inserted=0,
                rows_skipped=0,
                rows_rejected=0,
                errors=[f"Configuration error: {str(e)}"],
            )

        try:
            # Parse dates
            s_date = date.fromisoformat(start_date)
            e_date = date.fromisoformat(end_date)
        except ValueError as e:
            return WeatherIngestSummary(
                site_id=site_id,
                provider=provider.provider_name,
                start_date=start_date,
                end_date=end_date,
                rows_received=0,
                rows_inserted=0,
                rows_skipped=0,
                rows_rejected=0,
                errors=[f"Invalid date format: {str(e)}"],
            )

        try:
            records = provider.fetch_hourly_weather(
                site_id=site_id,
                latitude=location.latitude,
                longitude=location.longitude,
                start_date=s_date,
                end_date=e_date,
                timezone=location.timezone,
            )
        except WeatherProviderError as e:
            logger.error("Failed to fetch weather from provider '%s': %s", provider.provider_name, e)
            return WeatherIngestSummary(
                site_id=site_id,
                provider=provider.provider_name,
                start_date=start_date,
                end_date=end_date,
                rows_received=0,
                rows_inserted=0,
                rows_skipped=0,
                rows_rejected=0,
                errors=[f"Provider error ({provider.provider_name}): {str(e)}"],
            )
        except Exception as e:
            logger.error("Unexpected error fetching weather: %s", e)
            return WeatherIngestSummary(
                site_id=site_id,
                provider=provider.provider_name,
                start_date=start_date,
                end_date=end_date,
                rows_received=0,
                rows_inserted=0,
                rows_skipped=0,
                rows_rejected=0,
                errors=[f"Unexpected error: {str(e)}"],
            )

        summary = WeatherIngestionService.ingest_records(
            db=db,
            records=records,
            site_id=site_id,
            provider=provider.provider_name,
            start_date=start_date,
            end_date=end_date,
        )

        return summary

    @classmethod
    def get_status(cls, db: Session) -> WeatherStatusResponse:
        """
        Get system status for weather integration.

        Returns:
            WeatherStatusResponse with current config and total record count.
        """
        total_records = WeatherIngestionService.count_records(db)
        
        return WeatherStatusResponse(
            configured_provider=WeatherConfig.PROVIDER,
            provider_requires_key=WeatherConfig.is_key_required(),
            api_key_configured=bool(WeatherConfig.API_KEY),
            status="ready",
            message="Weather subsystem operational.",
            available_sites=list(SITE_LOCATIONS.keys()),
            total_weather_records=total_records,
        )

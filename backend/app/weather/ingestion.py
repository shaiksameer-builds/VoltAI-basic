"""
VoltAI Weather Ingestion Service (Stage 9)

Provider-agnostic service that persists normalized weather records to the database.
This service accepts NormalizedWeatherRecord objects from ANY provider adapter.
It does NOT import Open-Meteo or any concrete provider directly.

Responsibilities:
  - Validate normalized records before persistence
  - Skip duplicates (site_id + timestamp uniqueness)
  - Return detailed ingestion summaries
  - Support repeated safe ingestion (idempotent)
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.database.models import WeatherReading
from backend.app.weather.schemas import (
    NormalizedWeatherRecord,
    WeatherIngestSummary,
)

logger = logging.getLogger(__name__)


class WeatherIngestionService:
    """
    Persists normalized weather records from any provider to the database.
    """

    @classmethod
    def ingest_records(
        cls,
        db: Session,
        records: List[NormalizedWeatherRecord],
        site_id: str,
        provider: str,
        start_date: str,
        end_date: str,
    ) -> WeatherIngestSummary:
        """
        Persist a list of normalized weather records.
        Skips duplicates, rejects invalid records, returns a summary.

        Args:
            db:         SQLAlchemy session.
            records:    Normalized records from any provider adapter.
            site_id:    Site identifier (used in summary).
            provider:   Provider name (used in summary).
            start_date: Date range string (summary only).
            end_date:   Date range string (summary only).

        Returns:
            WeatherIngestSummary with inserted/skipped/rejected counts.
        """
        rows_received = len(records)
        rows_inserted = 0
        rows_skipped = 0
        rows_rejected = 0
        errors: List[str] = []

        for record in records:
            try:
                result = cls._insert_one(db, record)
                if result == "inserted":
                    rows_inserted += 1
                elif result == "skipped":
                    rows_skipped += 1
            except Exception as exc:
                rows_rejected += 1
                msg = f"Rejected record at {record.timestamp}: {exc}"
                errors.append(msg)
                logger.warning("WeatherIngestion: %s", msg)
                # Roll back the failed unit before continuing
                db.rollback()

        return WeatherIngestSummary(
            site_id=site_id,
            provider=provider,
            start_date=start_date,
            end_date=end_date,
            rows_received=rows_received,
            rows_inserted=rows_inserted,
            rows_skipped=rows_skipped,
            rows_rejected=rows_rejected,
            errors=errors,
        )

    @classmethod
    def _insert_one(cls, db: Session, record: NormalizedWeatherRecord) -> str:
        """
        Attempt to insert a single weather record.

        Returns:
            'inserted' if new record was committed.
            'skipped'  if the (site_id, timestamp) already exists.

        Raises:
            Exception for unexpected errors.
        """
        # Check for existing record to avoid IntegrityError on unique constraint
        existing = db.scalars(
            select(WeatherReading).where(
                WeatherReading.site_id == record.site_id,
                WeatherReading.timestamp == record.timestamp,
            )
        ).first()

        if existing is not None:
            return "skipped"

        weather_row = WeatherReading(
            site_id=record.site_id,
            timestamp=record.timestamp,
            latitude=record.latitude,
            longitude=record.longitude,
            temperature_c=record.temperature_c,
            relative_humidity_pct=record.relative_humidity_pct,
            precipitation_mm=record.precipitation_mm,
            cloud_cover_pct=record.cloud_cover_pct,
            wind_speed_ms=record.wind_speed_ms,
            wind_direction_deg=record.wind_direction_deg,
            shortwave_radiation_wm2=record.shortwave_radiation_wm2,
            provider=record.provider,
            fetched_at=record.fetched_at,
        )
        db.add(weather_row)
        db.commit()
        return "inserted"

    @classmethod
    def get_weather_for_site(
        cls,
        db: Session,
        site_id: str,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[WeatherReading]:
        """
        Query persisted weather readings for a site with optional time range filtering.

        Args:
            db:       SQLAlchemy session.
            site_id:  Site identifier.
            start_ts: Optional inclusive start timestamp filter.
            end_ts:   Optional inclusive end timestamp filter.
            limit:    Max records to return (default 1000).

        Returns:
            List of WeatherReading ORM objects ordered by timestamp ascending.
        """
        stmt = (
            select(WeatherReading)
            .where(WeatherReading.site_id == site_id)
            .order_by(WeatherReading.timestamp.asc())
            .limit(limit)
        )
        if start_ts is not None:
            stmt = stmt.where(WeatherReading.timestamp >= start_ts)
        if end_ts is not None:
            stmt = stmt.where(WeatherReading.timestamp <= end_ts)

        return list(db.scalars(stmt).all())

    @classmethod
    def count_records(cls, db: Session, site_id: Optional[str] = None) -> int:
        """Return total stored weather records, optionally filtered by site."""
        from sqlalchemy import func
        from sqlalchemy.exc import OperationalError
        try:
            stmt = select(func.count()).select_from(WeatherReading)
            if site_id:
                stmt = stmt.where(WeatherReading.site_id == site_id)
            return db.scalar(stmt) or 0
        except OperationalError:
            return 0

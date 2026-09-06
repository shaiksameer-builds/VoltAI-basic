"""
VoltAI Energy Ingestion Service

Responsible for receiving normalized EnergyReadingCreate records from any data source
(CSV, IoT, Smart Meters, SCADA) and safely persisting them into the database.

Decoupled from input file formats: this service deals exclusively with validated
EnergyReadingCreate domain models and the SQLAlchemy persistence layer.
"""

from typing import Any, Dict, Iterable, List
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.models import EnergyReading
from backend.app.schemas.energy import EnergyReadingCreate


class IngestionSummary:
    """
    Data transfer object capturing statistics from a data ingestion operation.
    """

    def __init__(
        self,
        rows_received: int = 0,
        rows_inserted: int = 0,
        rows_rejected: int = 0,
        errors: List[str] | None = None,
    ):
        self.rows_received = rows_received
        self.rows_inserted = rows_inserted
        self.rows_rejected = rows_rejected
        self.errors = errors or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows_received": self.rows_received,
            "rows_inserted": self.rows_inserted,
            "rows_rejected": self.rows_rejected,
            "errors": self.errors,
        }


def persist_readings(
    db: Session,
    readings: Iterable[EnergyReadingCreate],
    batch_size: int = 500,
) -> IngestionSummary:
    """
    Persist an iterable of normalized EnergyReadingCreate models to the database.

    Args:
        db: Active SQLAlchemy database session.
        readings: Iterable yielding EnergyReadingCreate schemas.
        batch_size: Number of records to add before executing a flush.

    Returns:
        IngestionSummary: Detailed counts of received, inserted, and rejected rows.
    """
    summary = IngestionSummary()
    batch: List[EnergyReading] = []

    for reading in readings:
        summary.rows_received += 1
        try:
            db_model = EnergyReading(
                timestamp=reading.timestamp,
                site_id=reading.site_id,
                solar_generation=reading.solar_generation,
                wind_generation=reading.wind_generation,
                energy_consumption=reading.energy_consumption,
                battery_soc=reading.battery_soc,
                battery_charge=reading.battery_charge,
                battery_discharge=reading.battery_discharge,
                grid_import=reading.grid_import,
                grid_export=reading.grid_export,
            )
            batch.append(db_model)

            if len(batch) >= batch_size:
                db.add_all(batch)
                db.commit()
                summary.rows_inserted += len(batch)
                batch = []
        except Exception as e:
            summary.rows_rejected += 1
            summary.errors.append(f"Record {summary.rows_received}: {str(e)}")

    # Flush remaining records
    if batch:
        try:
            db.add_all(batch)
            db.commit()
            summary.rows_inserted += len(batch)
        except SQLAlchemyError as e:
            db.rollback()
            summary.rows_rejected += len(batch)
            summary.errors.append(f"Batch flush error: {str(e)}")

    return summary

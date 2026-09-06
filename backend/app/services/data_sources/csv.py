"""
VoltAI CSV Data Source Adapter

Implements CSVDataSource inheriting from BaseDataSource.
Normalizes canonical CSV telemetry into standard EnergyReadingCreate models.

Canonical CSV Column Specification:
    - timestamp: ISO 8601 observation interval timestamp
    - site_id: Facility / microgrid identifier string
    - solar_generation_kwh: Solar generation over interval in kWh
    - wind_generation_kwh: Wind generation over interval in kWh
    - energy_consumption_kwh: Total consumption over interval in kWh
    - battery_soc: Instantaneous State of Charge percentage (0.0 to 100.0)
    - battery_charge_kwh: Battery charging energy in kWh
    - battery_discharge_kwh: Battery discharging energy in kWh
    - grid_import_kwh: Energy imported from utility grid in kWh
    - grid_export_kwh: Energy exported to utility grid in kWh
"""

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Iterator, Union

from pydantic import ValidationError

from backend.app.schemas.energy import EnergyReadingCreate
from backend.app.services.data_sources.base import BaseDataSource

# Required headers that must exist in any valid telemetry CSV
REQUIRED_COLUMNS = {"timestamp", "site_id"}

# Canonical CSV column to EnergyReadingCreate field mapping
CANONICAL_COLUMN_MAP = {
    "solar_generation_kwh": "solar_generation",
    "wind_generation_kwh": "wind_generation",
    "energy_consumption_kwh": "energy_consumption",
    "battery_soc": "battery_soc",
    "battery_charge_kwh": "battery_charge",
    "battery_discharge_kwh": "battery_discharge",
    "grid_import_kwh": "grid_import",
    "grid_export_kwh": "grid_export",
}


def parse_timestamp(value: str) -> datetime:
    """
    Parse timestamp string safely into a timezone-aware datetime.
    Supports ISO 8601 (with 'Z' or offset) and common standard formats.
    """
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Timestamp value cannot be empty.")

    # Handle standard ISO 8601 with Z suffix
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        # Fallback to standard space-separated datetime format
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M:%S"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Invalid timestamp format: '{value}'. Expected ISO 8601.")

    # Ensure timezone awareness (default to UTC if missing)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def parse_numeric(value: str | None, field_name: str, row_idx: int) -> float | None:
    """
    Convert string value to float, handling empty/null strings gracefully.
    """
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() in ("nan", "none", "null", ""):
        return None

    try:
        val = float(cleaned)
    except (ValueError, TypeError):
        raise ValueError(
            f"Row {row_idx}: Non-numeric value '{cleaned}' for field '{field_name}'."
        )

    return val


class CSVDataSource(BaseDataSource):
    """
    Adapter that reads and validates CSV telemetry files, normalizing records
    into EnergyReadingCreate objects.
    """

    def __init__(self, source: Union[str, Path, IO[str], io.StringIO]):
        """
        Args:
            source: A file path (str or Path) or an open text stream / StringIO.
        """
        self._source = source

    @property
    def source_name(self) -> str:
        return "csv"

    def _get_reader(self) -> tuple[csv.DictReader, IO[str] | None]:
        """
        Obtain a csv.DictReader from either file path or stream.
        """
        if isinstance(self._source, (str, Path)):
            path = Path(self._source)
            if not path.exists():
                raise FileNotFoundError(f"CSV file not found: {path}")
            f = path.open("r", encoding="utf-8-sig", newline="")
            reader = csv.DictReader(f)
            return reader, f
        elif isinstance(self._source, io.StringIO):
            reader = csv.DictReader(self._source)
            return reader, None
        else:
            # IO stream (e.g. from UploadFile)
            reader = csv.DictReader(self._source)
            return reader, None

    def read_readings(self) -> Iterator[EnergyReadingCreate]:
        """
        Stream validated and normalized EnergyReadingCreate instances.
        Raises ValueError on missing columns or invalid data rows.
        """
        reader, file_handle = self._get_reader()

        try:
            if reader.fieldnames is None:
                raise ValueError("CSV file is empty or has no header row.")

            # Validate required columns
            fieldnames = {col.strip() for col in reader.fieldnames if col}
            missing_required = REQUIRED_COLUMNS - fieldnames
            if missing_required:
                raise ValueError(
                    f"CSV missing required columns: {sorted(list(missing_required))}. "
                    f"Found columns: {sorted(list(fieldnames))}."
                )

            for idx, raw_row in enumerate(reader, start=2):  # Header is row 1
                # Skip empty lines
                if not raw_row or not any(str(v).strip() for v in raw_row.values() if v is not None):
                    continue

                row = {k.strip(): v for k, v in raw_row.items() if k is not None}

                # Parse required fields
                site_id = (row.get("site_id") or "").strip()
                if not site_id:
                    raise ValueError(f"Row {idx}: 'site_id' is required and cannot be empty.")

                raw_ts = row.get("timestamp")
                if not raw_ts:
                    raise ValueError(f"Row {idx}: 'timestamp' is required and cannot be empty.")

                try:
                    ts = parse_timestamp(raw_ts)
                except ValueError as e:
                    raise ValueError(f"Row {idx}: {str(e)}")

                # Map numeric fields
                reading_kwargs = {
                    "timestamp": ts,
                    "site_id": site_id,
                }

                for csv_col, model_field in CANONICAL_COLUMN_MAP.items():
                    raw_val = row.get(csv_col)
                    # Fallback to model field name if canonical column wasn't used
                    if raw_val is None:
                        raw_val = row.get(model_field)

                    val = parse_numeric(raw_val, model_field, idx)
                    reading_kwargs[model_field] = val

                # Validate battery_soc bounds before model validation
                soc = reading_kwargs.get("battery_soc")
                if soc is not None and (soc < 0.0 or soc > 100.0):
                    raise ValueError(
                        f"Row {idx}: battery_soc must be between 0.0 and 100.0 (got {soc})."
                    )

                # Validate non-negative energy flows
                for energy_field in (
                    "solar_generation",
                    "wind_generation",
                    "energy_consumption",
                    "battery_charge",
                    "battery_discharge",
                    "grid_import",
                    "grid_export",
                ):
                    flow_val = reading_kwargs.get(energy_field)
                    if flow_val is not None and flow_val < 0.0:
                        raise ValueError(
                            f"Row {idx}: {energy_field} must be non-negative (got {flow_val})."
                        )

                # Instantiate Pydantic model for final validation
                try:
                    reading = EnergyReadingCreate(**reading_kwargs)
                except ValidationError as e:
                    raise ValueError(f"Row {idx}: Validation error: {e}")

                yield reading

        finally:
            if file_handle is not None:
                file_handle.close()

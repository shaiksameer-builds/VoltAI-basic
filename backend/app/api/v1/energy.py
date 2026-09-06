"""
VoltAI Energy Telemetry API Endpoints

Thin router layer connecting HTTP requests to data source adapters and the
ingestion service.
"""

import io
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.services.data_sources.csv import CSVDataSource
from backend.app.services.energy_ingestion import persist_readings

router = APIRouter(prefix="/api/v1/energy", tags=["Energy Ingestion"])


@router.post(
    "/ingest/csv",
    status_code=status.HTTP_200_OK,
    summary="Ingest hourly energy telemetry via CSV",
    description=(
        "Upload a canonical CSV file containing interval energy telemetry. "
        "The file is parsed via CSVDataSource, validated into EnergyReadingCreate schemas, "
        "and persisted to the database via the EnergyIngestionService."
    ),
)
async def ingest_csv(
    file: UploadFile = File(..., description="Canonical telemetry CSV file"),
    db: Session = Depends(get_db),
):
    """
    Ingest telemetry data from an uploaded CSV file.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format: '{filename}'. Expected a .csv file.",
        )

    try:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded CSV file is empty.",
            )

        text_content = content_bytes.decode("utf-8-sig")
        string_io = io.StringIO(text_content)
        data_source = CSVDataSource(string_io)

        # Collect readings (validating structure and rows)
        readings = list(data_source.read_readings())

        if not readings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file contains no valid data rows.",
            )

        # Pass normalized readings to the ingestion service
        summary = persist_readings(db=db, readings=readings)

        return {
            "status": "success",
            "message": "CSV telemetry successfully ingested.",
            "data": summary.to_dict(),
        }

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file encoding error. Please ensure file is UTF-8 encoded.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV validation error: {str(e)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during ingestion: {str(e)}",
        )

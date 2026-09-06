"""
VoltAI Anomalies API Router (Stage 8)
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.database.models import EnergyAnomaly
from backend.app.schemas.anomalies import (
    AnomalyDetectionRequest,
    AnomalyRecord,
    AnomalyResponse,
    AnomalySeverity,
    AnomalyStatus,
    AnomalySummary,
    AnomalyType,
)
from backend.app.services.anomaly_detection import AnomalyDetectionService

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.post("/detect", response_model=AnomalyResponse)
def detect_anomalies(
    request: AnomalyDetectionRequest,
    db: Session = Depends(get_db),
):
    """
    Triggers hybrid anomaly detection pipeline across site energy telemetry.
    """
    try:
        return AnomalyDetectionService.detect_site_anomalies(db=db, request=request)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}",
        )


@router.get("", response_model=List[AnomalyRecord])
def list_anomalies(
    site_id: Optional[str] = Query(None, description="Filter by site identifier"),
    anomaly_type: Optional[AnomalyType] = Query(None, description="Filter by anomaly taxonomy type"),
    severity: Optional[AnomalySeverity] = Query(None, description="Filter by severity level"),
    status_filter: Optional[AnomalyStatus] = Query(None, alias="status", description="Filter by anomaly status"),
    db: Session = Depends(get_db),
):
    """
    Retrieves filtered list of persisted energy anomalies.
    """
    stmt = select(EnergyAnomaly).order_by(EnergyAnomaly.timestamp.desc())
    if site_id:
        stmt = stmt.where(EnergyAnomaly.site_id == site_id)
    if anomaly_type:
        stmt = stmt.where(EnergyAnomaly.anomaly_type == anomaly_type.value)
    if severity:
        stmt = stmt.where(EnergyAnomaly.severity == severity.value)
    if status_filter:
        stmt = stmt.where(EnergyAnomaly.status == status_filter.value)

    records = db.scalars(stmt).all()
    return [
        AnomalyRecord(
            anomaly_id=r.anomaly_id,
            site_id=r.site_id,
            timestamp=r.timestamp,
            anomaly_type=AnomalyType(r.anomaly_type),
            severity=AnomalySeverity(r.severity),
            metric=r.metric,
            observed_value=r.observed_value,
            expected_value=r.expected_value,
            deviation=r.deviation,
            deviation_pct=r.deviation_pct,
            confidence=r.confidence,
            detection_method=r.detection_method,
            explanation=r.explanation,
            status=AnomalyStatus(r.status),
            related_energy_reading_id=r.related_energy_reading_id,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/summary", response_model=AnomalySummary)
def get_anomalies_summary(
    site_id: Optional[str] = Query(None, description="Filter summary by site identifier"),
    db: Session = Depends(get_db),
):
    """
    Gets summary counts of persisted anomalies grouped by severity and type.
    """
    stmt = select(EnergyAnomaly)
    if site_id:
        stmt = stmt.where(EnergyAnomaly.site_id == site_id)

    records = db.scalars(stmt).all()
    by_sev: dict[str, int] = {}
    by_typ: dict[str, int] = {}
    for r in records:
        by_sev[r.severity] = by_sev.get(r.severity, 0) + 1
        by_typ[r.anomaly_type] = by_typ.get(r.anomaly_type, 0) + 1

    return AnomalySummary(
        total_anomalies=len(records),
        by_severity=by_sev,
        by_type=by_typ,
    )


@router.get("/{anomaly_id}", response_model=AnomalyRecord)
def get_anomaly_by_id(
    anomaly_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieves complete record details for a specific anomaly ID.
    """
    r = db.scalars(select(EnergyAnomaly).where(EnergyAnomaly.anomaly_id == anomaly_id)).first()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly with ID '{anomaly_id}' not found.",
        )
    return AnomalyRecord(
        anomaly_id=r.anomaly_id,
        site_id=r.site_id,
        timestamp=r.timestamp,
        anomaly_type=AnomalyType(r.anomaly_type),
        severity=AnomalySeverity(r.severity),
        metric=r.metric,
        observed_value=r.observed_value,
        expected_value=r.expected_value,
        deviation=r.deviation,
        deviation_pct=r.deviation_pct,
        confidence=r.confidence,
        detection_method=r.detection_method,
        explanation=r.explanation,
        status=AnomalyStatus(r.status),
        related_energy_reading_id=r.related_energy_reading_id,
        created_at=r.created_at,
    )

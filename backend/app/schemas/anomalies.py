"""
VoltAI Anomaly Schemas (Stage 8)

Defines Pydantic models for energy anomaly taxonomy, detection requests, records, and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnomalyType(str, Enum):
    """
    Supported anomaly taxonomy for VoltAI energy telemetry and storage operations.
    """
    CONSUMPTION_SPIKE = "CONSUMPTION_SPIKE"
    CONSUMPTION_DROP = "CONSUMPTION_DROP"
    SOLAR_DROP = "SOLAR_DROP"
    WIND_DROP = "WIND_DROP"
    BATTERY_SOC_ANOMALY = "BATTERY_SOC_ANOMALY"
    BATTERY_CHARGE_ANOMALY = "BATTERY_CHARGE_ANOMALY"
    BATTERY_DISCHARGE_ANOMALY = "BATTERY_DISCHARGE_ANOMALY"
    GRID_IMPORT_SPIKE = "GRID_IMPORT_SPIKE"
    GRID_EXPORT_SPIKE = "GRID_EXPORT_SPIKE"
    RENEWABLE_OUTPUT_ANOMALY = "RENEWABLE_OUTPUT_ANOMALY"
    ENERGY_BALANCE_ANOMALY = "ENERGY_BALANCE_ANOMALY"
    SENSOR_DATA_ANOMALY = "SENSOR_DATA_ANOMALY"


class AnomalySeverity(str, Enum):
    """
    Severity rating levels for detected anomalies.
    """
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyStatus(str, Enum):
    """
    Lifecycle status of an anomaly record.
    """
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class AnomalyDetectionRequest(BaseModel):
    """
    Request parameters for triggering anomaly detection on a site.
    """
    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., min_length=1, description="Site identifier")
    start_time: Optional[datetime] = Field(None, description="Start timestamp filter (UTC)")
    end_time: Optional[datetime] = Field(None, description="End timestamp filter (UTC)")
    z_threshold: float = Field(3.0, gt=0.0, description="Robust Z-score threshold for statistical anomalies")
    persist: bool = Field(True, description="Save detected anomalies into database")


class AnomalyRecord(BaseModel):
    """
    Structured energy anomaly detail record.
    """
    model_config = ConfigDict(from_attributes=True)

    anomaly_id: str = Field(..., min_length=1, description="Unique anomaly record identifier")
    site_id: str = Field(..., min_length=1, description="Site identifier")
    timestamp: datetime = Field(..., description="Observation interval timestamp (UTC)")
    anomaly_type: AnomalyType = Field(..., description="Taxonomy classification of the anomaly")
    severity: AnomalySeverity = Field(..., description="Severity rating")
    metric: str = Field(..., min_length=1, description="Observed energy metric name")
    observed_value: float = Field(..., description="Observed metric value in energy unit")
    expected_value: float = Field(..., description="Expected baseline or forecast metric value")
    deviation: float = Field(..., description="Absolute numeric deviation (observed - expected)")
    deviation_pct: float = Field(..., description="Percentage deviation from expected value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence rating (0.0 to 1.0)")
    detection_method: str = Field(..., min_length=1, description="Method used (PHYSICAL_RULE, STATISTICAL_MAD, TIME_OF_DAY, FORECAST_RESIDUAL)")
    explanation: str = Field(..., min_length=1, description="Human-readable explanation of why this anomaly was flagged")
    status: AnomalyStatus = Field(AnomalyStatus.OPEN, description="Lifecycle status")
    related_energy_reading_id: Optional[int] = Field(None, description="ID of associated EnergyReading record")
    created_at: datetime = Field(..., description="Timestamp when anomaly was detected (UTC)")

    @field_validator("site_id", "metric", "detection_method", "explanation")
    @classmethod
    def validate_non_empty_str(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field must not be empty or whitespace")
        return v.strip()


class AnomalySummary(BaseModel):
    """
    Summary breakdown counts of detected anomalies.
    """
    model_config = ConfigDict(from_attributes=True)

    total_anomalies: int = Field(..., ge=0)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)


class AnomalyResponse(BaseModel):
    """
    Complete API response for anomaly detection runs or queries.
    """
    model_config = ConfigDict(from_attributes=True)

    anomaly_detection_run_id: str = Field(..., min_length=1, description="Unique detection run ID")
    site_id: str = Field(..., min_length=1)
    created_at: datetime = Field(...)
    records_examined: int = Field(..., ge=0)
    summary: AnomalySummary
    anomalies: List[AnomalyRecord]

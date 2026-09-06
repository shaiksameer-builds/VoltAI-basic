"""
VoltAI Forecasting Schemas

Defines Pydantic models for renewable generation and energy demand forecasting.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Supported forecast target types
ForecastTarget = Literal["solar", "wind", "demand", "renewable", "balance"]


class ForecastPoint(BaseModel):
    """
    Schema representing a single forecast point prediction for a specific site, target, and horizon step.
    """
    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., min_length=1, description="Site identifier")
    target: ForecastTarget = Field(..., description="Target metric (solar, wind, demand, renewable, balance)")
    target_timestamp: datetime = Field(..., description="Target timestamp of the forecast point (UTC)")
    horizon_step: int = Field(..., ge=1, le=24, description="Horizon step (1 to 24 hours)")
    predicted_value_kwh: float = Field(..., description="Predicted energy value in kWh (can be negative for balance)")
    model_version: str = Field(..., min_length=1, description="Version/name of the forecasting model used")

    forecast_run_id: str = Field(..., min_length=1, description="Unique execution run identifier")
    generated_at: datetime = Field(..., description="Timestamp when the forecast was generated (UTC)")

    @field_validator("site_id", "model_version", "forecast_run_id")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field must not be empty or whitespace only")
        return v.strip()


class ForecastResponse(BaseModel):
    """
    Schema representing the complete multi-step forecast response for a site and target.
    """
    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., min_length=1, description="Site identifier")
    target: ForecastTarget = Field(..., description="Target metric forecasted")
    horizon_hours: int = Field(..., ge=1, le=24, description="Total horizon length in hours (e.g. 1, 6, or 24)")
    generated_at: datetime = Field(..., description="Timestamp when the forecast was generated (UTC)")
    model_version: str = Field(..., min_length=1, description="Version/name of the forecasting model used")
    forecast_run_id: str = Field(..., min_length=1, description="Unique execution run identifier")
    predictions: List[ForecastPoint] = Field(..., description="List of forecast predictions")

    @field_validator("site_id", "model_version", "forecast_run_id")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field must not be empty or whitespace only")
        return v.strip()


class ModelTrainingResponse(BaseModel):
    """
    Schema representing training/evaluation status and baseline performance metrics.
    """
    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., min_length=1, description="Site identifier")
    target: ForecastTarget = Field(..., description="Target metric trained")
    model_version: str = Field(..., min_length=1, description="Version/name of the model")
    status: Literal["success", "failed", "in_progress"] = Field(..., description="Training job status")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Model evaluation metrics (e.g., MAE, RMSE)")
    trained_at: datetime = Field(..., description="Timestamp when model training completed (UTC)")
    message: Optional[str] = Field(default=None, description="Detailed message or log summary")

    @field_validator("site_id", "model_version")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("String field must not be empty or whitespace only")
        return v.strip()

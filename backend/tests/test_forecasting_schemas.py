"""
Tests for Forecasting Pydantic Schemas (Stage 6 — Step 1)
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.schemas.forecasting import (
    ForecastPoint,
    ForecastResponse,
    ModelTrainingResponse,
)


def test_valid_forecast_point():
    """Test constructing a valid ForecastPoint instance."""
    now = datetime.now(timezone.utc)
    point = ForecastPoint(
        site_id="site-alpha",
        target="solar",
        target_timestamp=now,
        horizon_step=1,
        predicted_value_kwh=42.5,
        model_version="v1.0-ridge",
        forecast_run_id="run-12345",
        generated_at=now,
    )
    assert point.site_id == "site-alpha"
    assert point.target == "solar"
    assert point.horizon_step == 1
    assert point.predicted_value_kwh == 42.5
    assert point.model_version == "v1.0-ridge"
    assert point.forecast_run_id == "run-12345"


def test_valid_forecast_response():
    """Test constructing a valid ForecastResponse instance with multiple predictions."""
    now = datetime.now(timezone.utc)
    predictions = [
        ForecastPoint(
            site_id="site-alpha",
            target="demand",
            target_timestamp=now,
            horizon_step=i,
            predicted_value_kwh=10.0 + i,
            model_version="v1.0-hgb",
            forecast_run_id="run-999",
            generated_at=now,
        )
        for i in range(1, 7)
    ]
    response = ForecastResponse(
        site_id="site-alpha",
        target="demand",
        horizon_hours=6,
        generated_at=now,
        model_version="v1.0-hgb",
        forecast_run_id="run-999",
        predictions=predictions,
    )
    assert response.site_id == "site-alpha"
    assert response.target == "demand"
    assert response.horizon_hours == 6
    assert len(response.predictions) == 6


def test_valid_model_training_response():
    """Test constructing a valid ModelTrainingResponse instance."""
    now = datetime.now(timezone.utc)
    res = ModelTrainingResponse(
        site_id="site-beta",
        target="wind",
        model_version="v1.0-wind-ridge",
        status="success",
        metrics={"mae": 2.15, "rmse": 3.40},
        trained_at=now,
        message="Model trained successfully",
    )
    assert res.site_id == "site-beta"
    assert res.status == "success"
    assert res.metrics["mae"] == 2.15


def test_invalid_forecast_target():
    """Test that invalid target values raise ValidationError."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ForecastPoint(
            site_id="site-alpha",
            target="nuclear",  # Invalid target
            target_timestamp=now,
            horizon_step=1,
            predicted_value_kwh=10.0,
            model_version="v1.0",
            forecast_run_id="run-1",
            generated_at=now,
        )


def test_invalid_horizon_step():
    """Test invalid horizon_step values (e.g. 0 or > 24)."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ForecastPoint(
            site_id="site-alpha",
            target="solar",
            target_timestamp=now,
            horizon_step=0,  # Below ge=1
            predicted_value_kwh=10.0,
            model_version="v1.0",
            forecast_run_id="run-1",
            generated_at=now,
        )

    with pytest.raises(ValidationError):
        ForecastPoint(
            site_id="site-alpha",
            target="solar",
            target_timestamp=now,
            horizon_step=25,  # Above le=24
            predicted_value_kwh=10.0,
            model_version="v1.0",
            forecast_run_id="run-1",
            generated_at=now,
        )


def test_balance_negative_predicted_value():
    """Test that negative predicted energy values are allowed for balance target (energy deficit)."""
    now = datetime.now(timezone.utc)
    point = ForecastPoint(
        site_id="site-alpha",
        target="balance",
        target_timestamp=now,
        horizon_step=1,
        predicted_value_kwh=-5.0,  # Valid negative energy balance (deficit)
        model_version="v1.0",
        forecast_run_id="run-1",
        generated_at=now,
    )
    assert point.predicted_value_kwh == -5.0



def test_empty_site_id():
    """Test that empty or whitespace-only site_id raises ValidationError."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ForecastPoint(
            site_id="   ",  # Whitespace only
            target="solar",
            target_timestamp=now,
            horizon_step=1,
            predicted_value_kwh=10.0,
            model_version="v1.0",
            forecast_run_id="run-1",
            generated_at=now,
        )


def test_schema_serialization():
    """Test JSON serialization and deserialization of ForecastResponse."""
    now = datetime.now(timezone.utc)
    point = ForecastPoint(
        site_id="site-alpha",
        target="renewable",
        target_timestamp=now,
        horizon_step=1,
        predicted_value_kwh=100.0,
        model_version="v1.0",
        forecast_run_id="run-100",
        generated_at=now,
    )
    response = ForecastResponse(
        site_id="site-alpha",
        target="renewable",
        horizon_hours=1,
        generated_at=now,
        model_version="v1.0",
        forecast_run_id="run-100",
        predictions=[point],
    )

    json_str = response.model_dump_json()
    deserialized = ForecastResponse.model_validate_json(json_str)
    assert deserialized.site_id == response.site_id
    assert deserialized.predictions[0].predicted_value_kwh == 100.0

"""
VoltAI Forecast API Routes (Stage 6 — Step 5)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.schemas.forecasting import ForecastResponse, ModelTrainingResponse
from backend.app.services.energy_forecasting import EnergyForecastingService

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


@router.post("/train", response_model=ModelTrainingResponse)
def train_forecasting_model(
    site_id: str = Query(..., min_length=1, description="Site identifier"),
    target: str = Query(..., description="Target metric (solar, wind, demand)"),
    force_retrain: bool = Query(False, description="Force retraining if model already exists"),
    db: Session = Depends(get_db),
):
    """
    Train a 24-step forecasting model for a site and target metric.
    """
    if target not in ["solar", "wind", "demand"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target '{target}'. Must be one of ['solar', 'wind', 'demand'].",
        )

    try:
        response = EnergyForecastingService.train_model(
            db=db, site_id=site_id, target=target, force_retrain=force_retrain
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model training failed: {str(e)}",
        )


@router.get("/generation", response_model=ForecastResponse)
def get_generation_forecast(
    site_id: str = Query(..., min_length=1, description="Site identifier"),
    target: str = Query("renewable", description="Generation target (solar, wind, renewable)"),
    horizon_hours: int = Query(24, ge=1, le=24, description="Forecast horizon in hours (1-24)"),
    db: Session = Depends(get_db),
):
    """
    Get multi-step generation forecast (solar, wind, or total renewable).
    """
    if target not in ["solar", "wind", "renewable"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid generation target '{target}'. Must be one of ['solar', 'wind', 'renewable'].",
        )

    try:
        return EnergyForecastingService.generate_forecast(
            db=db, site_id=site_id, target=target, horizon_hours=horizon_hours, persist=True
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation forecast failed: {str(e)}",
        )


@router.get("/demand", response_model=ForecastResponse)
def get_demand_forecast(
    site_id: str = Query(..., min_length=1, description="Site identifier"),
    horizon_hours: int = Query(24, ge=1, le=24, description="Forecast horizon in hours (1-24)"),
    db: Session = Depends(get_db),
):
    """
    Get multi-step energy demand/consumption forecast.
    """
    try:
        return EnergyForecastingService.generate_forecast(
            db=db, site_id=site_id, target="demand", horizon_hours=horizon_hours, persist=True
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Demand forecast failed: {str(e)}",
        )


@router.get("/balance", response_model=ForecastResponse)
def get_balance_forecast(
    site_id: str = Query(..., min_length=1, description="Site identifier"),
    horizon_hours: int = Query(24, ge=1, le=24, description="Forecast horizon in hours (1-24)"),
    db: Session = Depends(get_db),
):
    """
    Get multi-step predicted energy balance (Renewable Generation - Demand).
    Positive = predicted surplus, Negative = predicted deficit.
    """
    try:
        return EnergyForecastingService.generate_balance_forecast(
            db=db, site_id=site_id, horizon_hours=horizon_hours, persist=True
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Balance forecast failed: {str(e)}",
        )

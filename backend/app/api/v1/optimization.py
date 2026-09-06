"""
VoltAI Optimization API Router (Stage 7)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.schemas.optimization import (
    OptimizationRequest,
    OptimizationResponse,
)
from backend.app.services.battery_optimization import BatteryOptimizationService

router = APIRouter(prefix="/optimization", tags=["Optimization"])


@router.post("/run", response_model=OptimizationResponse)
def run_battery_optimization(
    request: OptimizationRequest,
    db: Session = Depends(get_db),
):
    """
    Triggers an optimal 24-step battery storage dispatch schedule calculation.
    """
    try:
        response = BatteryOptimizationService.optimize_schedule(db=db, request=request, persist=True)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Battery optimization failed: {str(e)}",
        )


@router.get("/{optimization_run_id}", response_model=OptimizationResponse)
def get_optimization_run(
    optimization_run_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieves a previously persisted optimization run and schedule points by run ID.
    """
    result = BatteryOptimizationService.get_persisted_run(db=db, optimization_run_id=optimization_run_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Optimization run '{optimization_run_id}' not found.",
        )
    return result

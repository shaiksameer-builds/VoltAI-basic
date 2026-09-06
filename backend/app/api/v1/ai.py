"""
VoltAI AI Intelligence API Endpoints (Stage 10)

Provides natural language interaction, explanation endpoints, and AI subsystem status.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.ai.schemas import (
    AIExplanationResponse,
    AIIntentEnum,
    AIRequest,
    AIStatusResponse,
    ExplainAnomalyRequest,
    ExplainForecastRequest,
    ExplainOptimizationRequest,
)
from backend.app.ai.service import AIService
from backend.app.database.connection import get_db

router = APIRouter(prefix="/api/v1/ai", tags=["AI Intelligence & Explanation"])


@router.post(
    "/chat",
    response_model=AIExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask VoltAI natural language questions",
    description="Submits a question to VoltAI's grounded AI assistant for natural language explanation.",
)
async def ai_chat(
    request: AIRequest,
    db: Session = Depends(get_db),
):
    """
    General natural language assistant endpoint.
    """
    return AIService.ask(db=db, request=request)


@router.post(
    "/explain/forecast",
    response_model=AIExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Explain energy forecast",
    description="Generates a grounded natural language explanation of a site's energy forecast.",
)
async def explain_forecast(
    request: ExplainForecastRequest,
    db: Session = Depends(get_db),
):
    """
    Explain energy forecast for a site.
    """
    ai_req = AIRequest(
        query=f"Explain the 24-hour {request.target} forecast for site {request.site_id}",
        site_id=request.site_id,
        intent_override=AIIntentEnum.FORECAST_EXPLANATION,
    )
    return AIService.ask(db=db, request=ai_req)


@router.post(
    "/explain/optimization",
    response_model=AIExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Explain battery optimization schedule",
    description="Generates a grounded explanation of the battery charge/discharge schedule and cost savings.",
)
async def explain_optimization(
    request: ExplainOptimizationRequest,
    db: Session = Depends(get_db),
):
    """
    Explain battery optimization schedule.
    """
    ai_req = AIRequest(
        query=f"Explain the battery optimization schedule and grid cost savings for site {request.site_id}",
        site_id=request.site_id,
        intent_override=AIIntentEnum.BATTERY_EXPLANATION,
    )
    return AIService.ask(db=db, request=ai_req)


@router.post(
    "/explain/anomaly",
    response_model=AIExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Explain energy anomalies",
    description="Explains detected physical and statistical energy anomalies for a site.",
)
async def explain_anomaly(
    request: ExplainAnomalyRequest,
    db: Session = Depends(get_db),
):
    """
    Explain detected energy anomalies.
    """
    ai_req = AIRequest(
        query=f"Explain the detected energy anomalies and root causes for site {request.site_id}",
        site_id=request.site_id,
        intent_override=AIIntentEnum.ANOMALY_EXPLANATION,
    )
    return AIService.ask(db=db, request=ai_req)


@router.get(
    "/status",
    response_model=AIStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI subsystem status",
    description="Returns the status of the AI layer, active provider, model name, and credential status.",
)
async def get_ai_status(
    db: Session = Depends(get_db),
):
    """
    Get AI layer status.
    """
    return AIService.get_status(db=db)

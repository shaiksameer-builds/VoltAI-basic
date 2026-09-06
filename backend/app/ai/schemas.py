"""
VoltAI AI Pydantic Schemas (Stage 10)

Schemas for natural-language AI requests, intent routing, structured explanations,
and subsystem status reporting.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AIIntentEnum(str, Enum):
    """Supported intent classification categories."""
    ENERGY_SUMMARY = "ENERGY_SUMMARY"
    FORECAST_EXPLANATION = "FORECAST_EXPLANATION"
    BATTERY_EXPLANATION = "BATTERY_EXPLANATION"
    ANOMALY_EXPLANATION = "ANOMALY_EXPLANATION"
    WEATHER_EXPLANATION = "WEATHER_EXPLANATION"
    SITE_COMPARISON = "SITE_COMPARISON"
    GENERAL_ENERGY_QUESTION = "GENERAL_ENERGY_QUESTION"


class AIRequest(BaseModel):
    """Natural-language question or explanation request."""

    query: str = Field(..., min_length=1, max_length=1000, description="Natural language query from user")
    site_id: Optional[str] = Field(default=None, description="Site ID scoping context (e.g. site_001)")
    start_date: Optional[str] = Field(default=None, description="Start date YYYY-MM-DD for context window")
    end_date: Optional[str] = Field(default=None, description="End date YYYY-MM-DD for context window")
    intent_override: Optional[AIIntentEnum] = Field(default=None, description="Explicit intent override")


class ExplainForecastRequest(BaseModel):
    """Request for explaining a specific site's forecast."""
    site_id: str = Field(..., description="Site ID (e.g. site_001)")
    target: str = Field(default="solar_generation", description="solar_generation or energy_consumption")


class ExplainOptimizationRequest(BaseModel):
    """Request for explaining a site's battery optimization schedule."""
    site_id: str = Field(..., description="Site ID (e.g. site_001)")
    battery_capacity_kwh: float = Field(default=100.0, gt=0.0)
    max_charge_kw: float = Field(default=25.0, gt=0.0)
    max_discharge_kw: float = Field(default=25.0, gt=0.0)


class ExplainAnomalyRequest(BaseModel):
    """Request for explaining detected anomalies at a site."""
    site_id: str = Field(..., description="Site ID (e.g. site_001)")
    z_threshold: float = Field(default=3.0, ge=1.0, le=10.0)


class AIExplanationResponse(BaseModel):
    """Structured response returned by the AI service."""

    response: str = Field(..., description="Natural language explanation")
    intent: AIIntentEnum = Field(..., description="Classified query intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (uncalibrated heuristic)")
    source_context: Dict[str, Any] = Field(..., description="Structured facts and metrics supplied to LLM")
    facts_used: List[str] = Field(default_factory=list, description="Key deterministic metric summary")
    warnings: List[str] = Field(default_factory=list, description="Caveats or fallback warnings")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_fallback: bool = Field(default=False, description="True if response generated via deterministic fallback")
    provider_used: str = Field(default="gemini")

    model_config = ConfigDict(from_attributes=True)


class AIStatusResponse(BaseModel):
    """Subsystem status for the AI explanation layer."""

    configured: bool = Field(..., description="True if provider config is valid")
    selected_provider: str = Field(..., description="Configured LLM provider name")
    model_name: str = Field(..., description="Configured model name")
    api_key_configured: bool = Field(..., description="True if API key is set (never exposes key)")
    availability_status: str = Field(..., description="'ready' or 'fallback_mode'")

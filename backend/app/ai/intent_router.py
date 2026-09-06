"""
VoltAI Intent Router (Stage 10)

Lightweight deterministic classification routing user queries to specific AI context profiles
without requiring an LLM call for routing.
"""

import re
from typing import Tuple

from backend.app.ai.schemas import AIIntentEnum


class IntentRouter:
    """
    Deterministic keyword & rule-based intent router.
    """

    @classmethod
    def classify_intent(cls, query: str) -> Tuple[AIIntentEnum, float]:
        """
        Classify user query into an AIIntentEnum and return a heuristic confidence score.

        Args:
            query: User prompt text.

        Returns:
            Tuple of (AIIntentEnum, confidence_float)
        """
        text = query.lower().strip()

        # Anomaly keywords
        if any(w in text for w in ["anomaly", "anomalies", "spike", "out of bounds", "irregular", "issue", "fault", "unusual", "warning"]):
            return AIIntentEnum.ANOMALY_EXPLANATION, 0.90

        # Battery / Optimization keywords
        if any(w in text for w in ["battery", "charge", "discharge", "soc", "state of charge", "optimize", "optimization", "storage", "schedule"]):
            return AIIntentEnum.BATTERY_EXPLANATION, 0.90

        # Forecast keywords
        if any(w in text for w in ["forecast", "predict", "tomorrow", "future", "expected", "upcoming", "solar generation next", "demand next"]):
            return AIIntentEnum.FORECAST_EXPLANATION, 0.90

        # Weather keywords
        if any(w in text for w in ["weather", "temperature", "cloud", "rain", "precipitation", "wind", "irradiance", "sunshine"]):
            return AIIntentEnum.WEATHER_EXPLANATION, 0.85

        # Site comparison keywords
        if any(w in text for w in ["compare", "comparison", "highest site", "top site", "which site", "most energy", "most consuming", "site comparison"]):
            return AIIntentEnum.SITE_COMPARISON, 0.85

        # General energy summary keywords
        if any(w in text for w in ["summary", "overview", "today's performance", "performance", "how is the site", "status", "grid import"]):
            return AIIntentEnum.ENERGY_SUMMARY, 0.80

        # Fallback for open-ended queries
        return AIIntentEnum.GENERAL_ENERGY_QUESTION, 0.60

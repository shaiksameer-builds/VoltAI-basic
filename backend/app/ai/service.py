"""
VoltAI AI Service Orchestrator (Stage 10)

High-level service coordinating:
  1. Intent classification via IntentRouter
  2. Bounded context collection via AIContextBuilder
  3. LLM grounding via prompts
  4. Provider-agnostic LLM execution (Gemini)
  5. Deterministic fallback handling on missing credentials/quota/timeouts

The system NEVER crashes if LLM API is unavailable.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.ai.config import AIConfig
from backend.app.ai.context_builder import AIContextBuilder
from backend.app.ai.factory import get_llm_provider
from backend.app.ai.intent_router import IntentRouter
from backend.app.ai.prompts import (
    SYSTEM_GROUNDING_INSTRUCTION,
    format_fallback_response,
    format_user_prompt,
)
from backend.app.ai.providers import LLMError
from backend.app.ai.schemas import (
    AIExplanationResponse,
    AIIntentEnum,
    AIRequest,
    AIStatusResponse,
)

logger = logging.getLogger(__name__)


class AIService:
    """
    AI orchestrator service.
    """

    @classmethod
    def ask(cls, db: Session, request: AIRequest) -> AIExplanationResponse:
        """
        Process a user question, route intent, collect context, execute LLM or fallback,
        and return a structured response.
        """
        # 1. Intent Routing
        if request.intent_override:
            intent = request.intent_override
            confidence = 1.0
        else:
            intent, confidence = IntentRouter.classify_intent(request.query)

        # 2. Context Building
        context = AIContextBuilder.build_context_for_intent(
            db=db,
            intent=intent.value,
            site_id=request.site_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        facts_used = cls._extract_facts_summary(context)
        warnings: List[str] = []

        # 3. Check Credentials & Provider Availability
        if not AIConfig.is_api_key_configured():
            reason = "GEMINI_API_KEY unconfigured"
            warnings.append(reason)
            fallback_text = format_fallback_response(request.query, intent.value, context, reason=reason)
            return AIExplanationResponse(
                response=fallback_text,
                intent=intent,
                confidence=confidence,
                source_context=context,
                facts_used=facts_used,
                warnings=warnings,
                is_fallback=True,
                provider_used=AIConfig.PROVIDER,
            )

        # 4. LLM Execution with Fallback Protection
        try:
            provider = get_llm_provider()
            user_prompt = format_user_prompt(request.query, intent.value, context)
            
            explanation = provider.generate_explanation(
                system_instruction=SYSTEM_GROUNDING_INSTRUCTION,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=1024,
            )

            return AIExplanationResponse(
                response=explanation,
                intent=intent,
                confidence=confidence,
                source_context=context,
                facts_used=facts_used,
                warnings=warnings,
                is_fallback=False,
                provider_used=provider.provider_name,
            )

        except LLMError as exc:
            logger.warning("AIService fallback triggered due to LLM error: %s", exc)
            reason = f"LLM Provider Error: {type(exc).__name__}"
            warnings.append(reason)
            fallback_text = format_fallback_response(request.query, intent.value, context, reason=reason)
            
            return AIExplanationResponse(
                response=fallback_text,
                intent=intent,
                confidence=confidence,
                source_context=context,
                facts_used=facts_used,
                warnings=warnings,
                is_fallback=True,
                provider_used=AIConfig.PROVIDER,
            )
        except Exception as exc:
            logger.error("Unexpected error in AIService: %s", exc)
            reason = "Unexpected error"
            warnings.append(reason)
            fallback_text = format_fallback_response(request.query, intent.value, context, reason=reason)
            
            return AIExplanationResponse(
                response=fallback_text,
                intent=intent,
                confidence=confidence,
                source_context=context,
                facts_used=facts_used,
                warnings=warnings,
                is_fallback=True,
                provider_used=AIConfig.PROVIDER,
            )

    @classmethod
    def get_status(cls, db: Session) -> AIStatusResponse:
        """
        Return system status of the AI layer.
        """
        is_configured = AIConfig.is_api_key_configured()
        return AIStatusResponse(
            configured=is_configured,
            selected_provider=AIConfig.PROVIDER,
            model_name=AIConfig.GEMINI_MODEL,
            api_key_configured=is_configured,
            availability_status="ready" if is_configured else "fallback_mode",
        )

    @staticmethod
    def _extract_facts_summary(context: Dict[str, Any]) -> List[str]:
        facts = []
        analytics = context.get("analytics_summary") or {}
        if analytics:
            facts.append(f"Consumption: {analytics.get('total_consumption_kwh')} kWh")
            facts.append(f"Renewable Fraction: {analytics.get('renewable_fraction_pct')}%")
        
        telemetry = context.get("latest_telemetry") or {}
        if telemetry:
            facts.append(f"Latest Battery SOC: {telemetry.get('battery_soc_pct')}%")

        anomalies = context.get("detected_anomalies") or []
        facts.append(f"Detected Anomalies: {len(anomalies)}")

        return facts

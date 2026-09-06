"""
Comprehensive Unit & Integration Test Suite for AI Intelligence & Explanation Layer (Stage 10)
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.connection import Base, init_db, get_db
from backend.app.database.models import EnergyReading, WeatherReading
from backend.app.main import app
from backend.app.ai.config import AIConfig, AIConfigurationError
from backend.app.ai.context_builder import AIContextBuilder
from backend.app.ai.factory import get_llm_provider
from backend.app.ai.intent_router import IntentRouter
from backend.app.ai.prompts import SYSTEM_GROUNDING_INSTRUCTION, format_user_prompt
from backend.app.ai.providers import (
    BaseLLMProvider,
    LLMAuthError,
    LLMProviderError,
    LLMQuotaError,
    LLMTimeoutError,
)
from backend.app.ai.providers.gemini import GeminiProvider
from backend.app.ai.schemas import (
    AIExplanationResponse,
    AIIntentEnum,
    AIRequest,
    ExplainForecastRequest,
    ExplainOptimizationRequest,
    ExplainAnomalyRequest,
)
from backend.app.ai.service import AIService


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session, engine
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_with_telemetry(test_db):
    session, engine = test_db
    start_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    readings = [
        EnergyReading(
            timestamp=start_time + timedelta(hours=i),
            site_id="site_001",
            solar_generation=50.0 if 6 <= (i % 24) <= 18 else 0.0,
            wind_generation=10.0,
            energy_consumption=30.0,
            grid_import=20.0,
            grid_export=0.0,
            battery_soc=50.0,
            battery_charge=0.0,
            battery_discharge=0.0,
        )
        for i in range(48)
    ]
    session.add_all(readings)
    session.commit()
    return session, engine


# ----------------------------------------------------
# 1. Intent Router Tests
# ----------------------------------------------------

def test_intent_router_classification():
    """Test deterministic intent routing for various keyword patterns."""
    assert IntentRouter.classify_intent("Why is there a spike in consumption?")[0] == AIIntentEnum.ANOMALY_EXPLANATION
    assert IntentRouter.classify_intent("Should the battery charge now?")[0] == AIIntentEnum.BATTERY_EXPLANATION
    assert IntentRouter.classify_intent("What is tomorrow's solar forecast?")[0] == AIIntentEnum.FORECAST_EXPLANATION
    assert IntentRouter.classify_intent("How is the weather affecting solar generation?")[0] == AIIntentEnum.WEATHER_EXPLANATION
    assert IntentRouter.classify_intent("Show me today's energy summary")[0] == AIIntentEnum.ENERGY_SUMMARY
    assert IntentRouter.classify_intent("Which site consumes the most energy?")[0] == AIIntentEnum.SITE_COMPARISON
    assert IntentRouter.classify_intent("Tell me about VoltAI")[0] == AIIntentEnum.GENERAL_ENERGY_QUESTION


# ----------------------------------------------------
# 2. Provider Abstraction & Error Handling
# ----------------------------------------------------

def test_gemini_provider_missing_key():
    """Test GeminiProvider raises LLMAuthError when API key is empty."""
    provider = GeminiProvider(api_key="")
    with pytest.raises(LLMAuthError):
        provider.generate_explanation("system", "user")


def test_gemini_provider_mocked_success():
    """Test GeminiProvider successfully parses API response with mocked client."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Solar generation is expected to peak at 12 PM."}]
                }
            }
        ]
    }
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = mock_response

    provider = GeminiProvider(api_key="mock_key", http_client=mock_client)
    res = provider.generate_explanation("system instruction", "user prompt")

    assert "Solar generation is expected to peak" in res
    assert provider.provider_name == "gemini"
    assert provider.model_name == "gemini-1.5-flash"


def test_gemini_provider_error_mappings():
    """Test Gemini HTTP status codes map to specific LLM exceptions."""
    mock_client = MagicMock(spec=httpx.Client)

    # 401 Auth Error
    mock_resp_401 = MagicMock(status_code=401)
    mock_client.post.return_value = mock_resp_401
    p = GeminiProvider(api_key="bad_key", http_client=mock_client)
    with pytest.raises(LLMAuthError):
        p.generate_explanation("sys", "usr")

    # 429 Quota Error
    mock_resp_429 = MagicMock(status_code=429)
    mock_client.post.return_value = mock_resp_429
    with pytest.raises(LLMQuotaError):
        p.generate_explanation("sys", "usr")

    # 500 Server Error
    mock_resp_500 = MagicMock(status_code=500, text="Internal Error")
    mock_client.post.return_value = mock_resp_500
    with pytest.raises(LLMProviderError):
        p.generate_explanation("sys", "usr")


# ----------------------------------------------------
# 3. Context Builder Tests
# ----------------------------------------------------

def test_ai_context_builder(db_with_telemetry):
    """Test AIContextBuilder constructs structured bounded context."""
    session, _ = db_with_telemetry
    ctx = AIContextBuilder.build_context_for_intent(session, "ENERGY_SUMMARY", site_id="site_001")

    assert ctx["site_id"] == "site_001"
    assert "analytics_summary" in ctx
    assert "latest_telemetry" in ctx
    assert ctx["latest_telemetry"]["solar_kw"] >= 0.0


# ----------------------------------------------------
# 4. Service & Fallback Handling Tests
# ----------------------------------------------------

def test_ai_service_fallback_on_unconfigured_key(db_with_telemetry):
    """Test AIService gracefully returns fallback response when API key is missing."""
    session, _ = db_with_telemetry
    req = AIRequest(query="What is today's solar summary?", site_id="site_001")

    with patch.object(AIConfig, "GEMINI_API_KEY", ""):
        res = AIService.ask(session, req)
        assert res.is_fallback is True
        assert res.intent == AIIntentEnum.ENERGY_SUMMARY
        assert "VoltAI System Status for site_001" in res.response
        assert "GEMINI_API_KEY unconfigured" in res.warnings[0]


def test_ai_service_with_mocked_llm(db_with_telemetry):
    """Test AIService end-to-end execution with mocked LLM provider."""
    session, _ = db_with_telemetry
    req = AIRequest(query="Explain current energy status", site_id="site_001")

    with patch.object(AIConfig, "GEMINI_API_KEY", "valid_key"):
        with patch("backend.app.ai.service.get_llm_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.provider_name = "gemini"
            mock_provider.generate_explanation.return_value = "Everything is running smoothly with high solar output."
            mock_get_provider.return_value = mock_provider

            res = AIService.ask(session, req)
            assert res.is_fallback is False
            assert "Everything is running smoothly" in res.response
            assert res.provider_used == "gemini"


# ----------------------------------------------------
# 5. API Endpoint Tests
# ----------------------------------------------------

def test_ai_api_endpoints(db_with_telemetry):
    """Test FastAPI endpoints (/chat, /explain/*, /status)."""
    session, _ = db_with_telemetry
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: session

    try:
        # GET /api/v1/ai/status
        res_status = client.get("/api/v1/ai/status")
        assert res_status.status_code == 200
        assert "selected_provider" in res_status.json()

        # POST /api/v1/ai/chat
        chat_req = {"query": "What is the energy summary?", "site_id": "site_001"}
        res_chat = client.post("/api/v1/ai/chat", json=chat_req)
        assert res_chat.status_code == 200
        assert "response" in res_chat.json()
        assert res_chat.json()["intent"] == "ENERGY_SUMMARY"

        # POST /api/v1/ai/explain/forecast
        res_fc = client.post("/api/v1/ai/explain/forecast", json={"site_id": "site_001", "target": "solar_generation"})
        assert res_fc.status_code == 200
        assert res_fc.json()["intent"] == "FORECAST_EXPLANATION"

        # POST /api/v1/ai/explain/optimization
        res_opt = client.post("/api/v1/ai/explain/optimization", json={"site_id": "site_001"})
        assert res_opt.status_code == 200
        assert res_opt.json()["intent"] == "BATTERY_EXPLANATION"

        # POST /api/v1/ai/explain/anomaly
        res_anom = client.post("/api/v1/ai/explain/anomaly", json={"site_id": "site_001"})
        assert res_anom.status_code == 200
        assert res_anom.json()["intent"] == "ANOMALY_EXPLANATION"

    finally:
        app.dependency_overrides.clear()

# VoltAI — AI Intelligence & Explanation Layer (Stage 10)

## Executive Summary

Stage 10 introduces a natural-language interaction, reasoning, and explanation layer on top of VoltAI's deterministic intelligence engines.

> **Crucial Architectural Principle**:
> Gemini serves strictly as an **explanation and natural-language interaction layer**. It does NOT perform energy calculations, modify database state, create new forecasts, or alter optimization schedules. The deterministic VoltAI engines (Analytics, Forecasting, Optimization, Anomaly Detection, Weather Integration) remain the sole sources of truth.

---

## Core Architecture

```
User / Frontend / API
        │
        ▼
   FastAPI Router (/api/v1/ai/*)
        │
        ▼
   AIService Orchestrator
        │
        ├───────────────────────┐
        ▼                       ▼
  IntentRouter          AIContextBuilder
  (Keyword / Rules)     (Bounded Grounded Context)
        │                       │
        │      ┌────────────────┴────────────────┐
        │      ▼                                 ▼
        │   VoltAI Deterministic Engines     Weather Data
        │   (Analytics/Forecast/Opt/Anom)   (Stage 9)
        │      └────────────────┬────────────────┘
        │                       │
        └───────────────┬───────┘
                        ▼
                Prompts Formatter
             (System Grounding Rules)
                        │
                        ▼
               BaseLLMProvider (ABC)
                        │
                        ▼
                 GeminiProvider
            (Google Gemini 1.5 Flash)
```

---

## Provider-Agnostic LLM Architecture

VoltAI defines an Abstract Base Class `BaseLLMProvider` in `backend/app/ai/providers/__init__.py`.

The high-level `AIService` depends strictly on `BaseLLMProvider`, allowing easy substitution of future LLM backends (e.g. Claude, OpenAI, local Llama) without altering business logic.

```python
class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def generate_explanation(self, system_instruction: str, user_prompt: str, ...) -> str: ...
```

---

## Environment & Configuration

Environment variables configured in `.env`:

```env
# Active LLM Provider
LLM_PROVIDER=gemini

# API Key (Required for natural language synthesis, optional for core VoltAI platform)
GEMINI_API_KEY=

# Model Name
GEMINI_MODEL=gemini-1.5-flash

# Timeout & Retries
LLM_TIMEOUT_SECONDS=15
LLM_MAX_RETRIES=1
```

### Zero Secret Logging Policy
- `GEMINI_API_KEY` is never printed to logs or included in error tracebacks.
- If credentials are empty or missing, VoltAI seamlessly enters **Deterministic Fallback Mode**.

---

## Deterministic Fallback Mode

If any of the following occur:
1. `GEMINI_API_KEY` is missing or unconfigured.
2. HTTP 401 / 403 Authentication Error.
3. HTTP 429 Rate Limit / Quota Exceeded.
4. HTTP Timeout or Connection Error.
5. Malformed API Response.

VoltAI **NEVER crashes**. The system automatically generates a structured natural-language fallback response built directly from the grounded context.

---

## Grounding & Safety Guardrails

All LLM calls enforce strict system instructions:
1. Use **only** supplied VoltAI context.
2. Never invent numerical values, measurements, or forecasts.
3. Never invent optimization schedules.
4. Never claim an anomaly exists unless supplied by VoltAI.
5. Explicitly label uncertainty.
6. Distinguish **FACT** (observed telemetry) from **POSSIBLE CAUSE** (analytical explanation).
7. If requested data is missing, state: `"Data is currently unavailable in VoltAI."`

---

## Intent Classification

The `IntentRouter` classifies user questions deterministically into categories:

| Intent | Description | Context Included |
|---|---|---|
| `ENERGY_SUMMARY` | General overview of energy performance | Analytics, Telemetry, Weather |
| `FORECAST_EXPLANATION` | Explanation of expected generation/demand | 24h Solar Forecast, Weather |
| `BATTERY_EXPLANATION` | Explanation of battery charge/discharge decisions | Optimization Schedule, Tariff |
| `ANOMALY_EXPLANATION` | Explanation of detected irregularities | Anomaly Records, Rules violated |
| `WEATHER_EXPLANATION` | Explanation of weather impact on energy | Temperature, Humidity, Irradiance |
| `SITE_COMPARISON` | Comparative metrics across sites | Site Analytics |
| `GENERAL_ENERGY_QUESTION` | Open-ended question | Full bounded context |

---

## API Endpoints

- `POST /api/v1/ai/chat` — Submit open natural-language questions
- `POST /api/v1/ai/explain/forecast` — Explain 24-hour forecast
- `POST /api/v1/ai/explain/optimization` — Explain battery optimization schedule
- `POST /api/v1/ai/explain/anomaly` — Explain detected energy anomalies
- `GET /api/v1/ai/status` — Get AI subsystem readiness and provider status

---

## Testing & Quota Protection

- Unit tests mock all LLM network calls using `httpx.Client` injection.
- Zero real Gemini API quota is consumed during automated test execution.
- Run complete test suite:
  ```bash
  python -m pytest -q
  ```

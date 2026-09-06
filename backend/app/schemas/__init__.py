"""
VoltAI Schemas Package
"""

from backend.app.schemas.analytics import (
    DailyAnalyticsItem,
    DailyAnalyticsResponse,
    EnergySummaryResponse,
    PeakDemandResponse,
    SiteAnalyticsItem,
    SiteAnalyticsResponse,
)
from backend.app.schemas.energy import (
    EnergyReadingBase,
    EnergyReadingCreate,
    EnergyReadingResponse,
)

from backend.app.schemas.forecasting import (
    ForecastPoint,
    ForecastResponse,
    ForecastTarget,
    ModelTrainingResponse,
)
from backend.app.schemas.anomalies import (
    AnomalyDetectionRequest,
    AnomalyRecord,
    AnomalyResponse,
    AnomalySeverity,
    AnomalyStatus,
    AnomalySummary,
    AnomalyType,
)
from backend.app.schemas.optimization import (
    BatteryConfig,
    GridPricingConfig,
    OptimizationPoint,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationSummary,
)
from backend.app.schemas.weather import (
    NormalizedWeatherRecord,
    WeatherFeatures,
    WeatherIngestRequest,
    WeatherIngestSummary,
    WeatherRecord,
    WeatherStatusResponse,
)
from backend.app.schemas.ai import (
    AIExplanationResponse,
    AIIntentEnum,
    AIRequest,
    AIStatusResponse,
    ExplainAnomalyRequest,
    ExplainForecastRequest,
    ExplainOptimizationRequest,
)

__all__ = [
    "EnergyReadingBase",
    "EnergyReadingCreate",
    "EnergyReadingResponse",
    "EnergySummaryResponse",
    "DailyAnalyticsItem",
    "DailyAnalyticsResponse",
    "SiteAnalyticsItem",
    "SiteAnalyticsResponse",
    "PeakDemandResponse",
    "ForecastTarget",
    "ForecastPoint",
    "ForecastResponse",
    "ModelTrainingResponse",
    "BatteryConfig",
    "GridPricingConfig",
    "OptimizationPoint",
    "OptimizationRequest",
    "OptimizationResponse",
    "OptimizationSummary",
    "AnomalyType",
    "AnomalySeverity",
    "AnomalyStatus",
    "AnomalyDetectionRequest",
    "AnomalyRecord",
    "AnomalySummary",
    "AnomalyResponse",
    "NormalizedWeatherRecord",
    "WeatherIngestRequest",
    "WeatherIngestSummary",
    "WeatherRecord",
    "WeatherStatusResponse",
    "WeatherFeatures",
    "AIRequest",
    "AIExplanationResponse",
    "AIStatusResponse",
    "AIIntentEnum",
    "ExplainForecastRequest",
    "ExplainOptimizationRequest",
    "ExplainAnomalyRequest",
]




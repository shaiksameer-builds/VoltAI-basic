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
from backend.app.schemas.optimization import (
    BatteryConfig,
    GridPricingConfig,
    OptimizationPoint,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationSummary,
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
]



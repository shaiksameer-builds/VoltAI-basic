"""
VoltAI AI Context Builder (Stage 10)

Aggregates structured context from VoltAI's deterministic services:
  - Analytics (Stage 5)
  - Forecasting (Stage 6)
  - Optimization (Stage 7)
  - Anomaly Detection (Stage 8)
  - Weather Integration (Stage 9)

Ensures all facts supplied to the LLM are bounded, traceable, and grounded.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.database.models import EnergyReading
from backend.app.services.energy_analytics import get_energy_summary
from backend.app.services.energy_forecasting import EnergyForecastingService
from backend.app.services.battery_optimization import BatteryOptimizationService
from backend.app.services.anomaly_detection import AnomalyDetectionService
from backend.app.schemas.anomalies import AnomalyDetectionRequest
from backend.app.schemas.optimization import OptimizationRequest, BatteryConfig, GridPricingConfig
from backend.app.weather.ingestion import WeatherIngestionService

logger = logging.getLogger(__name__)


class AIContextBuilder:
    """
    Context builder for grounding LLM prompts with structured VoltAI data.
    """

    @classmethod
    def build_context_for_intent(
        cls,
        db: Session,
        intent: str,
        site_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build site/time-scoped bounded context tailored to the query intent.
        """
        target_site = site_id or "site_001"
        context: Dict[str, Any] = {
            "site_id": target_site,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Base Energy Analytics Summary
        try:
            summary = get_energy_summary(db, site_id=target_site)
            context["analytics_summary"] = {
                "total_consumption_kwh": summary.total_consumption_kwh,
                "total_solar_generation_kwh": summary.total_solar_generation_kwh,
                "total_wind_generation_kwh": summary.total_wind_generation_kwh,
                "total_grid_import_kwh": summary.total_grid_import_kwh,
                "total_grid_export_kwh": summary.total_grid_export_kwh,
                "renewable_contribution_pct": summary.renewable_contribution_pct,
                "peak_demand_kw": summary.peak_hourly_consumption_kwh,
            }
        except Exception as e:
            logger.warning("AIContextBuilder analytics fetch error: %s", e)
            context["analytics_summary"] = None

        # 2. Latest Telemetry Sample
        try:
            latest_reading = (
                db.query(EnergyReading)
                .filter(EnergyReading.site_id == target_site)
                .order_by(EnergyReading.timestamp.desc())
                .first()
            )
            if latest_reading:
                context["latest_telemetry"] = {
                    "timestamp": latest_reading.timestamp.isoformat(),
                    "solar_kw": latest_reading.solar_generation,
                    "wind_kw": latest_reading.wind_generation,
                    "consumption_kw": latest_reading.energy_consumption,
                    "battery_soc_pct": latest_reading.battery_soc,
                    "grid_import_kw": latest_reading.grid_import,
                    "grid_export_kw": latest_reading.grid_export,
                }
            else:
                context["latest_telemetry"] = None
        except Exception as e:
            logger.warning("AIContextBuilder telemetry fetch error: %s", e)
            context["latest_telemetry"] = None

        # 3. Forecast Context (if relevant)
        if intent in ("FORECAST_EXPLANATION", "ENERGY_SUMMARY", "GENERAL_ENERGY_QUESTION"):
            try:
                fc_solar = EnergyForecastingService.generate_forecast(db, site_id=target_site, target="solar", horizon_hours=24, persist=False)
                context["forecast_solar_24h"] = {
                    "total_expected_solar_kwh": round(sum(p.predicted_value_kwh for p in fc_solar.predictions), 2),
                    "peak_predicted_kw": round(max(p.predicted_value_kwh for p in fc_solar.predictions), 2) if fc_solar.predictions else 0.0,
                    "sample_points": [
                        {"hour": p.target_timestamp.hour, "val": round(p.predicted_value_kwh, 2)}
                        for p in fc_solar.predictions[:6]
                    ],
                }
            except Exception as e:
                logger.warning("AIContextBuilder forecast fetch error: %s", e)
                context["forecast_solar_24h"] = None

        # 4. Optimization Context (if relevant)
        if intent in ("BATTERY_EXPLANATION", "ENERGY_SUMMARY", "GENERAL_ENERGY_QUESTION"):
            try:
                opt_req = OptimizationRequest(
                    site_id=target_site,
                    battery_config=BatteryConfig(capacity_kwh=100.0, max_charge_kw=25.0, max_discharge_kw=25.0),
                    grid_pricing=GridPricingConfig(peak_rate=12.0, off_peak_rate=4.0),
                )
                opt_resp = BatteryOptimizationService.optimize_schedule(db, opt_req)
                context["battery_optimization"] = {
                    "total_cost_inr": opt_resp.summary.total_energy_cost_inr,
                    "cost_savings_inr": opt_resp.summary.cost_savings_inr,
                    "total_charge_kwh": opt_resp.summary.total_battery_charge_kwh,
                    "total_discharge_kwh": opt_resp.summary.total_battery_discharge_kwh,
                    "grid_import_reduced_kwh": opt_resp.summary.grid_import_reduction_kwh,
                    "peak_hours_charging_prohibited": True,
                }
            except Exception as e:
                logger.warning("AIContextBuilder optimization fetch error: %s", e)
                context["battery_optimization"] = None

        # 5. Anomalies Context (if relevant)
        if intent in ("ANOMALY_EXPLANATION", "ENERGY_SUMMARY", "GENERAL_ENERGY_QUESTION"):
            try:
                anom_req = AnomalyDetectionRequest(site_id=target_site, z_threshold=3.0, persist=False)
                anom_resp = AnomalyDetectionService.detect_site_anomalies(db, anom_req)
                context["detected_anomalies"] = [
                    {
                        "type": a.anomaly_type.value,
                        "severity": a.severity.value,
                        "timestamp": a.timestamp.isoformat(),
                        "observed": a.observed_value,
                        "expected": a.expected_value,
                        "description": a.description,
                    }
                    for a in anom_resp.anomalies[:5]
                ]
            except Exception as e:
                logger.warning("AIContextBuilder anomaly fetch error: %s", e)
                context["detected_anomalies"] = []

        # 6. Weather Context (if relevant)
        if intent in ("WEATHER_EXPLANATION", "FORECAST_EXPLANATION", "ENERGY_SUMMARY", "GENERAL_ENERGY_QUESTION"):
            try:
                w_readings = WeatherIngestionService.get_weather_for_site(db, site_id=target_site, limit=5)
                if w_readings:
                    latest_w = w_readings[-1]
                    context["latest_weather"] = {
                        "temperature_c": latest_w.temperature_c,
                        "humidity_pct": latest_w.relative_humidity_pct,
                        "cloud_cover_pct": latest_w.cloud_cover_pct,
                        "wind_speed_ms": latest_w.wind_speed_ms,
                        "solar_irradiance_wm2": latest_w.shortwave_radiation_wm2,
                        "provider": latest_w.provider,
                    }
                else:
                    context["latest_weather"] = "Unavailable (using standard seasonal baseline)"
            except Exception as e:
                logger.warning("AIContextBuilder weather fetch error: %s", e)
                context["latest_weather"] = None

        return context

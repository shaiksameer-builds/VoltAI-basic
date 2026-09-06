"""
VoltAI Energy Anomaly Detection Service (Stage 8)

Hybrid anomaly detection service integrating:
1. Physical Rule Violations (SOC limits, negative energy, simultaneous charge/discharge)
2. Robust Statistical Baselines (Rolling Median & Median Absolute Deviation)
3. Time-of-Day Seasonal Baselines (Hourly historical expectations)
4. Forecast Residual Detection (Comparison with Stage 6 prediction models)
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import AnomalyDetectionRun, EnergyAnomaly, EnergyReading
from backend.app.schemas.anomalies import (
    AnomalyDetectionRequest,
    AnomalyRecord,
    AnomalyResponse,
    AnomalySeverity,
    AnomalyStatus,
    AnomalySummary,
    AnomalyType,
)
from backend.app.services.energy_forecasting import EnergyForecastingService

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    """
    Hybrid service for detecting, scoring, deduplicating, and persisting energy anomalies.
    """

    @classmethod
    def calculate_robust_z_score(cls, value: float, median: float, mad: float) -> float:
        """
        Calculates robust Z-score using Median Absolute Deviation (MAD).
        z = 0.6745 * (x - median) / MAD
        """
        if mad <= 1e-6:
            # Handle MAD = 0 safely
            return 0.0 if abs(value - median) <= 1e-6 else 5.0
        return 0.6745 * (value - median) / mad

    @classmethod
    def determine_severity_and_confidence(
        cls, deviation_pct: float, abs_z_score: float, is_physical_rule: bool
    ) -> Tuple[AnomalySeverity, float]:
        """
        Calculates deterministic severity level and detection confidence score (0.0 to 1.0).
        """
        if is_physical_rule:
            return AnomalySeverity.CRITICAL, 1.0

        abs_dev_pct = abs(deviation_pct)
        if abs_z_score >= 6.0 or abs_dev_pct >= 100.0:
            severity = AnomalySeverity.HIGH
            confidence = min(0.95, 0.70 + (abs_z_score / 20.0))
        elif abs_z_score >= 4.0 or abs_dev_pct >= 50.0:
            severity = AnomalySeverity.MEDIUM
            confidence = min(0.85, 0.60 + (abs_z_score / 20.0))
        elif abs_z_score >= 3.0 or abs_dev_pct >= 25.0:
            severity = AnomalySeverity.LOW
            confidence = min(0.75, 0.50 + (abs_z_score / 20.0))
        else:
            severity = AnomalySeverity.INFO
            confidence = 0.50

        return severity, round(confidence, 2)

    @classmethod
    def detect_physical_rule_violations(cls, reading: EnergyReading) -> List[AnomalyRecord]:
        """
        Layer A: Detects physical rule violations (SOC bounds, negative energy, simultaneous C/D).
        """
        anomalies: List[AnomalyRecord] = []
        now = datetime.now(timezone.utc)
        site_id = reading.site_id
        ts = reading.timestamp
        reading_id = reading.id

        # 1. Invalid battery SOC
        if reading.battery_soc is not None:
            soc = reading.battery_soc
            if soc < 0.0 or soc > 100.0:
                anomalies.append(
                    AnomalyRecord(
                        anomaly_id=f"ANOM-PHYS-SOC-{reading_id}-{ts.strftime('%H%M%S')}",
                        site_id=site_id,
                        timestamp=ts,
                        anomaly_type=AnomalyType.BATTERY_SOC_ANOMALY,
                        severity=AnomalySeverity.CRITICAL,
                        metric="battery_soc",
                        observed_value=soc,
                        expected_value=50.0,
                        deviation=soc - 50.0,
                        deviation_pct=((soc - 50.0) / 50.0) * 100.0,
                        confidence=1.0,
                        detection_method="PHYSICAL_RULE",
                        explanation=f"Physical SOC violation: State of Charge ({soc}%) is out of valid [0, 100]% range.",
                        status=AnomalyStatus.OPEN,
                        related_energy_reading_id=reading_id,
                        created_at=now,
                    )
                )

        # 2. Simultaneous battery charging and discharging
        c_kwh = reading.battery_charge or 0.0
        d_kwh = reading.battery_discharge or 0.0
        if c_kwh > 1e-3 and d_kwh > 1e-3:
            anomalies.append(
                AnomalyRecord(
                    anomaly_id=f"ANOM-PHYS-CD-{reading_id}-{ts.strftime('%H%M%S')}",
                    site_id=site_id,
                    timestamp=ts,
                    anomaly_type=AnomalyType.BATTERY_CHARGE_ANOMALY,
                    severity=AnomalySeverity.CRITICAL,
                    metric="battery_charge_discharge",
                    observed_value=c_kwh + d_kwh,
                    expected_value=0.0,
                    deviation=c_kwh + d_kwh,
                    deviation_pct=100.0,
                    confidence=1.0,
                    detection_method="PHYSICAL_RULE",
                    explanation=f"Physical violation: Simultaneous battery charging ({c_kwh} kWh) and discharging ({d_kwh} kWh).",
                    status=AnomalyStatus.OPEN,
                    related_energy_reading_id=reading_id,
                    created_at=now,
                )
            )

        # 3. Negative energy flows
        energy_fields = [
            ("solar_generation", reading.solar_generation, AnomalyType.SENSOR_DATA_ANOMALY),
            ("wind_generation", reading.wind_generation, AnomalyType.SENSOR_DATA_ANOMALY),
            ("energy_consumption", reading.energy_consumption, AnomalyType.SENSOR_DATA_ANOMALY),
            ("grid_import", reading.grid_import, AnomalyType.GRID_IMPORT_SPIKE),
            ("grid_export", reading.grid_export, AnomalyType.GRID_EXPORT_SPIKE),
        ]
        for field_name, val, a_type in energy_fields:
            if val is not None and val < 0.0:
                anomalies.append(
                    AnomalyRecord(
                        anomaly_id=f"ANOM-PHYS-NEG-{field_name}-{reading_id}",
                        site_id=site_id,
                        timestamp=ts,
                        anomaly_type=a_type,
                        severity=AnomalySeverity.CRITICAL,
                        metric=field_name,
                        observed_value=val,
                        expected_value=0.0,
                        deviation=val,
                        deviation_pct=-100.0,
                        confidence=1.0,
                        detection_method="PHYSICAL_RULE",
                        explanation=f"Physical violation: Negative energy measurement ({val} kWh) for field '{field_name}'.",
                        status=AnomalyStatus.OPEN,
                        related_energy_reading_id=reading_id,
                        created_at=now,
                    )
                )

        return anomalies

    @classmethod
    def detect_site_anomalies(
        cls,
        db: Session,
        request: AnomalyDetectionRequest,
    ) -> AnomalyResponse:
        """
        Executes hybrid anomaly detection pipeline across site telemetry.
        """
        now = datetime.now(timezone.utc)
        # Use a more precise timestamp with microseconds and a short UUID to ensure uniqueness across rapid consecutive calls.
        import uuid
        run_id = f"ANOMRUN-{request.site_id.upper()}-{now.strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex[:6]}"

        # Fetch telemetry
        stmt = (
            select(EnergyReading)
            .where(EnergyReading.site_id == request.site_id)
            .order_by(EnergyReading.timestamp.asc())
        )
        if request.start_time:
            stmt = stmt.where(EnergyReading.timestamp >= request.start_time)
        if request.end_time:
            stmt = stmt.where(EnergyReading.timestamp <= request.end_time)

        readings = db.scalars(stmt).all()
        records_examined = len(readings)

        if not readings:
            summary = AnomalySummary(total_anomalies=0, by_severity={}, by_type={})
            return AnomalyResponse(
                anomaly_detection_run_id=run_id,
                site_id=request.site_id,
                created_at=now,
                records_examined=0,
                summary=summary,
                anomalies=[],
            )

        detected_anomalies: List[AnomalyRecord] = []

        # Layer A: Physical Rule Validation
        for r in readings:
            detected_anomalies.extend(cls.detect_physical_rule_violations(r))

        # Build DataFrame for statistical & seasonal detection
        df = pd.DataFrame([
            {
                "id": r.id,
                "timestamp": r.timestamp,
                "solar_generation": r.solar_generation or 0.0,
                "wind_generation": r.wind_generation or 0.0,
                "energy_consumption": r.energy_consumption or 0.0,
                "battery_soc": r.battery_soc if r.battery_soc is not None else 50.0,
                "grid_import": r.grid_import or 0.0,
                "grid_export": r.grid_export or 0.0,
            }
            for r in readings
        ])

        # Cold-Start Check
        num_hours = len(df)
        if num_hours >= 24:
            # Layer B & C: Statistical & Time-of-Day Baselines
            df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour

            metrics_to_check = [
                ("energy_consumption", AnomalyType.CONSUMPTION_SPIKE, AnomalyType.CONSUMPTION_DROP),
                ("solar_generation", None, AnomalyType.SOLAR_DROP),
                ("wind_generation", None, AnomalyType.WIND_DROP),
                ("grid_import", AnomalyType.GRID_IMPORT_SPIKE, None),
                ("grid_export", AnomalyType.GRID_EXPORT_SPIKE, None),
            ]

            for metric_col, spike_type, drop_type in metrics_to_check:
                # Compute hourly time-of-day median & MAD
                hourly_group = df.groupby("hour")[metric_col]
                hourly_medians = hourly_group.transform("median")

                # Compute MAD per hour
                mad_series = df.groupby("hour")[metric_col].transform(lambda x: np.median(np.abs(x - np.median(x))))

                for i, row in df.iterrows():
                    obs_val = float(row[metric_col])
                    exp_val = float(hourly_medians.iloc[i])
                    mad_val = float(mad_series.iloc[i])

                    # Ignore trivial 0.0 -> 0.0 solar nighttime / zero demand
                    if abs(obs_val) < 1e-3 and abs(exp_val) < 1e-3:
                        continue

                    z_score = cls.calculate_robust_z_score(obs_val, exp_val, mad_val)
                    abs_z = abs(z_score)

                    if abs_z >= request.z_threshold:
                        dev = obs_val - exp_val
                        dev_pct = (dev / exp_val * 100.0) if exp_val > 1e-3 else 100.0

                        a_type = spike_type if dev > 0 and spike_type else drop_type
                        if not a_type:
                            a_type = AnomalyType.RENEWABLE_OUTPUT_ANOMALY

                        severity, conf = cls.determine_severity_and_confidence(dev_pct, abs_z, is_physical_rule=False)

                        method = "TIME_OF_DAY_MAD" if num_hours >= 168 else "STATISTICAL_MAD"
                        exp_msg = f"Statistical anomaly in '{metric_col}': Observed {obs_val:.2f} kWh vs expected {exp_val:.2f} kWh (Z-score: {z_score:.2f})."

                        anom_id = f"ANOM-STAT-{metric_col}-{row['id']}"
                        detected_anomalies.append(
                            AnomalyRecord(
                                anomaly_id=anom_id,
                                site_id=request.site_id,
                                timestamp=row["timestamp"],
                                anomaly_type=a_type,
                                severity=severity,
                                metric=metric_col,
                                observed_value=round(obs_val, 4),
                                expected_value=round(exp_val, 4),
                                deviation=round(dev, 4),
                                deviation_pct=round(dev_pct, 4),
                                confidence=conf,
                                detection_method=method,
                                explanation=exp_msg,
                                status=AnomalyStatus.OPEN,
                                related_energy_reading_id=int(row["id"]),
                                created_at=now,
                            )
                        )

        # Layer D: Forecast Residual Anomalies (if Stage 6 model trained)
        try:
            fc_solar = EnergyForecastingService.generate_forecast(
                db, request.site_id, "solar", horizon_hours=min(24, num_hours), persist=False
            )
            # Compare latest observations with forecast predictions
            latest_readings = df.iloc[-len(fc_solar.predictions):]
            for p, (_, r_row) in zip(fc_solar.predictions, latest_readings.iterrows()):
                obs_solar = float(r_row["solar_generation"])
                exp_solar = p.predicted_value_kwh
                res = obs_solar - exp_solar

                if abs(res) > 25.0 and exp_solar > 5.0:  # Significant forecast error residual
                    dev_pct = (res / exp_solar) * 100.0
                    anom_id = f"ANOM-FC-RES-SOLAR-{r_row['id']}"
                    detected_anomalies.append(
                        AnomalyRecord(
                            anomaly_id=anom_id,
                            site_id=request.site_id,
                            timestamp=p.target_timestamp,
                            anomaly_type=AnomalyType.SOLAR_DROP if res < 0 else AnomalyType.RENEWABLE_OUTPUT_ANOMALY,
                            severity=AnomalySeverity.MEDIUM,
                            metric="solar_generation",
                            observed_value=round(obs_solar, 4),
                            expected_value=round(exp_solar, 4),
                            deviation=round(res, 4),
                            deviation_pct=round(dev_pct, 4),
                            confidence=0.80,
                            detection_method="FORECAST_RESIDUAL",
                            explanation=f"Forecast residual anomaly: Observed solar generation ({obs_solar:.2f} kWh) deviated from forecast ({exp_solar:.2f} kWh).",
                            status=AnomalyStatus.OPEN,
                            related_energy_reading_id=int(r_row["id"]),
                            created_at=now,
                        )
                    )
        except Exception:
            # Forecast models not yet trained for site; skip Layer D gracefully
            pass

        # Deduplicate anomalies by unique anomaly_id
        unique_anomalies: Dict[str, AnomalyRecord] = {}
        for a in detected_anomalies:
            unique_anomalies[a.anomaly_id] = a

        final_anomalies = list(unique_anomalies.values())

        # Build Summary
        by_sev: Dict[str, int] = {}
        by_typ: Dict[str, int] = {}
        for a in final_anomalies:
            by_sev[a.severity.value] = by_sev.get(a.severity.value, 0) + 1
            by_typ[a.anomaly_type.value] = by_typ.get(a.anomaly_type.value, 0) + 1

        summary = AnomalySummary(
            total_anomalies=len(final_anomalies),
            by_severity=by_sev,
            by_type=by_typ,
        )

        response = AnomalyResponse(
            anomaly_detection_run_id=run_id,
            site_id=request.site_id,
            created_at=now,
            records_examined=records_examined,
            summary=summary,
            anomalies=final_anomalies,
        )

        if request.persist:
            cls._persist_anomaly_run(db, response, request.z_threshold)

        return response

    @classmethod
    def _persist_anomaly_run(cls, db: Session, response: AnomalyResponse, z_threshold: float) -> None:
        """Persists AnomalyDetectionRun and EnergyAnomaly records into database."""
        run_db = AnomalyDetectionRun(
            anomaly_detection_run_id=response.anomaly_detection_run_id,
            site_id=response.site_id,
            created_at=response.created_at,
            records_examined=response.records_examined,
            anomalies_detected=len(response.anomalies),
            z_threshold=z_threshold,
        )
        # Check for existing run to avoid duplicate primary key errors
        existing_run = db.scalars(select(AnomalyDetectionRun).where(AnomalyDetectionRun.anomaly_detection_run_id == response.anomaly_detection_run_id)).first()
        if not existing_run:
            db.add(run_db)
        else:
            logger.warning(f"AnomalyDetectionRun with id {response.anomaly_detection_run_id} already exists; skipping insertion.")

        for a in response.anomalies:
            # Avoid re-inserting duplicate anomaly_id into DB
            existing = db.scalars(select(EnergyAnomaly).where(EnergyAnomaly.anomaly_id == a.anomaly_id)).first()
            if not existing:
                db.add(
                    EnergyAnomaly(
                        anomaly_id=a.anomaly_id,
                        anomaly_detection_run_id=response.anomaly_detection_run_id,
                        site_id=a.site_id,
                        timestamp=a.timestamp,
                        anomaly_type=a.anomaly_type.value,
                        severity=a.severity.value,
                        metric=a.metric,
                        observed_value=a.observed_value,
                        expected_value=a.expected_value,
                        deviation=a.deviation,
                        deviation_pct=a.deviation_pct,
                        confidence=a.confidence,
                        detection_method=a.detection_method,
                        explanation=a.explanation,
                        status=a.status.value,
                        related_energy_reading_id=a.related_energy_reading_id,
                        created_at=a.created_at,
                    )
                )
        db.commit()

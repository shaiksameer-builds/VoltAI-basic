"""
VoltAI Energy Forecasting Service

Core forecasting logic for VoltAI:
- Baselines (1h persistence, 24h seasonal persistence)
- ML Models (HistGradientBoostingRegressor / MultiOutputRegressor with RidgeCV fallback)
- Empirical solar physical zero constraint
- Evaluation metrics (MAE, RMSE, wMAPE)
- Multi-step (24h) forecast generation & database persistence
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.multioutput import MultiOutputRegressor
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import EnergyReading, ForecastResult
from backend.app.schemas.forecasting import ForecastPoint, ForecastResponse, ModelTrainingResponse
from backend.app.services.feature_engineering import FeatureEngineeringService, MIN_COLD_START_HOURS

logger = logging.getLogger(__name__)

# Directory for storing trained model artifacts
MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "models"


class EnergyForecastingService:
    """
    Service layer handling training, persistence, and forecasting for renewable generation and demand.
    """

    @classmethod
    def get_model_path(cls, site_id: str, target: str) -> Path:
        """Returns the artifact path for a specific site and target."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        return MODEL_DIR / f"{site_id}_{target}_v1.joblib"

    @classmethod
    def calculate_metrics(cls, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """
        Calculates MAE, RMSE, and wMAPE metrics in kWh.
        """
        mae = float(np.mean(np.abs(y_true - y_pred)))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        total_actual = float(np.sum(np.abs(y_true)))
        wmape = float(np.sum(np.abs(y_true - y_pred)) / total_actual * 100.0) if total_actual > 0 else 0.0
        return {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "wmape": round(wmape, 4),
        }

    @classmethod
    def compute_baseline_forecast(
        cls, df: pd.DataFrame, target_col: str, horizon_hours: int = 24
    ) -> np.ndarray:
        """
        Produces baseline 24-step predictions:
        - 1-hour horizon: last observed value
        - 24-hour horizon: previous day seasonal persistence (t-24+h)
        """
        latest_val = float(df[target_col].iloc[-1])
        if len(df) >= 24:
            # Previous-day 24-step sequence
            prev_day_vals = df[target_col].iloc[-24:].values.astype(float)
            if horizon_hours <= 24:
                return prev_day_vals[:horizon_hours]
            else:
                return np.pad(prev_day_vals, (0, horizon_hours - 24), mode="edge")
        else:
            # Fallback to naive 1-hour persistence for all steps
            return np.full(horizon_hours, latest_val)

    @classmethod
    def apply_solar_physical_constraint(
        cls, df: pd.DataFrame, predictions: np.ndarray, start_timestamp: datetime
    ) -> np.ndarray:
        """
        Empirical Solar Physical Zero Constraint:
        If historical max solar generation for a given hour-of-day is zero,
        constrain the prediction to zero.
        """
        df_copy = df.copy()
        df_copy["hour"] = pd.to_datetime(df_copy["timestamp"]).dt.hour
        hourly_max = df_copy.groupby("hour")["solar_generation"].max().to_dict()

        constrained_preds = predictions.copy()
        for step in range(len(constrained_preds)):
            target_hour = (start_timestamp + timedelta(hours=step + 1)).hour
            if hourly_max.get(target_hour, 0.0) == 0.0:
                constrained_preds[step] = 0.0

        return np.maximum(0.0, constrained_preds)

    @classmethod
    def train_model(
        cls, db: Session, site_id: str, target: str, force_retrain: bool = False
    ) -> ModelTrainingResponse:
        """
        Trains a MultiOutputRegressor for a specific site_id and target.
        Uses chronological train/val/test splits and evaluates MAE/RMSE/wMAPE.
        """
        target_map = {
            "solar": "solar_generation",
            "wind": "wind_generation",
            "demand": "energy_consumption",
        }
        if target not in target_map:
            raise ValueError(f"Invalid target '{target}'. Must be one of {list(target_map.keys())}")

        target_col = target_map[target]
        model_path = cls.get_model_path(site_id, target)

        if model_path.exists() and not force_retrain:
            return ModelTrainingResponse(
                site_id=site_id,
                target=target,
                model_version="v1.0-multioutput",
                status="success",
                metrics={"info": "Loaded existing model artifact without retraining"},
                trained_at=datetime.now(timezone.utc),
                message="Model artifact already exists. Pass force_retrain=True to retrain.",
            )

        # Query site energy readings
        stmt = (
            select(EnergyReading)
            .where(EnergyReading.site_id == site_id)
            .order_by(EnergyReading.timestamp.asc())
        )
        readings = db.scalars(stmt).all()
        if len(readings) < MIN_COLD_START_HOURS:
            raise ValueError(
                f"Insufficient energy readings for site '{site_id}'. Found {len(readings)}, minimum required is {MIN_COLD_START_HOURS}."
            )

        # Build dataframe
        records = [
            {
                "timestamp": r.timestamp,
                "solar_generation": r.solar_generation or 0.0,
                "wind_generation": r.wind_generation or 0.0,
                "energy_consumption": r.energy_consumption or 0.0,
                "battery_soc": r.battery_soc if r.battery_soc is not None else 50.0,
            }
            for r in readings
        ]
        df = pd.DataFrame(records)

        # Create training datasets
        X, Y, clean_df = FeatureEngineeringService.create_training_dataset(df, target_col, horizon_steps=24)

        # Chronological split (70% train, 30% test)
        split_idx = int(len(X) * 0.7)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        Y_train, Y_test = Y.iloc[:split_idx], Y.iloc[split_idx:]

        # Primary model: MultiOutputRegressor(HistGradientBoostingRegressor)
        try:
            base_estimator = HistGradientBoostingRegressor(max_iter=100, random_state=42)
            model = MultiOutputRegressor(base_estimator)
            model.fit(X_train, Y_train)
        except Exception as e:
            logger.warning(f"HistGradientBoostingRegressor failed ({e}), falling back to RidgeCV")
            model = MultiOutputRegressor(RidgeCV())
            model.fit(X_train, Y_train)

        # Evaluate on test split
        Y_pred = model.predict(X_test)

        # Enforce non-negativity on predictions for metrics evaluation
        Y_pred = np.maximum(0.0, Y_pred)

        metrics = cls.calculate_metrics(Y_test.values, Y_pred)

        # Save model artifact
        joblib.dump(model, model_path)

        return ModelTrainingResponse(
            site_id=site_id,
            target=target,
            model_version="v1.0-multioutput",
            status="success",
            metrics=metrics,
            trained_at=datetime.now(timezone.utc),
            message=f"Model successfully trained on {len(X_train)} samples and evaluated on {len(X_test)} samples.",
        )

    @classmethod
    def generate_forecast(
        cls,
        db: Session,
        site_id: str,
        target: str,
        horizon_hours: int = 24,
        persist: bool = True,
    ) -> ForecastResponse:
        """
        Generates multi-step forecast predictions for solar, wind, demand, or derived (renewable/balance).
        Persists results to database if requested.
        """
        if horizon_hours < 1 or horizon_hours > 24:
            raise ValueError(f"Horizon hours must be between 1 and 24, got {horizon_hours}")

        now = datetime.now(timezone.utc)
        run_id = f"RUN-{site_id.upper()}-{now.strftime('%Y%m%d%H%M%S')}"

        if target == "renewable":
            # Derived: solar + wind
            solar_resp = cls.generate_forecast(db, site_id, "solar", horizon_hours, persist=False)
            wind_resp = cls.generate_forecast(db, site_id, "wind", horizon_hours, persist=False)

            preds = []
            for sp, wp in zip(solar_resp.predictions, wind_resp.predictions):
                val = sp.predicted_value_kwh + wp.predicted_value_kwh
                preds.append(
                    ForecastPoint(
                        site_id=site_id,
                        target="renewable",
                        target_timestamp=sp.target_timestamp,
                        horizon_step=sp.horizon_step,
                        predicted_value_kwh=round(val, 4),
                        model_version="v1.0-derived",
                        forecast_run_id=run_id,
                        generated_at=now,
                    )
                )

            resp = ForecastResponse(
                site_id=site_id,
                target="renewable",
                horizon_hours=horizon_hours,
                generated_at=now,
                model_version="v1.0-derived",
                forecast_run_id=run_id,
                predictions=preds,
            )
            if persist:
                cls._persist_forecast_results(db, resp)
            return resp

        # Direct targets (solar, wind, demand)
        target_map = {
            "solar": "solar_generation",
            "wind": "wind_generation",
            "demand": "energy_consumption",
        }
        if target not in target_map:
            raise ValueError(f"Unsupported target '{target}'")

        target_col = target_map[target]

        # Query site energy readings
        stmt = (
            select(EnergyReading)
            .where(EnergyReading.site_id == site_id)
            .order_by(EnergyReading.timestamp.asc())
        )
        readings = db.scalars(stmt).all()
        if not readings:
            raise ValueError(f"No energy readings found for site '{site_id}'")

        records = [
            {
                "timestamp": r.timestamp,
                "solar_generation": r.solar_generation or 0.0,
                "wind_generation": r.wind_generation or 0.0,
                "energy_consumption": r.energy_consumption or 0.0,
                "battery_soc": r.battery_soc if r.battery_soc is not None else 50.0,
            }
            for r in readings
        ]
        df = pd.DataFrame(records)
        latest_ts = df["timestamp"].iloc[-1]
        if not isinstance(latest_ts, datetime):
            latest_ts = pd.to_datetime(latest_ts).to_pydatetime()

        model_path = cls.get_model_path(site_id, target)
        if model_path.exists() and len(df) >= MIN_COLD_START_HOURS:
            # Use trained ML model
            model = joblib.load(model_path)
            latest_X = FeatureEngineeringService.create_inference_features(df, target_col)
            pred_24 = model.predict(latest_X)[0]
            model_ver = "v1.0-multioutput"
        else:
            # Baseline seasonal persistence fallback
            pred_24 = cls.compute_baseline_forecast(df, target_col, horizon_hours=24)
            model_ver = "v1.0-baseline-persistence"

        # Truncate to requested horizon
        predictions_array = pred_24[:horizon_hours]

        # Enforce non-negativity for generation/demand
        predictions_array = np.maximum(0.0, predictions_array)

        # Apply Solar Physical Zero Constraint
        if target == "solar":
            predictions_array = cls.apply_solar_physical_constraint(df, predictions_array, latest_ts)

        # Build ForecastPoints
        forecast_points = []
        for step in range(1, horizon_hours + 1):
            target_ts = latest_ts + timedelta(hours=step)
            val = float(predictions_array[step - 1])
            forecast_points.append(
                ForecastPoint(
                    site_id=site_id,
                    target=target,
                    target_timestamp=target_ts,
                    horizon_step=step,
                    predicted_value_kwh=round(val, 4),
                    model_version=model_ver,
                    forecast_run_id=run_id,
                    generated_at=now,
                )
            )

        resp = ForecastResponse(
            site_id=site_id,
            target=target,
            horizon_hours=horizon_hours,
            generated_at=now,
            model_version=model_ver,
            forecast_run_id=run_id,
            predictions=forecast_points,
        )

        if persist:
            cls._persist_forecast_results(db, resp)

        return resp

    @classmethod
    def generate_balance_forecast(
        cls,
        db: Session,
        site_id: str,
        horizon_hours: int = 24,
        persist: bool = True,
    ) -> ForecastResponse:
        """
        Generates predicted energy balance (Renewable Forecast - Demand Forecast).
        Positive = surplus, Negative = deficit.
        """
        renewable_resp = cls.generate_forecast(db, site_id, "renewable", horizon_hours, persist=False)
        demand_resp = cls.generate_forecast(db, site_id, "demand", horizon_hours, persist=False)

        now = datetime.now(timezone.utc)
        run_id = f"RUN-BALANCE-{site_id.upper()}-{now.strftime('%Y%m%d%H%M%S')}"

        preds = []
        for rp, dp in zip(renewable_resp.predictions, demand_resp.predictions):
            balance_val = rp.predicted_value_kwh - dp.predicted_value_kwh
            preds.append(
                ForecastPoint(
                    site_id=site_id,
                    target="balance",
                    target_timestamp=rp.target_timestamp,
                    horizon_step=rp.horizon_step,
                    predicted_value_kwh=round(balance_val, 4),  # Can be negative for balance!
                    model_version="v1.0-balance-derived",
                    forecast_run_id=run_id,
                    generated_at=now,
                )
            )

        resp = ForecastResponse(
            site_id=site_id,
            target="balance",
            horizon_hours=horizon_hours,
            generated_at=now,
            model_version="v1.0-balance-derived",
            forecast_run_id=run_id,
            predictions=preds,
        )

        if persist:
            cls._persist_forecast_results(db, resp)

        return resp

    @classmethod
    def _persist_forecast_results(cls, db: Session, forecast_resp: ForecastResponse) -> None:
        """Helper to save ForecastResult records into energy_forecasts table."""
        results = [
            ForecastResult(
                forecast_run_id=p.forecast_run_id,
                site_id=p.site_id,
                target=p.target,
                generated_at=p.generated_at,
                target_timestamp=p.target_timestamp,
                horizon_step=p.horizon_step,
                predicted_value_kwh=p.predicted_value_kwh,
                model_version=p.model_version,
            )
            for p in forecast_resp.predictions
        ]
        db.add_all(results)
        db.commit()

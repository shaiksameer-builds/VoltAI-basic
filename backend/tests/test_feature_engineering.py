"""
Tests for Feature Engineering Service (Stage 6 — Step 3)
"""

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from backend.app.services.feature_engineering import (
    MIN_COLD_START_HOURS,
    FeatureEngineeringService,
)


def create_synthetic_dataframe(num_hours: int = 300, site_id: str = "site_001") -> pd.DataFrame:
    """Helper to generate a clean synthetic dataframe for feature testing."""
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    records = []
    for i in range(num_hours):
        ts = start_time + timedelta(hours=i)
        solar = max(0.0, 50.0 * np.sin(np.pi * (ts.hour - 6) / 12)) if 6 <= ts.hour <= 18 else 0.0
        consumption = 20.0 + 10.0 * np.sin(2 * np.pi * ts.hour / 24)
        records.append({
            "timestamp": ts,
            "site_id": site_id,
            "solar_generation": solar,
            "wind_generation": 15.0,
            "energy_consumption": consumption,
            "battery_soc": 50.0 + (i % 30),
        })
    return pd.DataFrame(records)


def test_feature_creation_correctness():
    """Verify feature generation includes all required time, lag, and rolling features."""
    df = create_synthetic_dataframe(200)
    df_feat = FeatureEngineeringService.create_features(df, target_col="solar_generation")

    feature_names = FeatureEngineeringService.get_feature_column_names()
    for col in feature_names:
        assert col in df_feat.columns

    # Test lag values
    assert np.isnan(df_feat.loc[0, "lag_1"])
    assert df_feat.loc[1, "lag_1"] == df.loc[0, "solar_generation"]
    assert df_feat.loc[24, "lag_24"] == df.loc[0, "solar_generation"]
    assert df_feat.loc[168, "lag_168"] == df.loc[0, "solar_generation"]

    # Test cyclical encoding bounds
    assert -1.0 <= df_feat["hour_sin"].min() and df_feat["hour_sin"].max() <= 1.0
    assert -1.0 <= df_feat["hour_cos"].min() and df_feat["hour_cos"].max() <= 1.0


def test_no_target_leakage():
    """Strict test verifying future values target_t+k are never present in feature_t."""
    df = create_synthetic_dataframe(200)
    df_feat = FeatureEngineeringService.create_features(df, target_col="solar_generation")

    # Change solar generation at index 10 to a huge spike 9999.0
    df_spiked = df.copy()
    df_spiked.loc[10, "solar_generation"] = 9999.0
    df_feat_spiked = FeatureEngineeringService.create_features(df_spiked, target_col="solar_generation")

    # Features at index <= 10 must be EXACTLY identical before the spike
    for idx in range(10):
        for col in FeatureEngineeringService.get_feature_column_names():
            v1 = df_feat.loc[idx, col]
            v2 = df_feat_spiked.loc[idx, col]
            if np.isnan(v1):
                assert np.isnan(v2)
            else:
                assert v1 == v2


def test_insufficient_history_rejection():
    """Verify exception is raised if data length is below 168 hours cold-start history."""
    short_df = create_synthetic_dataframe(100)  # Only 100 hours
    with pytest.raises(ValueError, match="Insufficient historical data"):
        FeatureEngineeringService.create_training_dataset(short_df, target_col="solar_generation")


def test_site_isolation():
    """Verify feature engineering handles single-site datasets independently."""
    df1 = create_synthetic_dataframe(200, site_id="site_001")
    df2 = create_synthetic_dataframe(200, site_id="site_002")

    X1, Y1, _ = FeatureEngineeringService.create_training_dataset(df1, "solar_generation")
    X2, Y2, _ = FeatureEngineeringService.create_training_dataset(df2, "solar_generation")

    assert len(X1) == len(X2)
    assert not X1.empty

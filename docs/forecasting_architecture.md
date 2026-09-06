# Stage 6 Architecture: Renewable Generation & Energy Demand Forecasting

## 1. Overview
Stage 6 implements production-oriented renewable generation (solar, wind) and energy demand forecasting for the VoltAI platform. The forecasting pipeline consumes normalized hourly energy telemetry (`EnergyReading`) from the database, extracts time-series features without target leakage, trains horizon-aware multi-output regression models, and persists multi-step forecast predictions (`ForecastResult`).

---

## 2. Target Metrics
- **`solar_generation`**: Hourly solar energy generated in kWh.
- **`wind_generation`**: Hourly wind energy generated in kWh.
- **`energy_consumption` (Demand)**: Hourly site energy consumed in kWh.
- **`renewable` (Derived)**: Sum of predicted solar and wind generation ($y_{\text{solar}} + y_{\text{wind}}$).
- **`balance` (Derived)**: Net predicted energy balance ($y_{\text{renewable}} - y_{\text{demand}}$). Positive values represent an energy surplus, while negative values represent a deficit.

---

## 3. Horizon & Multi-Step Strategy
- **Supported Horizons**: 1-hour, 6-hour, and 24-hour steps.
- **Multi-Output Strategy**: Each model outputs a 24-dimensional vector $[y_{t+1}, y_{t+2}, \dots, y_{t+24}]$. This direct multi-output approach avoids error accumulation inherent in recursive single-step forecasting.

---

## 4. Model Architecture & Baselines
- **Primary Model**: `scikit-learn` `MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=100, random_state=42))`.
- **Fallback Model**: `MultiOutputRegressor(RidgeCV())`.
- **Seasonal Baseline Persistence**:
  - 1-hour: Naive persistence ($y_{t+1} = y_t$).
  - 24-hour: Previous-day seasonal persistence ($y_{t+h} = y_{t-24+h}$).
- **Solar Physical Zero Constraint**: Empirical check that constrains solar predictions to $0.0\text{ kWh}$ if historical maximum generation for that specific hour-of-day across all recorded history is zero.

---

## 5. Feature Engineering
The `FeatureEngineeringService` ([`feature_engineering.py`](file:///d:/1.%20MY%20PROJECTS/VoltAI/VoltAI/backend/app/services/feature_engineering.py)) engineers 21 features strictly using telemetry observed at or before time $t$:
- **Time/Calendar**: `hour_of_day`, `day_of_week`, `is_weekend`.
- **Cyclical Encoding**: `hour_sin`, `hour_cos`, `day_of_week_sin`, `day_of_week_cos`.
- **Lags**: $t-1, t-2, t-3, t-24, t-48, t-168$.
- **Rolling Windows**: 6h rolling mean/std, 24h rolling mean/min/max, EMA-6, EMA-24.
- **State**: `recent_battery_soc`.

> **Target Leakage Protection**: All lag and rolling calculations apply a minimum 1-step shift ($t-1$) before computing window statistics.

---

## 6. Validation & Evaluation Metrics
- **Temporal Splitting**: 70% chronological training, 30% test set (no random k-fold or future data leakage).
- **Evaluation Metrics**:
  - **MAE**: Mean Absolute Error (kWh).
  - **RMSE**: Root Mean Squared Error (kWh).
  - **wMAPE**: Weighted Mean Absolute Percentage Error ($\frac{\sum |y - \hat{y}|}{\sum |y|} \times 100\%$), avoiding division-by-zero on nighttime solar values.

---

## 7. Model Artifact & Database Persistence
- **Model Artifacts**: Trained model objects are serialized with `joblib` under `ml/models/<site_id>_<target>_v1.joblib`. Models are ignored by `.gitignore`.
- **Database Schema**: `ForecastResult` table (`energy_forecasts`) stores indexed execution runs (`forecast_run_id`), site ID, target, generated timestamp, target timestamp, horizon step (1-24), predicted kWh, and model version.

---

## 8. API Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/forecast/train` | Train a 24-step forecasting model for a site and target metric (`force_retrain` option). |
| `GET` | `/forecast/generation` | Get 1h/6h/24h solar, wind, or total renewable forecast predictions. |
| `GET` | `/forecast/demand` | Get 1h/6h/24h energy demand forecast predictions. |
| `GET` | `/forecast/balance` | Get 1h/6h/24h predicted energy balance (surplus/deficit). |

---

## 9. Real-Data & Future Weather Migration Path
The forecasting engine depends strictly on `EnergyReading` ORM models and is completely source-agnostic. When Smart Meter, IoT, SCADA, or Weather sensors (`WeatherReading`) are introduced, they will enter through dedicated adapters without requiring changes to the core forecasting business logic.

> **Note**: Current performance validation is based on synthetic 30-day hourly telemetry generated for testing.

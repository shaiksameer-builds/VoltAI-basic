"""
VoltAI Smart-Meter Telemetry Simulator

Generates realistic simulated energy telemetry for a given site using
time-of-day patterns. Designed for the Stage 12 live-stream WebSocket
endpoint; does NOT replace or modify any existing database or ingestion logic.

Patterns modelled:
    - Solar generation: sinusoidal curve peaking at solar noon (~13:00 IST)
    - Wind generation: moderate base with random fluctuation
    - Energy consumption: morning + evening peaks (household/industrial load)
    - Battery SoC: charges when solar surplus, discharges in evening peak
    - Grid import/export: residual after renewable + battery dispatch
"""

import math
import random
from datetime import datetime, timezone
from typing import Dict, Any


# Site-specific base parameters (lat/lon not used in sim, reserved for future)
SITE_PROFILES: Dict[str, Dict[str, float]] = {
    "site_001": {"solar_peak_kw": 80.0,  "wind_base_kw": 20.0, "demand_base_kw": 60.0,  "battery_cap_kwh": 100.0},
    "site_002": {"solar_peak_kw": 120.0, "wind_base_kw": 35.0, "demand_base_kw": 95.0,  "battery_cap_kwh": 150.0},
    "site_003": {"solar_peak_kw": 350.0, "wind_base_kw": 80.0, "demand_base_kw": 40.0,  "battery_cap_kwh": 500.0},
    "site_anom_01": {"solar_peak_kw": 50.0,  "wind_base_kw": 10.0, "demand_base_kw": 45.0, "battery_cap_kwh": 80.0},
}

DEFAULT_PROFILE = {"solar_peak_kw": 80.0, "wind_base_kw": 20.0, "demand_base_kw": 60.0, "battery_cap_kwh": 100.0}

# Stateful per-site battery SoC (in-memory, resets on server restart)
_battery_soc_state: Dict[str, float] = {}


def _solar_factor(hour: float) -> float:
    """
    Solar irradiance factor [0.0, 1.0] modelled as a bell curve
    centred on hour 13.0 (1 PM local), active 06:00–19:00.
    """
    if hour < 6.0 or hour > 19.0:
        return 0.0
    # Gaussian-like curve: sigma≈2.5 h, peak at 13.0
    factor = math.exp(-0.5 * ((hour - 13.0) / 2.5) ** 2)
    return max(0.0, factor)


def _demand_factor(hour: float) -> float:
    """
    Demand factor [0.5, 1.5] with morning peak (08–10) and
    evening peak (18–21), low overnight.
    """
    # Two-hump Gaussian approximation
    morning = 0.4 * math.exp(-0.5 * ((hour - 9.0) / 1.2) ** 2)
    evening = 0.6 * math.exp(-0.5 * ((hour - 19.5) / 1.5) ** 2)
    base = 0.55
    return base + morning + evening


def simulate_reading(site_id: str, interval_seconds: float = 1.0, noise: float = 0.05) -> Dict[str, Any]:
    """
    Generate one simulated smart-meter reading for the given site.

    Args:
        site_id: The VoltAI site identifier.
        noise: Fractional Gaussian noise magnitude (default ±5%).

    Returns:
        Dict containing instantaneous smart-meter power telemetry.
        Generation, consumption, battery, and grid flow values are reported in kW.
        Battery SoC is reported as a percentage.
    """
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero")

    profile = SITE_PROFILES.get(site_id, DEFAULT_PROFILE)

    now_utc = datetime.now(timezone.utc)
    # Use UTC+5:30 (IST) for solar calculation
    ist_hour = (now_utc.hour + 5.5) % 24

    # --- Solar ---
    solar_kw = profile["solar_peak_kw"] * _solar_factor(ist_hour)
    solar_kw *= (1.0 + random.gauss(0, noise))
    solar_kw = max(0.0, round(solar_kw, 2))

    # --- Wind ---
    wind_kw = profile["wind_base_kw"] * (0.6 + 0.5 * random.random())
    wind_kw = max(0.0, round(wind_kw, 2))

    # --- Demand ---
    demand_kw = profile["demand_base_kw"] * _demand_factor(ist_hour)
    demand_kw *= (1.0 + random.gauss(0, noise))
    demand_kw = max(5.0, round(demand_kw, 2))

    # --- Battery dispatch (simple heuristic) ---
    cap = profile["battery_cap_kwh"]
    soc = _battery_soc_state.get(site_id, 50.0)

    renewable_surplus = solar_kw + wind_kw - demand_kw
    battery_charge_kw = 0.0
    battery_discharge_kw = 0.0

    if renewable_surplus > 0 and soc < 95.0:
        # Charge battery with surplus
        charge_rate = min(renewable_surplus, cap * 0.25)  # max 25% C-rate
        battery_charge_kw = round(charge_rate * (1 - soc / 100), 2)
        interval_hours = interval_seconds / 3600.0
        soc = min(100.0, soc + battery_charge_kw * interval_hours / cap * 100)
    elif renewable_surplus < 0 and soc > 10.0:
        # Discharge battery to cover deficit
        discharge_rate = min(-renewable_surplus, cap * 0.25)
        battery_discharge_kw = round(discharge_rate * (soc / 100), 2)
        interval_hours = interval_seconds / 3600.0
        soc = max(0.0, soc - battery_discharge_kw * interval_hours / cap * 100)

    _battery_soc_state[site_id] = soc

    # --- Grid ---
    net = demand_kw - solar_kw - wind_kw - battery_discharge_kw + battery_charge_kw
    grid_import_kw = max(0.0, round(net, 2))
    grid_export_kw = max(0.0, round(-net, 2))

    return {
        "type": "telemetry",
        "timestamp": now_utc.isoformat(),
        "site_id": site_id,
        "solar_generation_kw": solar_kw,
        "wind_generation_kw": wind_kw,
        "energy_consumption_kw": demand_kw,
        "battery_soc_pct": round(soc, 1),
        "battery_charge_kw": battery_charge_kw,
        "battery_discharge_kw": battery_discharge_kw,
        "grid_import_kw": grid_import_kw,
        "grid_export_kw": grid_export_kw,
        "renewable_fraction_pct": round(
            (solar_kw + wind_kw) / demand_kw * 100 if demand_kw > 0 else 0.0, 1
        ),
    }

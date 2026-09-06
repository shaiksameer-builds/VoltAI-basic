"""
VoltAI Synthetic Hourly Telemetry Generator

Development tool generating realistic, synthetic hourly renewable energy data
for 30 days across multiple site profiles.

Patterns Simulated:
    - Solar: Follows bell curve during daylight (06:00 - 18:00), 0.0 at night.
    - Wind: Variable generation independent of daylight with diurnal shifts.
    - Consumption: Daily morning & evening peaks; weekday vs weekend differences.
    - Battery Storage: Dynamic State of Charge (0-100%), charging during surplus,
      discharging during deficit.
    - Grid Interchange: Non-negative import and export balancing residual power.

NOTICE: This data is strictly for development, testing, and benchmarking.
It contains NO real customer, private, or operational smart-meter data.
"""

import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

CANONICAL_COLUMNS = [
    "timestamp",
    "site_id",
    "solar_generation_kwh",
    "wind_generation_kwh",
    "energy_consumption_kwh",
    "battery_soc",
    "battery_charge_kwh",
    "battery_discharge_kwh",
    "grid_import_kwh",
    "grid_export_kwh",
]

# Distinct facility profiles
SITE_PROFILES = {
    "site_001": {
        "name": "Commercial Microgrid Alpha",
        "solar_capacity_kw": 60.0,
        "wind_capacity_kw": 25.0,
        "base_consumption_kw": 25.0,
        "peak_consumption_kw": 55.0,
        "battery_capacity_kwh": 100.0,
        "battery_max_rate_kw": 20.0,
    },
    "site_002": {
        "name": "Industrial Facility Beta",
        "solar_capacity_kw": 120.0,
        "wind_capacity_kw": 50.0,
        "base_consumption_kw": 60.0,
        "peak_consumption_kw": 110.0,
        "battery_capacity_kwh": 200.0,
        "battery_max_rate_kw": 40.0,
    },
    "site_003": {
        "name": "Community Solar & Storage Gamma",
        "solar_capacity_kw": 40.0,
        "wind_capacity_kw": 15.0,
        "base_consumption_kw": 12.0,
        "peak_consumption_kw": 35.0,
        "battery_capacity_kwh": 60.0,
        "battery_max_rate_kw": 15.0,
    },
}


def generate_synthetic_dataset(
    start_date: datetime | None = None,
    days: int = 30,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Generate chronological hourly records for all configured sites over the given timeframe.
    """
    rng = random.Random(seed)
    if start_date is None:
        start_date = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    total_hours = days * 24
    records: List[Dict[str, Any]] = []

    for site_id, cfg in SITE_PROFILES.items():
        # Initialize battery state for site
        battery_soc = 50.0  # Start at 50%
        battery_cap = cfg["battery_capacity_kwh"]
        max_rate = cfg["battery_max_rate_kw"]

        for hour_idx in range(total_hours):
            current_time = start_date + timedelta(hours=hour_idx)
            hour = current_time.hour
            is_weekend = current_time.weekday() >= 5

            # 1. Solar Generation (kWh)
            if 6 <= hour <= 18:
                # Sine bell curve peaking around 12:00
                solar_factor = math.sin(math.pi * (hour - 6) / 12.0)
                # Add weather variability (cloud factor 0.75 - 1.0)
                weather_factor = rng.uniform(0.75, 1.0)
                solar_gen = round(cfg["solar_capacity_kw"] * solar_factor * weather_factor, 2)
            else:
                solar_gen = 0.0

            # 2. Wind Generation (kWh)
            # Oscillates with time-of-day + random gusts
            wind_base = 0.4 + 0.3 * math.cos(math.pi * hour / 12.0)
            wind_noise = rng.uniform(-0.15, 0.25)
            wind_factor = max(0.0, min(1.0, wind_base + wind_noise))
            wind_gen = round(cfg["wind_capacity_kw"] * wind_factor, 2)

            # 3. Energy Consumption (kWh)
            # Base load + morning peak (07-09) + evening peak (17-21)
            consumption_base = cfg["base_consumption_kw"]
            peak_boost = 0.0

            if 7 <= hour <= 9:
                peak_boost = (cfg["peak_consumption_kw"] - consumption_base) * 0.7
            elif 17 <= hour <= 21:
                peak_boost = (cfg["peak_consumption_kw"] - consumption_base) * 0.95
            elif 10 <= hour <= 16:
                peak_boost = (cfg["peak_consumption_kw"] - consumption_base) * 0.4

            if is_weekend:
                # Weekend reduction
                peak_boost *= 0.65
                consumption_base *= 0.85

            noise = rng.uniform(-2.0, 3.0)
            consumption = max(5.0, round(consumption_base + peak_boost + noise, 2))

            # 4. Storage & Grid Balancing
            net_renewable = solar_gen + wind_gen
            net_balance = round(net_renewable - consumption, 2)

            battery_charge = 0.0
            battery_discharge = 0.0
            grid_import = 0.0
            grid_export = 0.0

            if net_balance > 0:
                # Surplus generation: charge battery first
                available_capacity = (100.0 - battery_soc) / 100.0 * battery_cap
                charge_energy = min(net_balance, max_rate, available_capacity)
                battery_charge = round(charge_energy, 2)
                battery_soc += (battery_charge / battery_cap) * 100.0

                # Remaining surplus is exported
                grid_export = round(net_balance - battery_charge, 2)
            else:
                # Deficit: discharge battery first
                deficit = abs(net_balance)
                available_discharge = max(0.0, (battery_soc - 10.0) / 100.0 * battery_cap)
                discharge_energy = min(deficit, max_rate, available_discharge)
                battery_discharge = round(discharge_energy, 2)
                battery_soc -= (battery_discharge / battery_cap) * 100.0

                # Remaining deficit is imported
                grid_import = round(deficit - battery_discharge, 2)

            # Clamp battery_soc to strict bounds [0.0, 100.0]
            battery_soc = max(0.0, min(100.0, round(battery_soc, 1)))

            records.append({
                "timestamp": current_time.isoformat(),
                "site_id": site_id,
                "solar_generation_kwh": solar_gen,
                "wind_generation_kwh": wind_gen,
                "energy_consumption_kwh": consumption,
                "battery_soc": battery_soc,
                "battery_charge_kwh": battery_charge,
                "battery_discharge_kwh": battery_discharge,
                "grid_import_kwh": grid_import,
                "grid_export_kwh": grid_export,
            })

    return records


def write_synthetic_csv(
    output_path: Path | str,
    days: int = 30,
) -> Path:
    """
    Generate and save the synthetic energy dataset to disk in canonical CSV format.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    records = generate_synthetic_dataset(days=days)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(records)

    return path


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent.parent
    target_csv = repo_root / "data" / "sample" / "synthetic_energy_30d.csv"
    saved = write_synthetic_csv(target_csv)
    print(f"Generated 30-day synthetic dataset at: {saved}")

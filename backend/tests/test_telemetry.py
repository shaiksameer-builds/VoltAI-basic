from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.telemetry_simulator import (
    _battery_soc_state,
    simulate_reading,
)


def test_simulator_returns_valid_telemetry():
    _battery_soc_state.clear()

    reading = simulate_reading(
        "site_001",
        interval_seconds=1.0,
        noise=0.0,
    )

    assert reading["type"] == "telemetry"
    assert reading["site_id"] == "site_001"
    assert 0.0 <= reading["battery_soc_pct"] <= 100.0

    for field in (
        "solar_generation_kw",
        "wind_generation_kw",
        "energy_consumption_kw",
        "battery_charge_kw",
        "battery_discharge_kw",
        "grid_import_kw",
        "grid_export_kw",
    ):
        assert reading[field] >= 0.0


def test_simulator_power_balance():
    _battery_soc_state.clear()

    reading = simulate_reading(
        "site_001",
        interval_seconds=1.0,
        noise=0.0,
    )

    supply = (
        reading["solar_generation_kw"]
        + reading["wind_generation_kw"]
        + reading["battery_discharge_kw"]
        + reading["grid_import_kw"]
    )

    demand = (
        reading["energy_consumption_kw"]
        + reading["battery_charge_kw"]
        + reading["grid_export_kw"]
    )

    assert abs(supply - demand) < 0.01


def test_simulator_rejects_invalid_interval():
    _battery_soc_state.clear()

    try:
        simulate_reading("site_001", interval_seconds=0)
    except ValueError as exc:
        assert "interval_seconds" in str(exc)
    else:
        raise AssertionError("Expected ValueError for zero interval")


def test_websocket_stream_returns_telemetry():
    _battery_soc_state.clear()

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/v1/telemetry/stream/site_001?interval_ms=500"
        ) as websocket:
            message = websocket.receive_json()

            assert message["type"] == "telemetry"
            assert message["site_id"] == "site_001"
            assert "timestamp" in message
            assert "solar_generation_kw" in message
            assert "energy_consumption_kw" in message
            assert "battery_soc_pct" in message
            assert "grid_import_kw" in message
            assert "grid_export_kw" in message

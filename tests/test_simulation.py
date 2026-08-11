"""Tests for deterministic synthetic sensor behavior."""

import json
from datetime import timedelta

import pytest

from sensor_stream_simulator import SCENARIOS, generate_session, write_csv, write_json

WATER_SPECIFIC_HEAT_J_KG_K = 4180.0
HEAT_BALANCE_ROUNDING_TOLERANCE_W = 6.0


def _mean(values: list[float | None]) -> float:
    present = [value for value in values if value is not None]
    return sum(present) / len(present)


def test_normal_session_has_required_fields() -> None:
    reading = generate_session("normal", sample_count=1)[0]
    assert set(reading.to_mapping()) == {
        "timestamp",
        "inlet_temperature_c",
        "outlet_temperature_c",
        "flow_rate_kg_s",
        "synthetic_heat_load_w",
        "inlet_pressure_kpa",
        "outlet_pressure_kpa",
        "relative_humidity_percent",
        "pump_speed_percent",
        "leak_detected",
        "scenario",
        "is_anomaly",
        "anomaly_type",
    }


def test_heat_load_field_is_explicitly_named_as_synthetic() -> None:
    mapping = generate_session("normal", sample_count=1)[0].to_mapping()
    assert "synthetic_heat_load_w" in mapping
    assert "heat_load_w" not in mapping
    assert mapping["synthetic_heat_load_w"] > 0


def test_scenario_catalog_preserves_all_eight_modes() -> None:
    assert {
        "normal",
        "gradual-temperature-increase",
        "restricted-flow",
        "pressure-drop-increase",
        "sensor-drift",
        "random-missing",
        "pump-failure",
        "leak-event",
    } == SCENARIOS


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_every_scenario_generates_requested_sample_count(scenario: str) -> None:
    readings = generate_session(scenario, sample_count=25, seed=9)
    assert len(readings) == 25
    assert {reading.scenario for reading in readings} == {scenario}


def test_same_seed_is_fully_reproducible() -> None:
    first = generate_session("restricted-flow", sample_count=40, seed=123)
    second = generate_session("restricted-flow", sample_count=40, seed=123)
    assert first == second


def test_different_seed_changes_measurements() -> None:
    first = generate_session("normal", sample_count=5, seed=1)
    second = generate_session("normal", sample_count=5, seed=2)
    assert first != second


def test_timestamps_follow_requested_interval() -> None:
    readings = generate_session("normal", sample_count=3, interval_seconds=2.5)
    assert readings[1].timestamp - readings[0].timestamp == timedelta(seconds=2.5)


@pytest.mark.parametrize(
    "scenario",
    [
        "normal",
        "gradual-temperature-increase",
        "restricted-flow",
        "pressure-drop-increase",
        "random-missing",
        "pump-failure",
        "leak-event",
    ],
)
def test_synthetic_heat_load_matches_reported_heat_balance(scenario: str) -> None:
    readings = generate_session(scenario, sample_count=100, seed=18)
    checked = 0
    for reading in readings:
        if (
            reading.inlet_temperature_c is None
            or reading.outlet_temperature_c is None
            or reading.flow_rate_kg_s is None
        ):
            continue
        calculated_heat_load = (
            reading.flow_rate_kg_s
            * WATER_SPECIFIC_HEAT_J_KG_K
            * (reading.outlet_temperature_c - reading.inlet_temperature_c)
        )
        assert calculated_heat_load == pytest.approx(
            reading.synthetic_heat_load_w,
            abs=HEAT_BALANCE_ROUNDING_TOLERANCE_W,
        )
        checked += 1
    assert checked > 0


def test_restricted_flow_links_flow_pressure_and_temperature() -> None:
    normal = generate_session("normal", sample_count=200, seed=4)[120:]
    restricted = generate_session("restricted-flow", sample_count=200, seed=4)[120:]
    normal_flow = _mean([reading.flow_rate_kg_s for reading in normal])
    restricted_flow = _mean([reading.flow_rate_kg_s for reading in restricted])
    normal_drop = _mean(
        [
            reading.inlet_pressure_kpa - reading.outlet_pressure_kpa
            for reading in normal
            if reading.inlet_pressure_kpa is not None
            and reading.outlet_pressure_kpa is not None
        ]
    )
    restricted_drop = _mean(
        [
            reading.inlet_pressure_kpa - reading.outlet_pressure_kpa
            for reading in restricted
            if reading.inlet_pressure_kpa is not None
            and reading.outlet_pressure_kpa is not None
        ]
    )
    normal_delta = _mean(
        [
            reading.outlet_temperature_c - reading.inlet_temperature_c
            for reading in normal
            if reading.inlet_temperature_c is not None
            and reading.outlet_temperature_c is not None
        ]
    )
    restricted_delta = _mean(
        [
            reading.outlet_temperature_c - reading.inlet_temperature_c
            for reading in restricted
            if reading.inlet_temperature_c is not None
            and reading.outlet_temperature_c is not None
        ]
    )
    assert restricted_flow < normal_flow
    assert restricted_drop > normal_drop
    assert restricted_delta > normal_delta
    assert _mean([reading.pump_speed_percent for reading in restricted]) > _mean(
        [reading.pump_speed_percent for reading in normal]
    )


def test_pressure_drop_increase_raises_resistance_response() -> None:
    normal = generate_session("normal", sample_count=200, seed=15)[150:]
    increased = generate_session("pressure-drop-increase", sample_count=200, seed=15)[
        150:
    ]
    normal_drop = _mean(
        [
            reading.inlet_pressure_kpa - reading.outlet_pressure_kpa
            for reading in normal
            if reading.inlet_pressure_kpa is not None
            and reading.outlet_pressure_kpa is not None
        ]
    )
    increased_drop = _mean(
        [
            reading.inlet_pressure_kpa - reading.outlet_pressure_kpa
            for reading in increased
            if reading.inlet_pressure_kpa is not None
            and reading.outlet_pressure_kpa is not None
        ]
    )
    assert _mean([reading.flow_rate_kg_s for reading in increased]) < _mean(
        [reading.flow_rate_kg_s for reading in normal]
    )
    assert _mean([reading.pump_speed_percent for reading in increased]) > _mean(
        [reading.pump_speed_percent for reading in normal]
    )
    assert increased_drop > normal_drop


def test_gradual_temperature_scenario_increases_synthetic_heat_load() -> None:
    readings = generate_session(
        "gradual-temperature-increase", sample_count=200, seed=21
    )
    early = readings[:40]
    late = readings[-40:]
    assert _mean([reading.synthetic_heat_load_w for reading in late]) > _mean(
        [reading.synthetic_heat_load_w for reading in early]
    )
    assert _mean(
        [
            reading.outlet_temperature_c - reading.inlet_temperature_c
            for reading in late
            if reading.inlet_temperature_c is not None
            and reading.outlet_temperature_c is not None
        ]
    ) > _mean(
        [
            reading.outlet_temperature_c - reading.inlet_temperature_c
            for reading in early
            if reading.inlet_temperature_c is not None
            and reading.outlet_temperature_c is not None
        ]
    )


def test_pump_failure_reduces_pump_speed_and_flow() -> None:
    readings = generate_session("pump-failure", sample_count=200, seed=8)
    before = readings[:80]
    after = readings[150:]
    assert _mean([reading.pump_speed_percent for reading in after]) < _mean(
        [reading.pump_speed_percent for reading in before]
    )
    assert _mean([reading.flow_rate_kg_s for reading in after]) < _mean(
        [reading.flow_rate_kg_s for reading in before]
    )
    assert _mean([reading.synthetic_heat_load_w for reading in after]) < _mean(
        [reading.synthetic_heat_load_w for reading in before]
    )
    assert all(reading.anomaly_type == "pump_failure" for reading in after)


def test_leak_signal_only_appears_in_leak_scenario() -> None:
    leak = generate_session("leak-event", sample_count=100)
    normal = generate_session("normal", sample_count=100)
    assert any(reading.leak_detected for reading in leak)
    assert not any(reading.leak_detected for reading in normal)


def test_random_missing_labels_missing_measurements() -> None:
    readings = generate_session("random-missing", sample_count=300, seed=42)
    missing = [reading for reading in readings if reading.is_anomaly]
    assert missing
    assert all(reading.anomaly_type == "missing_measurement" for reading in missing)
    assert all(
        any(getattr(reading, field) is None for field in reading.to_mapping())
        for reading in missing
    )
    assert all(reading.synthetic_heat_load_w > 0 for reading in readings)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"scenario": "not-a-mode"}, "unknown scenario"),
        ({"scenario": "normal", "sample_count": 0}, "positive integer"),
        ({"scenario": "normal", "interval_seconds": -1}, "greater than zero"),
    ],
)
def test_invalid_generation_inputs(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        generate_session(**kwargs)  # type: ignore[arg-type]


def test_csv_output_contains_synthetic_labels(tmp_path: object) -> None:
    path = write_csv(generate_session("normal", sample_count=2), tmp_path / "out.csv")
    text = path.read_text(encoding="utf-8")
    header = text.splitlines()[0].split(",")
    assert "synthetic_heat_load_w" in header
    assert "heat_load_w" not in header
    assert header[-3:] == ["scenario", "is_anomaly", "anomaly_type"]
    assert "normal" in text


def test_json_output_is_valid(tmp_path: object) -> None:
    path = write_json(
        generate_session("leak-event", sample_count=3), tmp_path / "out.json"
    )
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert len(rows) == 3
    assert rows[0]["scenario"] == "leak-event"
    assert "synthetic_heat_load_w" in rows[0]
    assert "heat_load_w" not in rows[0]

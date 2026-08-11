"""Understandable, relationship-based synthetic sensor generation."""

import csv
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCENARIOS = frozenset(
    {
        "normal",
        "gradual-temperature-increase",
        "restricted-flow",
        "pressure-drop-increase",
        "sensor-drift",
        "random-missing",
        "pump-failure",
        "leak-event",
    }
)

DEFAULT_START = datetime(2026, 1, 1, tzinfo=UTC)
WATER_SPECIFIC_HEAT_J_KG_K = 4180.0
REFERENCE_PUMP_SPEED_PERCENT = 60.0
REFERENCE_FLOW_RATE_KG_S = 0.39
REFERENCE_PRESSURE_DROP_KPA = 35.0
MINIMUM_FLOW_RATE_KG_S = 0.015
MEASUREMENT_FIELDS = (
    "inlet_temperature_c",
    "outlet_temperature_c",
    "flow_rate_kg_s",
    "inlet_pressure_kpa",
    "outlet_pressure_kpa",
    "relative_humidity_percent",
    "pump_speed_percent",
)


@dataclass(frozen=True)
class SensorReading:
    """One synthetic cooling-loop sample plus its ground-truth labels."""

    timestamp: datetime
    inlet_temperature_c: float | None
    outlet_temperature_c: float | None
    flow_rate_kg_s: float | None
    synthetic_heat_load_w: float
    inlet_pressure_kpa: float | None
    outlet_pressure_kpa: float | None
    relative_humidity_percent: float | None
    pump_speed_percent: float | None
    leak_detected: bool
    scenario: str
    is_anomaly: bool
    anomaly_type: str

    def to_mapping(self) -> dict[str, Any]:
        """Return a serialization-ready mapping with an ISO 8601 timestamp."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat().replace("+00:00", "Z")
        return result


def _progress(index: int, sample_count: int) -> float:
    return 0.0 if sample_count == 1 else index / (sample_count - 1)


def _rounded(value: float) -> float:
    return round(value, 4)


def generate_session(
    scenario: str,
    sample_count: int = 300,
    interval_seconds: float = 5.0,
    seed: int = 42,
    start_time: datetime = DEFAULT_START,
) -> list[SensorReading]:
    """Generate a reproducible synthetic sensor session.

    Relationships are intentionally simplified but coupled. Scenario state is
    set first, then flow is made proportional to pump speed and inversely
    proportional to the square root of relative resistance. Pressure loss
    follows resistance times flow squared, and fluid temperature rise follows
    synthetic heat load divided by mass flow and specific heat.
    """
    if scenario not in SCENARIOS:
        choices = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"unknown scenario '{scenario}'; choose one of: {choices}")
    if isinstance(sample_count, bool) or sample_count <= 0:
        raise ValueError("sample_count must be a positive integer")
    if not math.isfinite(interval_seconds) or interval_seconds <= 0:
        raise ValueError("interval_seconds must be a finite value greater than zero")
    if start_time.tzinfo is None:
        raise ValueError("start_time must include timezone information")

    generator = random.Random(seed)
    readings: list[SensorReading] = []

    for index in range(sample_count):
        progress = _progress(index, sample_count)
        inlet_temperature = (
            20.0 + 0.25 * math.sin(index / 15) + generator.gauss(0.0, 0.08)
        )
        pump_speed = 60.0 + generator.gauss(0.0, 1.0)
        flow_noise_fraction = generator.gauss(0.0, 0.015)
        heat_load_w = 10000.0 + generator.gauss(0.0, 180.0)
        relative_resistance = 1.0
        downstream_delivery_fraction = 1.0
        inlet_pressure = 300.0 + generator.gauss(0.0, 0.6)
        humidity = 45.0 + 1.5 * math.sin(index / 20) + generator.gauss(0.0, 0.25)
        outlet_sensor_drift_c = 0.0
        leak_detected = False
        is_anomaly = False
        anomaly_type = "none"

        if scenario == "gradual-temperature-increase":
            heat_load_w += 14000.0 * progress
            if progress >= 0.6:
                is_anomaly = True
                anomaly_type = "high_temperature"
        elif scenario == "restricted-flow" and progress >= 0.25:
            severity = (progress - 0.25) / 0.75
            pump_speed += 12.0 * severity
            relative_resistance += 4.0 * severity
            if progress >= 0.4:
                is_anomaly = True
                anomaly_type = "restricted_flow"
        elif scenario == "pressure-drop-increase":
            relative_resistance += 2.0 * progress
            pump_speed += 10.0 * progress
            if progress >= 0.5:
                is_anomaly = True
                anomaly_type = "pressure_drop_increase"
        elif scenario == "sensor-drift" and progress >= 0.25:
            outlet_sensor_drift_c = 4.0 * (progress - 0.25) / 0.75
            if progress >= 0.45:
                is_anomaly = True
                anomaly_type = "sensor_drift"
        elif scenario == "pump-failure" and progress >= 0.5:
            severity = min(1.0, (progress - 0.5) / 0.15)
            pump_speed *= 1.0 - 0.92 * severity
            heat_load_w *= 1.0 - 0.75 * severity
            if severity >= 0.2:
                is_anomaly = True
                anomaly_type = "pump_failure"
        elif scenario == "leak-event" and progress >= 0.6:
            severity = min(1.0, (progress - 0.6) / 0.15)
            leak_detected = True
            downstream_delivery_fraction = 1.0 - 0.28 * severity
            inlet_pressure -= 45.0 * severity
            if severity >= 0.2:
                is_anomaly = True
                anomaly_type = "leak_event"

        pump_speed = max(0.0, min(100.0, pump_speed))
        ideal_flow_rate = (
            REFERENCE_FLOW_RATE_KG_S
            * (pump_speed / REFERENCE_PUMP_SPEED_PERCENT)
            * downstream_delivery_fraction
            / math.sqrt(relative_resistance)
        )
        flow_rate = max(
            MINIMUM_FLOW_RATE_KG_S,
            ideal_flow_rate * (1.0 + flow_noise_fraction),
        )

        temperature_rise = heat_load_w / (flow_rate * WATER_SPECIFIC_HEAT_J_KG_K)
        outlet_temperature = (
            inlet_temperature + temperature_rise + outlet_sensor_drift_c
        )

        pressure_drop = (
            REFERENCE_PRESSURE_DROP_KPA
            * relative_resistance
            * (flow_rate / REFERENCE_FLOW_RATE_KG_S) ** 2
        )
        outlet_pressure = inlet_pressure - pressure_drop

        values: dict[str, float | None] = {
            "inlet_temperature_c": _rounded(inlet_temperature),
            "outlet_temperature_c": _rounded(outlet_temperature),
            "flow_rate_kg_s": _rounded(flow_rate),
            "synthetic_heat_load_w": _rounded(heat_load_w),
            "inlet_pressure_kpa": _rounded(inlet_pressure),
            "outlet_pressure_kpa": _rounded(outlet_pressure),
            "relative_humidity_percent": _rounded(humidity),
            "pump_speed_percent": _rounded(pump_speed),
        }

        if scenario == "random-missing" and generator.random() < 0.12:
            missing_field = generator.choice(MEASUREMENT_FIELDS)
            values[missing_field] = None
            is_anomaly = True
            anomaly_type = "missing_measurement"

        readings.append(
            SensorReading(
                timestamp=start_time + timedelta(seconds=index * interval_seconds),
                leak_detected=leak_detected,
                scenario=scenario,
                is_anomaly=is_anomaly,
                anomaly_type=anomaly_type,
                **values,
            )
        )
    return readings


def write_csv(readings: list[SensorReading], output_path: str | Path) -> Path:
    """Write readings as UTF-8 CSV and return the resolved output path."""
    if not readings:
        raise ValueError("at least one reading is required")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [reading.to_mapping() for reading in readings]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return path.resolve()


def write_json(readings: list[SensorReading], output_path: str | Path) -> Path:
    """Write readings as indented UTF-8 JSON and return the resolved output path."""
    if not readings:
        raise ValueError("at least one reading is required")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [reading.to_mapping() for reading in readings]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
        handle.write("\n")
    return path.resolve()

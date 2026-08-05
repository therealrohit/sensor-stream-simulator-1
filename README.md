# Sensor Stream Simulator

A reproducible generator for **synthetic** cooling-loop sensor measurements.
The data is intended for software testing and engineering education; it is not
collected from physical equipment.

## Why I built it

I built this project while preparing to study mechanical engineering at Case
Western Reserve University. I wanted to understand how physical relationships,
random variation, anomalies, file formats, and automated tests fit together in
an engineering software project.

## Features

- Eight modes: normal operation, gradual temperature increase, restricted flow,
  pressure-drop increase, sensor drift, random missing measurements, pump
  failure, and leak event
- Configurable sample count, interval, random seed, and ISO 8601 start time
- CSV and JSON output
- Scenario and ground-truth anomaly labels in every row
- Coupled flow, pump, pressure-loss, heat-load, and temperature relationships
- Fixed default start time and seeded randomness for full reproducibility
- Committed example datasets and a matplotlib plotting script

## Technical approach

The simulator uses Python's standard `random.Random` class with a local seeded
generator. Pump speed influences flow, pipe resistance and flow influence
pressure loss, and the outlet temperature rise is calculated from a simplified
heat balance using water's approximate specific heat. Each scenario changes a
small number of those variables so its behavior remains understandable.

These relationships are simplified and are not a complete physical model.

## Installation

Python 3.11 or newer is required.

```bash
python -m venv .venv
```

Activate on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Or activate on macOS/Linux:

```bash
source .venv/bin/activate
```

Install the project and development tools:

```bash
python -m pip install -e ".[dev]"
```

## Usage

```bash
python -m sensor_stream_simulator generate \
  --scenario restricted-flow \
  --samples 500 \
  --interval-seconds 5 \
  --seed 42 \
  --output data/restricted_flow.csv
```

Use a `.json` output filename for JSON. Run
`python -m sensor_stream_simulator generate --help` for every option and
scenario.

## Example output

```text
Generated 500 synthetic samples for 'restricted-flow' at .../restricted_flow.csv
```

Every output row contains:

```text
timestamp, inlet_temperature_c, outlet_temperature_c, flow_rate_kg_s,
inlet_pressure_kpa, outlet_pressure_kpa, relative_humidity_percent,
pump_speed_percent, leak_detected, scenario, is_anomaly, anomaly_type
```

Committed datasets:

- `data/normal.csv`
- `data/restricted_flow.csv`
- `data/pump_failure.csv`
- `data/leak_event.json`

Plot the restricted-flow dataset:

```bash
python examples/plot_session.py
```

![Synthetic restricted-flow session](screenshots/restricted_flow_session.png)

## Testing

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

The tests cover all scenarios, physical relationships, timestamps, file output,
invalid inputs, CLI behavior, and exact reproducibility for equal seeds.

## Assumptions

- Water has a constant approximate specific heat of 4180 J/(kg·K).
- A steady synthetic heat load is applied within each sample.
- Flow is related to pump speed with small measurement noise.
- Pressure loss follows a simplified resistance-times-flow-squared relationship.
- Scenario transitions are intentionally smooth enough to inspect in a chart.

## Limitations

- All values are synthetic and have not been measured on physical equipment.
- The model omits control-loop dynamics, fluid-property variation, pipe geometry,
  sensor calibration curves, and detailed pump performance.
- Ground-truth labels are known because the generator creates the anomalies; they
  do not represent the output of a detection algorithm.
- The ranges are plausible examples, not specifications for a real system.

## What I learned

This project helped me practice reproducible simulation, linking variables with
simple physical relationships, modeling different failure modes, designing file
formats, and testing both numerical behavior and command-line workflows.

## Possible future work

- Read scenario parameters from a small configuration file
- Add correlated noise and configurable sensor accuracy
- Model recovery periods after transient events
- Add streaming output that yields samples in real time

## How the repositories connect

This simulator produces synthetic files that can be opened by
[`cooling-loop-dashboard`](https://github.com/ryanmalone-0/cooling-loop-dashboard).
The dashboard uses calculations from
[`thermal-calculator`](https://github.com/ryanmalone-0/thermal-calculator). The
simulator remains independent and does not require either project.

## License

MIT

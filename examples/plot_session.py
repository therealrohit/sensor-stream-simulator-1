"""Plot the committed restricted-flow synthetic session."""

import csv
from pathlib import Path

import matplotlib.pyplot as plt

plt.switch_backend("Agg")

repository_root = Path(__file__).parents[1]
input_path = repository_root / "data" / "restricted_flow.csv"
output_path = repository_root / "screenshots" / "restricted_flow_session.png"

with input_path.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))

sample_numbers = list(range(len(rows)))
flow_rates = [float(row["flow_rate_kg_s"]) for row in rows]
pressure_drops = [
    float(row["inlet_pressure_kpa"]) - float(row["outlet_pressure_kpa"]) for row in rows
]
temperature_differences = [
    float(row["outlet_temperature_c"]) - float(row["inlet_temperature_c"])
    for row in rows
]
synthetic_heat_loads_kw = [float(row["synthetic_heat_load_w"]) / 1000 for row in rows]

figure, axes = plt.subplots(4, 1, figsize=(9, 9), sharex=True)
axes[0].plot(sample_numbers, flow_rates, color="tab:blue")
axes[0].set_ylabel("Flow (kg/s)")
axes[1].plot(sample_numbers, pressure_drops, color="tab:orange")
axes[1].set_ylabel("Pressure drop (kPa)")
axes[2].plot(sample_numbers, synthetic_heat_loads_kw, color="tab:green")
axes[2].set_ylabel("Synthetic load (kW)")
axes[3].plot(sample_numbers, temperature_differences, color="tab:red")
axes[3].set_ylabel("Temperature rise (°C)")
axes[3].set_xlabel("Sample")
figure.suptitle("Synthetic restricted-flow session")
figure.tight_layout()
figure.savefig(output_path, dpi=160)
print(f"Saved synthetic-session chart to {output_path}")

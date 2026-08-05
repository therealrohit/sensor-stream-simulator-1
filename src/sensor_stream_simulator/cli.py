"""Command-line interface for synthetic sensor generation."""

import argparse
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from sensor_stream_simulator.simulation import (
    DEFAULT_START,
    SCENARIOS,
    generate_session,
    write_csv,
    write_json,
)


def _parse_start_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("start time must be ISO 8601") from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("start time must include a timezone")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sensor-stream-simulator",
        description="Generate reproducible synthetic cooling-loop sensor data.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="generate a synthetic session")
    generate.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    generate.add_argument("--samples", type=int, default=300)
    generate.add_argument("--interval-seconds", type=float, default=5.0)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--start-time", type=_parse_start_time, default=DEFAULT_START)
    generate.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        readings = generate_session(
            scenario=args.scenario,
            sample_count=args.samples,
            interval_seconds=args.interval_seconds,
            seed=args.seed,
            start_time=args.start_time,
        )
        suffix = args.output.suffix.lower()
        if suffix == ".csv":
            path = write_csv(readings, args.output)
        elif suffix == ".json":
            path = write_json(readings, args.output)
        else:
            raise ValueError("output file must use a .csv or .json extension")
    except ValueError as error:
        parser.error(str(error))
    print(
        f"Generated {len(readings)} synthetic samples for '{args.scenario}' at {path}"
    )
    return 0

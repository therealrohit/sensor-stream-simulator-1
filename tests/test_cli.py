"""Command-line interface tests."""

from pathlib import Path

import pytest

from sensor_stream_simulator.cli import main


def test_cli_writes_requested_csv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "session.csv"
    exit_code = main(
        [
            "generate",
            "--scenario",
            "restricted-flow",
            "--samples",
            "12",
            "--interval-seconds",
            "5",
            "--seed",
            "42",
            "--output",
            str(output),
        ]
    )
    assert exit_code == 0
    assert output.exists()
    assert len(output.read_text(encoding="utf-8").splitlines()) == 13
    assert "12 synthetic samples" in capsys.readouterr().out


def test_cli_writes_json(tmp_path: Path) -> None:
    output = tmp_path / "session.json"
    assert main(["generate", "--scenario", "normal", "--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8").startswith("[")


def test_cli_rejects_unsupported_extension(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as error:
        main(
            [
                "generate",
                "--scenario",
                "normal",
                "--output",
                str(tmp_path / "session.txt"),
            ]
        )
    assert error.value.code == 2

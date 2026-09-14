"""Data discovery and loading utilities.

These utilities work with any dataset files placed in the ``data/`` directory.
The original datasets are never modified by this module.
"""

import json
from pathlib import Path
from typing import Any

SUPPORTED_SUFFIXES = {".csv", ".json", ".geojson", ".parquet"}

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def discover_files(data_dir: str | Path | None = None) -> list[Path]:
    """Return sorted list of supported data files under *data_dir*."""
    directory = Path(data_dir) if data_dir else _DATA_DIR
    if not directory.exists():
        return []
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def load_json(filename: str, data_dir: str | Path | None = None) -> Any:
    """Load and return a parsed JSON file from the data directory."""
    directory = Path(data_dir) if data_dir else _DATA_DIR
    filepath = directory / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")
    with open(filepath, encoding="utf-8") as fh:
        return json.load(fh)


def load_csv_rows(filename: str, data_dir: str | Path | None = None) -> list[dict[str, str]]:
    """Load a CSV file as a list of dicts (header-keyed rows).

    Uses the stdlib ``csv`` module so pandas is not required at runtime.
    """
    import csv

    directory = Path(data_dir) if data_dir else _DATA_DIR
    filepath = directory / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")
    with open(filepath, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))

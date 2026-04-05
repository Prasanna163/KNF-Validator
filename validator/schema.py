from __future__ import annotations

import csv
from pathlib import Path

REQUIRED_COLUMNS = [
    "molecule_name",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "SNCI",
    "SCDI",
    "backend",
    "nci_grid_spacing",
    "nci_grid_padding",
    "xtb_version",
    "knf_core_version",
    "water_mode",
    "charge",
    "spin",
    "instance_hash",
]

ATLAS_REQUIRED_COLUMNS = list(REQUIRED_COLUMNS)

NUMERIC_FEATURE_COLUMNS = [f"f{i}" for i in range(1, 10)]
KUID_INT_FEATURES = ["f3", "f4", "f7", "f8", "f9"]
KUID_INT_BOUNDS: dict[str, tuple[float, float, str, int]] = {
    "f3": (0.0, 1.0, "linear", 16),
    "f4": (0.0, 30.0, "linear", 16),
    "f7": (-0.10, -0.001, "linear", 16),
    "f8": (0.0, 0.05, "linear", 16),
    "f9": (-5.0, 5.0, "linear", 16),
}


def load_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return rows, fieldnames


def validate_csv_schema(fieldnames: list[str]) -> list[str]:
    field_set = set(fieldnames)
    missing = [name for name in REQUIRED_COLUMNS if name not in field_set]
    if missing:
        return [f"missing required columns: {', '.join(missing)}"]
    return []


def validate_atlas_schema(fieldnames: list[str]) -> list[str]:
    field_set = set(fieldnames)
    missing = [name for name in ATLAS_REQUIRED_COLUMNS if name not in field_set]
    if missing:
        return [f"atlas missing required columns: {', '.join(missing)}"]
    return []

from __future__ import annotations

import json
import math
from pathlib import Path

REQUIRED_MANIFEST_KEYS = [
    "submission_schema_version",
    "knf_version",
    "backend",
    "method",
    "grid_spacing",
    "grid_padding",
    "dtype",
    "row_count",
    "created_at",
]

SUPPORTED_SCHEMA_VERSIONS = {"1", "1.0", "v1"}
SUPPORTED_DTYPES = {"float32", "float64"}


def load_manifest(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return data


def validate_manifest(manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(f"missing required manifest key: {key}")

    if errors:
        return errors

    schema_version = str(manifest.get("submission_schema_version", "")).strip().lower()
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            "unsupported submission_schema_version: "
            f"{manifest.get('submission_schema_version')!r}"
        )

    row_count_raw = manifest.get("row_count")
    try:
        row_count = int(row_count_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        errors.append(f"row_count must be an integer > 0, got {row_count_raw!r}")
    else:
        if row_count <= 0:
            errors.append(f"row_count must be > 0, got {row_count}")

    for field, min_value in (("grid_spacing", 0.0), ("grid_padding", 0.0)):
        value_raw = manifest.get(field)
        try:
            value = float(value_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            errors.append(f"{field} must be numeric, got {value_raw!r}")
            continue
        if not math.isfinite(value):
            errors.append(f"{field} must be finite, got {value_raw!r}")
            continue
        if field == "grid_spacing" and value <= min_value:
            errors.append(f"{field} must be > 0, got {value}")
        if field == "grid_padding" and value < min_value:
            errors.append(f"{field} must be >= 0, got {value}")

    dtype = str(manifest.get("dtype", "")).strip().lower()
    if dtype not in SUPPORTED_DTYPES:
        errors.append(f"unsupported dtype: {manifest.get('dtype')!r}")

    created_at = str(manifest.get("created_at", "")).strip()
    if not created_at:
        errors.append("created_at must be non-empty")

    for field in ("knf_version", "backend", "method"):
        value = str(manifest.get(field, "")).strip()
        if not value:
            errors.append(f"{field} must be non-empty")

    return errors


def canonical_number_string(value: object) -> str:
    number = float(value)
    return format(number, ".12g")


def build_settings_profile(
    *,
    method: object,
    backend: object,
    grid_spacing: object,
    grid_padding: object,
    dtype: object,
    knf_version: object,
) -> str:
    return (
        f"{str(method).strip()}|"
        f"{str(backend).strip()}|"
        f"{canonical_number_string(grid_spacing)}|"
        f"{canonical_number_string(grid_padding)}|"
        f"{str(dtype).strip()}|"
        f"{str(knf_version).strip()}"
    )

from __future__ import annotations

import math

from .dedup import normalize_instance_hash
from .schema import NUMERIC_FEATURE_COLUMNS

INVALID = "invalid"
ALLOWED_BACKENDS = {"torch", "multiwfn"}


def _parse_finite_float(value: object) -> tuple[bool, float | None]:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False, None
    if not math.isfinite(number):
        return False, None
    return True, number


def _parse_int(value: object) -> tuple[bool, int | None]:
    raw = str(value).strip()
    if not raw:
        return False, None
    try:
        return True, int(raw)
    except ValueError:
        return False, None


def _parse_bool(value: object) -> tuple[bool, bool | None]:
    raw = str(value).strip().lower()
    if raw in {"true", "1", "yes", "y"}:
        return True, True
    if raw in {"false", "0", "no", "n"}:
        return True, False
    return False, None


def _clean_text(value: object) -> str:
    return str(value).strip()


def validate_rows(rows: list[dict[str, object]]) -> list[str]:
    stage_errors: list[str] = []

    for idx, row in enumerate(rows, start=1):
        row["_row_index"] = idx
        row["_decision_class"] = ""
        row["_xp"] = 0
        row["_reason"] = ""
        errors: list[str] = []
        numeric: dict[str, float] = {}

        # Surface-level numeric validation only; no physical-range constraints.
        for col in [*NUMERIC_FEATURE_COLUMNS, "SNCI", "nci_grid_spacing", "nci_grid_padding"]:
            ok, value = _parse_finite_float(row.get(col))
            if not ok or value is None:
                errors.append(f"{col} must be numeric and finite")
            else:
                numeric[col] = value

        for col in ("charge", "spin"):
            ok, value = _parse_int(row.get(col))
            if not ok or value is None:
                errors.append(f"{col} must be an integer")
            else:
                row[f"_{col}_int"] = value

        water_ok, water_mode = _parse_bool(row.get("water_mode"))
        if not water_ok or water_mode is None:
            errors.append("water_mode must be boolean (true/false)")
            water_mode = False
        row["_water_mode_bool"] = water_mode

        for field in ("molecule_name", "xtb_version", "knf_core_version", "instance_hash"):
            if not _clean_text(row.get(field, "")):
                errors.append(f"{field} must be non-empty")

        backend = _clean_text(row.get("backend", ""))
        if not backend:
            errors.append("backend must be non-empty")
        elif backend.lower() not in ALLOWED_BACKENDS:
            errors.append("backend must be one of: torch, multiwfn")
        row["_backend_norm"] = backend.lower()

        instance_hash = _clean_text(row.get("instance_hash", ""))
        if instance_hash:
            try:
                row["_instance_hash"] = normalize_instance_hash(instance_hash)
            except Exception as exc:
                errors.append(str(exc))

        scdi_raw = _clean_text(row.get("SCDI", ""))
        if scdi_raw:
            ok, scdi_num = _parse_finite_float(scdi_raw)
            if not ok or scdi_num is None:
                errors.append("SCDI must be numeric and finite when provided")
            else:
                numeric["SCDI"] = scdi_num

        spacing = numeric.get("nci_grid_spacing")
        if spacing is not None and spacing <= 0:
            errors.append("nci_grid_spacing must be > 0")
        padding = numeric.get("nci_grid_padding")
        if padding is not None and padding < 0:
            errors.append("nci_grid_padding must be >= 0")

        if errors:
            row["_decision_class"] = INVALID
            row["_xp"] = 0
            row["_reason"] = "; ".join(errors)
            stage_errors.append(f"row {idx}: {row['_reason']}")
        else:
            row["_num"] = numeric

    return stage_errors

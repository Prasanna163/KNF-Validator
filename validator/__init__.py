from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dedup import build_atlas_reference, mark_atlas_duplicates, mark_internal_duplicates
from .kuid import assign_kuid_int_rows
from .novelty import classify_novelty
from .report import (
    build_console_summary,
    summarize_rows,
    write_accepted_rows,
    write_row_report,
    write_summary_json,
)
from .sanity import validate_rows
from .schema import load_csv_rows, validate_atlas_schema, validate_csv_schema
from .scoring import apply_xp

BUNDLE_CSV_NAME = "atlas_submission.csv"


@dataclass
class ValidationResult:
    summary: dict[str, Any]
    console_summary: str
    summary_json_path: Path | None
    row_report_path: Path | None
    accepted_rows_path: Path | None


def _mark_all_rows_invalid(rows: list[dict[str, object]], reason: str) -> None:
    for idx, row in enumerate(rows, start=1):
        row["_row_index"] = idx
        row["_decision_class"] = "invalid"
        row["_xp"] = 0
        existing_reason = str(row.get("_reason", "")).strip()
        row["_reason"] = existing_reason if existing_reason else reason


def _bundle_integrity_errors(bundle_path: Path, atlas_path: Path) -> list[str]:
    errors: list[str] = []

    if not bundle_path.exists() or not bundle_path.is_dir():
        return [f"submission bundle path does not exist or is not a directory: {bundle_path}"]

    submission_csv = bundle_path / BUNDLE_CSV_NAME

    for path, label in (
        (submission_csv, "submission CSV"),
        (atlas_path, "atlas CSV"),
    ):
        if not path.exists() or not path.is_file():
            errors.append(f"{label} file missing: {path}")
            continue
        try:
            with path.open("r", encoding="utf-8"):
                pass
        except OSError as exc:
            errors.append(f"{label} file is not readable: {path} ({exc})")

    return errors


def validate_submission_bundle(
    bundle_path: str | Path,
    atlas_path: str | Path,
    *,
    out_dir: str | Path | None = None,
    write_artifacts: bool = True,
) -> ValidationResult:
    bundle = Path(bundle_path)
    atlas = Path(atlas_path)
    output_dir = Path(out_dir) if out_dir is not None else bundle
    if write_artifacts:
        output_dir.mkdir(parents=True, exist_ok=True)

    summary_json_path = (
        output_dir / "submission_validation_summary.json" if write_artifacts else None
    )
    row_report_path = (
        output_dir / "submission_validation_report.csv" if write_artifacts else None
    )
    accepted_rows_path = (
        output_dir / "submission_accepted_rows.csv" if write_artifacts else None
    )

    rows: list[dict[str, object]] = []
    hard_reject_reason: str | None = None
    is_valid = False

    integrity_errors = _bundle_integrity_errors(bundle, atlas)
    if integrity_errors:
        hard_reject_reason = "; ".join(integrity_errors)
    else:
        submission_csv = bundle / BUNDLE_CSV_NAME

        try:
            rows_csv, fieldnames = load_csv_rows(submission_csv)
            rows = [dict(r) for r in rows_csv]
        except Exception as exc:  # pragma: no cover - defensive parse errors
            hard_reject_reason = f"unable to read submission CSV: {exc}"
            fieldnames = []

        if hard_reject_reason is None:
            schema_errors = validate_csv_schema(fieldnames)
            if schema_errors:
                hard_reject_reason = "; ".join(schema_errors)

        atlas_rows: list[dict[str, str]] = []
        if hard_reject_reason is None:
            try:
                atlas_rows, atlas_fieldnames = load_csv_rows(atlas)
            except Exception as exc:  # pragma: no cover - defensive parse errors
                hard_reject_reason = f"unable to read atlas CSV: {exc}"
                atlas_fieldnames = []

            if hard_reject_reason is None:
                atlas_errors = validate_atlas_schema(atlas_fieldnames)
                if atlas_errors:
                    hard_reject_reason = "; ".join(atlas_errors)

        if hard_reject_reason is None:
            stage_1_errors = validate_rows(rows)
            if stage_1_errors:
                sample = stage_1_errors[:3]
                hard_reject_reason = (
                    f"stage 1 format validation failed on {len(stage_1_errors)} row(s): "
                    + " | ".join(sample)
                )

        if hard_reject_reason is None:
            assign_kuid_int_rows(rows)
            mark_internal_duplicates(rows)
            atlas_families, atlas_hashes, _family_stats = build_atlas_reference(atlas_rows)
            mark_atlas_duplicates(rows, atlas_hashes)
            classify_novelty(rows, atlas_families)
            apply_xp(rows)
            is_valid = True

    if hard_reject_reason:
        _mark_all_rows_invalid(rows, hard_reject_reason)

    summary = summarize_rows(
        rows,
        is_valid=is_valid,
        hard_reject_reason=hard_reject_reason,
    )

    console_summary = build_console_summary(summary)
    if (
        write_artifacts
        and summary_json_path is not None
        and row_report_path is not None
        and accepted_rows_path is not None
    ):
        write_summary_json(summary_json_path, summary)
        write_row_report(row_report_path, rows)
        write_accepted_rows(accepted_rows_path, rows)

    return ValidationResult(
        summary=summary,
        console_summary=console_summary,
        summary_json_path=summary_json_path,
        row_report_path=row_report_path,
        accepted_rows_path=accepted_rows_path,
    )


def validate_submission_for_backend(
    bundle_path: str | Path,
    atlas_path: str | Path,
) -> dict[str, Any]:
    result = validate_submission_bundle(
        bundle_path,
        atlas_path,
        out_dir=None,
        write_artifacts=False,
    )
    return {
        "is_valid": bool(result.summary.get("is_valid", False)),
        "submission_status": str(result.summary.get("submission_status", "rejected")),
        "summary": result.summary,
    }


__all__ = [
    "ValidationResult",
    "validate_submission_bundle",
    "validate_submission_for_backend",
]

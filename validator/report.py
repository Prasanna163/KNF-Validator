from __future__ import annotations

import csv
import json
from pathlib import Path

from .scoring import compute_submission_status

ROW_REPORT_COLUMNS = [
    "row_index",
    "molecule_name",
    "kuid_int",
    "instance_hash",
    "SNCI",
    "decision_class",
    "xp",
    "reason",
]


def summarize_rows(
    rows: list[dict[str, object]],
    *,
    is_valid: bool,
    hard_reject_reason: str | None,
) -> dict[str, object]:
    counts = {
        "rows_uploaded": len(rows),
        "rows_invalid": 0,
        "rows_internal_duplicates": 0,
        "rows_atlas_duplicates": 0,
        "rows_new_family": 0,
        "rows_new_unique_system": 0,
        "xp_awarded": 0,
    }

    for row in rows:
        decision = str(row.get("_decision_class", ""))
        if decision == "invalid":
            counts["rows_invalid"] += 1
        elif decision == "duplicate_internal":
            counts["rows_internal_duplicates"] += 1
        elif decision == "duplicate_atlas":
            counts["rows_atlas_duplicates"] += 1
        elif decision == "new_family":
            counts["rows_new_family"] += 1
        elif decision == "new_unique_system":
            counts["rows_new_unique_system"] += 1

        counts["xp_awarded"] += int(row.get("_xp", 0))

    counts["rows_valid"] = counts["rows_uploaded"] - counts["rows_invalid"]

    submission_status = compute_submission_status(
        counts,
        hard_reject=hard_reject_reason is not None,
    )

    summary: dict[str, object] = {
        "is_valid": is_valid,
        "submission_status": submission_status,
        **counts,
    }

    if hard_reject_reason:
        summary["hard_reject_reason"] = hard_reject_reason

    return summary


def build_console_summary(summary: dict[str, object]) -> str:
    lines = [
        "KNF Atlas Validation Summary",
        "----------------------------",
        f"Rows uploaded: {summary['rows_uploaded']}",
        f"Rows valid: {summary['rows_valid']}",
        f"Invalid rows: {summary['rows_invalid']}",
        f"Internal duplicates: {summary['rows_internal_duplicates']}",
        f"Atlas duplicates: {summary['rows_atlas_duplicates']}",
        f"New KUID_INT families: {summary['rows_new_family']}",
        f"New unique systems (existing families): {summary['rows_new_unique_system']}",
        f"XP awarded: {summary['xp_awarded']}",
        f"Decision: {str(summary['submission_status']).upper()}",
    ]

    reason = summary.get("hard_reject_reason")
    if reason:
        lines.append(f"Reason: {reason}")

    return "\n".join(lines)


def write_summary_json(path: Path, summary: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")


def write_row_report(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_REPORT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "row_index": row.get("_row_index", ""),
                    "molecule_name": row.get("molecule_name", ""),
                    "kuid_int": row.get("_kuid_int", ""),
                    "instance_hash": row.get("_instance_hash", ""),
                    "SNCI": row.get("SNCI", ""),
                    "decision_class": row.get("_decision_class", ""),
                    "xp": row.get("_xp", 0),
                    "reason": row.get("_reason", ""),
                }
            )


def write_accepted_rows(path: Path, rows: list[dict[str, object]]) -> None:
    accepted_rows = [
        row
        for row in rows
        if str(row.get("_decision_class", "")) in {"new_family", "new_unique_system"}
    ]

    fieldnames: list[str]
    if accepted_rows:
        original_keys = [k for k in accepted_rows[0].keys() if not str(k).startswith("_")]
        fieldnames = original_keys + ["kuid_int", "instance_hash", "decision_class", "xp", "reason"]
    else:
        fieldnames = ["molecule_name", "kuid_int", "instance_hash", "decision_class", "xp", "reason"]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in accepted_rows:
            clean = {k: v for k, v in row.items() if not str(k).startswith("_")}
            clean["kuid_int"] = row.get("_kuid_int", "")
            clean["instance_hash"] = row.get("_instance_hash", "")
            clean["decision_class"] = row.get("_decision_class", "")
            clean["xp"] = row.get("_xp", 0)
            clean["reason"] = row.get("_reason", "")
            writer.writerow(clean)

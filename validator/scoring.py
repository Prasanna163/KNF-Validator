from __future__ import annotations

XP_BY_DECISION = {
    "new_family": 500,
    "new_unique_system": 50,
    "invalid": 0,
    "duplicate_internal": 0,
    "duplicate_atlas": 0,
}


def apply_xp(rows: list[dict[str, object]]) -> None:
    for row in rows:
        decision = str(row.get("_decision_class", ""))
        row["_xp"] = XP_BY_DECISION.get(decision, 0)


def compute_submission_status(
    summary: dict[str, object],
    *,
    hard_reject: bool,
) -> str:
    if hard_reject:
        return "rejected"

    accepted_rows = int(summary.get("rows_new_family", 0)) + int(
        summary.get("rows_new_unique_system", 0)
    )

    if accepted_rows > 0:
        return "accepted"
    return "rejected"

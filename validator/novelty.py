from __future__ import annotations

NEW_FAMILY = "new_family"
NEW_UNIQUE_SYSTEM = "new_unique_system"


def classify_novelty(rows: list[dict[str, object]], atlas_families: set[str]) -> None:
    for row in rows:
        if row.get("_decision_class"):
            continue

        family = str(row.get("_kuid_int", ""))
        if family and family not in atlas_families:
            row["_decision_class"] = NEW_FAMILY
            row["_reason"] = "new KUID_INT family not present in atlas"
        else:
            row["_decision_class"] = NEW_UNIQUE_SYSTEM
            row["_reason"] = "new unique instance in existing KUID_INT family"

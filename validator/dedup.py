from __future__ import annotations

import hashlib
import json
import math
import re

from .kuid import assign_kuid_int_from_values
from .schema import KUID_INT_FEATURES, NUMERIC_FEATURE_COLUMNS

DUPLICATE_INTERNAL = "duplicate_internal"
DUPLICATE_ATLAS = "duplicate_atlas"
INSTANCE_HASH_RE = re.compile(r"^[0-9a-fA-F]{8}$")


def normalize_text(value: object) -> str:
    return str(value).strip()


def normalize_instance_hash(value: object) -> str:
    text = normalize_text(value)
    if not text:
        raise ValueError("instance_hash must be non-empty")
    if not INSTANCE_HASH_RE.fullmatch(text):
        raise ValueError("instance_hash must be 8 hex characters")
    return text.lower()


def canonicalize_smiles(smiles: object) -> str:
    text = normalize_text(smiles)
    if not text:
        raise ValueError("smiles must be non-empty")

    try:
        from rdkit import Chem  # type: ignore
    except Exception:
        # Fallback when RDKit is unavailable locally.
        return text

    mol = Chem.MolFromSmiles(text)
    if mol is None:
        raise ValueError(f"invalid SMILES: {text!r}")
    return str(Chem.MolToSmiles(mol))


def compute_instance_hash(row: dict[str, object]) -> str:
    # Preferred path: trust KNF-CORE provided instance_hash.
    provided = normalize_text(row.get("instance_hash", ""))
    if provided:
        normalized = normalize_instance_hash(provided)
        row["_instance_hash"] = normalized
        return normalized

    # Backward-compatible fallback path if smiles-based records are supplied.
    canonical_smiles = str(row.get("_canonical_smiles", "")).strip()
    if not canonical_smiles:
        canonical_smiles = canonicalize_smiles(row.get("smiles", ""))
        row["_canonical_smiles"] = canonical_smiles

    payload = json.dumps(
        {
            "smiles": canonical_smiles,
            "charge": int(row.get("charge", 0)),
            "spin": int(row.get("spin", 0)),
            "xtb": normalize_text(row.get("xtb_version", "")),
            "spacing": round(float(row.get("nci_grid_spacing", 0.0)), 3),
            "padding": round(float(row.get("nci_grid_padding", 0.0)), 3),
        },
        sort_keys=True,
    )
    normalized = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
    row["_instance_hash"] = normalized
    return normalized


def _extract_family_values(row: dict[str, object]) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for feature in KUID_INT_FEATURES:
        raw = row.get(feature)
        try:
            num = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(num):
            return None
        values[feature] = num
    return values


def _extract_knf_vector(row: dict[str, object]) -> tuple[float, ...] | None:
    values: list[float] = []
    for feature in NUMERIC_FEATURE_COLUMNS:
        raw = row.get(feature)
        try:
            num = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(num):
            return None
        values.append(num)
    return tuple(values)


def _compute_family_stats(vectors: list[tuple[float, ...]]) -> dict[str, object]:
    member_count = len(vectors)
    if member_count == 0:
        return {"member_count": 0, "centroid": tuple(), "sigma": 0.0}

    dims = len(vectors[0])
    centroid = tuple(
        sum(vec[idx] for vec in vectors) / member_count for idx in range(dims)
    )
    distances = [
        math.sqrt(sum((a - b) ** 2 for a, b in zip(vec, centroid))) for vec in vectors
    ]
    mean_distance = sum(distances) / member_count
    variance = sum((d - mean_distance) ** 2 for d in distances) / member_count
    sigma = math.sqrt(variance)

    return {"member_count": member_count, "centroid": centroid, "sigma": sigma}


def mark_internal_duplicates(rows: list[dict[str, object]]) -> None:
    seen_hashes: set[str] = set()
    for row in rows:
        if row.get("_decision_class"):
            continue
        try:
            instance_hash = compute_instance_hash(row)
        except Exception as exc:
            row["_decision_class"] = "invalid"
            row["_xp"] = 0
            row["_reason"] = f"unable to compute instance hash: {exc}"
            continue

        row["_instance_hash"] = instance_hash
        if instance_hash in seen_hashes:
            row["_decision_class"] = DUPLICATE_INTERNAL
            row["_xp"] = 0
            row["_reason"] = "duplicate in submission by instance_hash"
            continue
        seen_hashes.add(instance_hash)


def build_atlas_reference(
    atlas_rows: list[dict[str, str]],
) -> tuple[set[str], set[str], dict[str, dict[str, object]]]:
    families: set[str] = set()
    duplicate_hashes: set[str] = set()
    vectors_by_family: dict[str, list[tuple[float, ...]]] = {}

    for row in atlas_rows:
        try:
            instance_hash = compute_instance_hash(row)
        except Exception:
            continue
        duplicate_hashes.add(instance_hash)

        family_raw = normalize_text(row.get("kuid_int", ""))
        if family_raw:
            family = family_raw
        else:
            family_values = _extract_family_values(row)
            if family_values is None:
                continue
            family = assign_kuid_int_from_values(family_values)

        families.add(family)

        vector = _extract_knf_vector(row)
        if vector is None:
            continue
        vectors_by_family.setdefault(family, []).append(vector)

    family_stats = {
        family: _compute_family_stats(vectors)
        for family, vectors in vectors_by_family.items()
    }

    return families, duplicate_hashes, family_stats


def mark_atlas_duplicates(
    rows: list[dict[str, object]],
    atlas_duplicate_hashes: set[str],
) -> None:
    for row in rows:
        if row.get("_decision_class"):
            continue
        instance_hash = str(row.get("_instance_hash", ""))
        if instance_hash in atlas_duplicate_hashes:
            row["_decision_class"] = DUPLICATE_ATLAS
            row["_xp"] = 0
            row["_reason"] = "duplicate in atlas by instance_hash"

from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path
from uuid import uuid4

from validator import validate_submission_bundle, validate_submission_for_backend
from validator.schema import REQUIRED_COLUMNS


def make_row(
    *,
    molecule_name: str,
    smiles: str,
    f1: float = 3.0,
    f2: float = 120.0,
    f3: float = 0.2,
    f4: float = 5.0,
    f5: float = 300.0,
    f6: float = 1200.0,
    f7: float = -0.02,
    f8: float = 0.01,
    f9: float = 0.3,
    nci_grid_spacing: float = 0.1,
    nci_grid_padding: float = 2.0,
    SNCI: float | None = None,
    **overrides: object,
) -> dict[str, object]:
    snci = SNCI if SNCI is not None else abs(f6 * f7 * (nci_grid_spacing**3))
    default_hash_seed = (
        f"{molecule_name}|{smiles}|{f6}|{f7}|{nci_grid_spacing}|{nci_grid_padding}"
    )
    instance_hash = str(
        overrides.pop(
            "instance_hash",
            hashlib.sha256(default_hash_seed.encode("utf-8")).hexdigest()[:8],
        )
    )
    row: dict[str, object] = {
        "molecule_name": molecule_name,
        "f1": f1,
        "f2": f2,
        "f3": f3,
        "f4": f4,
        "f5": f5,
        "f6": f6,
        "f7": f7,
        "f8": f8,
        "f9": f9,
        "SNCI": snci,
        "SCDI": 0.15,
        "backend": "torch",
        "nci_grid_spacing": nci_grid_spacing,
        "nci_grid_padding": nci_grid_padding,
        "xtb_version": "6.4.1",
        "knf_core_version": "1.0.5",
        "water_mode": "false",
        "charge": 0,
        "spin": 1,
        "instance_hash": instance_hash,
    }
    row.update(overrides)
    return row


def write_submission_bundle(
    bundle_path: Path,
    rows: list[dict[str, object]],
    *,
    drop_columns: list[str] | None = None,
) -> None:
    bundle_path.mkdir(parents=True, exist_ok=True)
    columns = [c for c in REQUIRED_COLUMNS if c not in set(drop_columns or [])]
    with (bundle_path / "atlas_submission.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in columns})


def write_atlas_csv(atlas_path: Path, rows: list[dict[str, object]]) -> None:
    atlas_path.parent.mkdir(parents=True, exist_ok=True)
    with atlas_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in REQUIRED_COLUMNS})


def make_case_paths(case_name: str) -> tuple[Path, Path, Path, Path]:
    base = Path.cwd() / ".test-work"
    base.mkdir(parents=True, exist_ok=True)
    root = base / f"{case_name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    bundle = root / "submission_bundle"
    atlas = root / "atlas_master.csv"
    out = root / "reports"
    return root, bundle, atlas, out


def cleanup_case(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def test_clean_submission_is_accepted() -> None:
    root, bundle, atlas, out = make_case_paths("clean")
    try:
        submission_rows = [
            make_row(
                molecule_name="new-family",
                smiles="CCO",
                f3=0.9,
                f4=24.0,
                f7=-0.08,
                f8=0.03,
                f9=2.0,
            ),
            make_row(
                molecule_name="existing-family-new-instance",
                smiles="CCN",
                f3=0.2,
                f4=5.0,
                f7=-0.02,
                f8=0.01,
                f9=0.3,
            ),
        ]
        atlas_rows = [
            make_row(
                molecule_name="atlas-existing-family",
                smiles="CO",
                f3=0.2,
                f4=5.0,
                f7=-0.02,
                f8=0.01,
                f9=0.3,
            ),
        ]

        write_submission_bundle(bundle, submission_rows)
        write_atlas_csv(atlas, atlas_rows)

        result = validate_submission_bundle(bundle, atlas, out_dir=out)

        assert result.summary["is_valid"] is True
        assert result.summary["submission_status"] == "accepted"
        assert result.summary["rows_new_family"] == 1
        assert result.summary["rows_new_unique_system"] == 1
        assert result.summary["xp_awarded"] == 550
        assert result.summary_json_path and result.summary_json_path.exists()
        assert result.row_report_path and result.row_report_path.exists()
        assert result.accepted_rows_path and result.accepted_rows_path.exists()
    finally:
        cleanup_case(root)


def test_missing_required_column_hard_rejects() -> None:
    root, bundle, atlas, _ = make_case_paths("missing_column")
    try:
        write_submission_bundle(
            bundle,
            [make_row(molecule_name="sample", smiles="CCO")],
            drop_columns=["instance_hash"],
        )
        write_atlas_csv(atlas, [])

        result = validate_submission_bundle(bundle, atlas)

        assert result.summary["is_valid"] is False
        assert result.summary["submission_status"] == "rejected"
        assert "missing required columns" in str(result.summary.get("hard_reject_reason", ""))
    finally:
        cleanup_case(root)


def test_surface_level_accepts_out_of_range_snci_f1_f8_f9() -> None:
    root, bundle, atlas, _ = make_case_paths("surface_only")
    try:
        write_submission_bundle(
            bundle,
            [
                make_row(
                    molecule_name="range-outlier",
                    smiles="CCO",
                    f1=0.8,
                    f8=0.12,
                    f9=-15.0,
                    SNCI=42.0,
                )
            ],
        )
        write_atlas_csv(atlas, [])

        result = validate_submission_bundle(bundle, atlas)

        assert result.summary["is_valid"] is True
        assert result.summary["submission_status"] == "accepted"
        assert result.summary["rows_invalid"] == 0
    finally:
        cleanup_case(root)


def test_scdi_can_be_empty_and_still_pass_surface_validation() -> None:
    root, bundle, atlas, _ = make_case_paths("scdi_optional")
    try:
        write_submission_bundle(
            bundle,
            [
                make_row(
                    molecule_name="scdi-empty",
                    smiles="CCO",
                    SCDI="",
                    water_mode="false",
                )
            ],
        )
        write_atlas_csv(atlas, [])

        result = validate_submission_bundle(bundle, atlas)

        assert result.summary["is_valid"] is True
        assert result.summary["submission_status"] == "accepted"
        assert result.summary["rows_invalid"] == 0
    finally:
        cleanup_case(root)


def test_atlas_duplicate_by_instance_hash_rejects_when_only_duplicates() -> None:
    root, bundle, atlas, _ = make_case_paths("atlas_dupe")
    try:
        row = make_row(molecule_name="dup", smiles="CCC")
        write_submission_bundle(bundle, [row])
        write_atlas_csv(atlas, [row])

        result = validate_submission_bundle(bundle, atlas)

        assert result.summary["rows_atlas_duplicates"] == 1
        assert result.summary["xp_awarded"] == 0
        assert result.summary["submission_status"] == "rejected"
    finally:
        cleanup_case(root)


def test_backend_entrypoint_works_without_writing_artifacts() -> None:
    root, bundle, atlas, _ = make_case_paths("backend_mode")
    try:
        write_submission_bundle(bundle, [make_row(molecule_name="backend", smiles="CCO")])
        write_atlas_csv(atlas, [])

        payload = validate_submission_for_backend(bundle, atlas)

        assert payload["is_valid"] is True
        assert payload["submission_status"] == "accepted"
        assert isinstance(payload["summary"], dict)
        assert (bundle / "submission_validation_summary.json").exists() is False
        assert (bundle / "submission_validation_report.csv").exists() is False
        assert (bundle / "submission_accepted_rows.csv").exists() is False
    finally:
        cleanup_case(root)

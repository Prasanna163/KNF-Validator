from __future__ import annotations

import argparse
from pathlib import Path

from . import validate_submission_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knf-validate",
        description="Validate a KNF Atlas submission bundle CSV against a local atlas CSV.",
    )
    parser.add_argument("bundle_path", help="Path to submission_bundle directory")
    parser.add_argument("--atlas", required=True, help="Path to atlas_master.csv")
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory for reports (default: submission_bundle directory)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    result = validate_submission_bundle(
        Path(args.bundle_path),
        Path(args.atlas),
        out_dir=Path(args.out) if args.out else None,
    )

    print(result.console_summary)
    print()
    print(f"JSON summary: {result.summary_json_path}")
    print(f"Row report: {result.row_report_path}")
    print(f"Accepted rows: {result.accepted_rows_path}")

    status = str(result.summary.get("submission_status", "rejected"))
    if status in {"accepted"}:
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


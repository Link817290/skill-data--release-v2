#!/usr/bin/env python3
"""Derive hidden scoring data from the already-produced expert ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    with args.golden.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or any(not row.get("finding_id") for row in rows):
        raise RuntimeError("Golden ledger has no identified findings")

    source_names = [
        "01_staff_comment.pdf",
        "02_company_response.htm",
        "03_amended_registration_statement.htm",
        "04_issued_filing.htm",
        "05_remediation_annual_report.pdf",
        "06_estimate_change_annual_report.pdf",
        "review_template.csv",
    ]
    hashes = {
        name: hashlib.sha256((args.workspace / name).read_bytes()).hexdigest()
        for name in source_names
    }
    payload = {
        "version": 1,
        "golden_rows": rows,
        "weights": {row["finding_id"]: 1.0 / len(rows) for row in rows},
        "source_sha256": hashes,
        "reward_formulas": {
            "strict": "integrity_gate * sum(issue_weight * evidence_state_score)",
            "lenient": "1 if usable_traceable_issue_ledger else 0",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

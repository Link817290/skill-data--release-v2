#!/usr/bin/env python3
"""Create a deterministic case-to-report ledger from a versioned CSV header."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case-col", required=True)
    parser.add_argument("--version-col", required=True)
    parser.add_argument("--report-col", required=True)
    parser.add_argument("--date-col", required=True)
    return parser.parse_args()


def numeric_identifier(value: str) -> tuple[int, object]:
    text = value.strip()
    return (1, int(text)) if text.isdigit() else (0, text)


def main() -> int:
    args = parse_args()
    selected: dict[str, tuple[tuple[object, ...], dict[str, str]]] = {}
    rejected: dict[str, list[str]] = {}
    input_rows = 0

    with args.input.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {args.case_col, args.version_col, args.report_col, args.date_col}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"missing columns: {sorted(missing)}")
        for row in reader:
            input_rows += 1
            case_id = row[args.case_col].strip()
            report_id = row[args.report_col].strip()
            version = row[args.version_col].strip()
            if not case_id or not report_id or not version.isdigit():
                raise SystemExit(f"unusable identifier or version at input row {input_rows + 1}")
            rank = (int(version), row[args.date_col].strip(), numeric_identifier(report_id))
            previous = selected.get(case_id)
            if previous is None or rank > previous[0]:
                if previous is not None:
                    rejected.setdefault(case_id, []).append(previous[1][args.report_col].strip())
                selected[case_id] = (rank, row)
            else:
                rejected.setdefault(case_id, []).append(report_id)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case_id",
        "selected_report_id",
        "selected_version",
        "selected_date",
        "rejected_report_ids",
    ]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case_id in sorted(selected, key=numeric_identifier):
            row = selected[case_id][1]
            writer.writerow(
                {
                    "case_id": case_id,
                    "selected_report_id": row[args.report_col].strip(),
                    "selected_version": row[args.version_col].strip(),
                    "selected_date": row[args.date_col].strip(),
                    "rejected_report_ids": "|".join(
                        sorted(rejected.get(case_id, []), key=numeric_identifier)
                    ),
                }
            )

    rejected_count = sum(len(values) for values in rejected.values())
    print(f"input_rows={input_rows}")
    print(f"retained_cases={len(selected)}")
    print(f"rejected_versions={rejected_count}")
    print(f"closure_ok={input_rows == len(selected) + rejected_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

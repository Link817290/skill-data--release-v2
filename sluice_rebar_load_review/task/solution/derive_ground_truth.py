#!/usr/bin/env python3
"""Derive the verifier key from the generated reference workbook."""
import json
import sys
from pathlib import Path
from openpyxl import load_workbook

def main():
    book = load_workbook(sys.argv[1], data_only=False, read_only=True)
    ws = book["Review"]
    headers = [c.value for c in next(ws.iter_rows())]
    index = {h: i for i, h in enumerate(headers)}
    checks = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        checks.append({
            "check_id": row[index["check_id"]],
            "subject": row[index["subject"]],
            "status": row[index["status"]],
            "source_locator": row[index["source_locator"]],
            "observed_value": row[index["observed_value"]],
            "expected_or_limit": row[index["expected_or_limit"]],
            "formula_required": bool(row[index["formula"]]),
        })
    out = {"schema_version": "1.1", "checks": checks}
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()

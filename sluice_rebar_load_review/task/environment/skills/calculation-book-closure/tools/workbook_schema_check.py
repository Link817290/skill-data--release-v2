#!/usr/bin/env python3
"""Check caller-supplied workbook rows for basic closure; no answer knowledge."""
import argparse
import json
from pathlib import Path

from openpyxl import load_workbook


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook")
    args = ap.parse_args()
    book = load_workbook(args.workbook, data_only=False, read_only=True)
    sheet = book["Review"] if "Review" in book.sheetnames else book[book.sheetnames[0]]
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        print(json.dumps({"rows": 0, "missing_status": 0, "missing_locator": 0}, indent=2))
        return
    headers = [str(x or "").strip().lower() for x in rows[0]]
    def idx(names):
        for n in names:
            if n in headers:
                return headers.index(n)
        return None
    id_i = idx(["check_id", "id"])
    status_i = idx(["status", "conclusion"])
    loc_i = idx(["source_locator", "source", "locator"])
    body = rows[1:]
    result = {"rows": len(body), "missing_status": 0, "missing_locator": 0, "duplicate_ids": 0}
    seen = set()
    for row in body:
        if status_i is None or not str(row[status_i] or "").strip():
            result["missing_status"] += 1
        if loc_i is None or not str(row[loc_i] or "").strip():
            result["missing_locator"] += 1
        if id_i is not None:
            key = str(row[id_i] or "").strip()
            if key in seen and key:
                result["duplicate_ids"] += 1
            seen.add(key)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

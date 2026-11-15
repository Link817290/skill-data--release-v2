#!/usr/bin/env python3
"""Validate workbook structure without encoding task answers."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from openpyxl import load_workbook


REQUIRED = {
    "testid": "Test ID",
    "testmodule": "Test Module",
    "testcasename": "Test Case Name",
    "preconditions": "Preconditions",
    "teststeps": "Test Steps",
    "expectedresult": "Expected Result",
}


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def find_case_sheet(workbook):
    ranked = []
    for sheet in workbook.worksheets:
        first_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
        headers = [norm(value) for value in first_row]
        recognized = sum(key in headers for key in REQUIRED)
        ranked.append((recognized, sheet.max_row, sheet))
    recognized, _, sheet = max(ranked, key=lambda item: (item[0], item[1]))
    return sheet if recognized else None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_deliverable.py <workbook.xlsx>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file() or path.suffix.lower() != ".xlsx":
        print("FAIL: provide a readable .xlsx workbook", file=sys.stderr)
        return 1
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet = find_case_sheet(workbook)
    except Exception as exc:
        print(f"FAIL: workbook cannot be read: {exc}", file=sys.stderr)
        return 1
    if sheet is None or sheet.max_row < 2:
        print("FAIL: workbook has no test-case table", file=sys.stderr)
        return 1
    first_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
    headers = {norm(value): index for index, value in enumerate(first_row) if norm(value)}
    missing = [label for key, label in REQUIRED.items() if key not in headers]
    if missing:
        print("FAIL: missing required columns: " + ", ".join(missing), file=sys.stderr)
        return 1
    substantive = 0
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if all(index < len(values) and str(values[index] or "").strip() for key, index in headers.items() if key in REQUIRED):
            substantive += 1
    if substantive == 0:
        print("FAIL: no complete test-case rows", file=sys.stderr)
        return 1
    print(f"PASS: {substantive} structurally complete test-case row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

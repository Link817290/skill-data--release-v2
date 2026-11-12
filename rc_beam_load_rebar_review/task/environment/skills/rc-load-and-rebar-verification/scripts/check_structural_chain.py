#!/usr/bin/env python3
"""Neutral structural workbook closure checker.

The script checks artifact structure only. It does not solve the beam or emit
engineering conclusions; the author must provide the calculations and statuses.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    try:
        import openpyxl
        book = openpyxl.load_workbook(args.workbook, data_only=False)
    except Exception as exc:
        args.output.write_text(json.dumps({"readable": False, "error": str(exc)}), encoding="utf-8")
        return
    formula_cells = []
    cross_sheet = []
    unit_cells = []
    status_cells = []
    for ws in book.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                value = cell.value
                if isinstance(value, str) and value.startswith("="):
                    formula_cells.append(f"{ws.title}!{cell.coordinate}")
                    if "!" in value:
                        cross_sheet.append(f"{ws.title}!{cell.coordinate}")
                if isinstance(value, str) and value.strip().lower() in {"pass", "fail", "review"}:
                    status_cells.append(f"{ws.title}!{cell.coordinate}")
                if isinstance(value, str) and re.search(r"\b(kip|in|psi|lb|ft|in2|in²)\b", value, re.I):
                    unit_cells.append(f"{ws.title}!{cell.coordinate}")
    payload = {
        "readable": True,
        "sheet_count": len(book.sheetnames),
        "sheets": book.sheetnames,
        "formula_count": len(formula_cells),
        "cross_sheet_formula_count": len(cross_sheet),
        "unit_cell_count": len(unit_cells),
        "status_cell_count": len(status_cells),
        "formula_cells": formula_cells,
    }
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()

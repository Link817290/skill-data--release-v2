#!/usr/bin/env python3
"""Report formula coverage and cross-sheet references in an xlsx workbook."""
import sys
from openpyxl import load_workbook

if len(sys.argv) != 2:
    raise SystemExit("usage: audit_workbook_formulas.py <workbook.xlsx>")
wb = load_workbook(sys.argv[1], data_only=False, read_only=True)
for ws in wb.worksheets:
    formulas = []
    cross = []
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                formulas.append(cell.coordinate)
                if "!" in cell.value:
                    cross.append(cell.coordinate)
    print(f"{ws.title}: formulas={len(formulas)}, cross_sheet={len(cross)}")

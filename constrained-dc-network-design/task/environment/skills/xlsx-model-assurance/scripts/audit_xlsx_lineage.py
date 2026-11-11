#!/usr/bin/env python3
"""Report structural formula-lineage and review controls in an XLSX workbook."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


ERROR_TOKENS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!")


def audit(path: Path) -> dict[str, Any]:
    is_zip = zipfile.is_zipfile(path)
    workbook = load_workbook(path, read_only=False, data_only=False, keep_links=True)
    sheet_reports = []
    total_formulas = 0
    total_cross_sheet = 0
    external_formulas = []
    error_cells = []
    for sheet in workbook.worksheets:
        formulas = []
        cross_sheet = []
        for row in sheet.iter_rows():
            for cell in row:
                value = cell.value
                if cell.data_type == "e" or (isinstance(value, str) and any(token in value for token in ERROR_TOKENS)):
                    error_cells.append({"sheet": sheet.title, "cell": cell.coordinate, "value": str(value)})
                if cell.data_type != "f":
                    continue
                text = str(value)
                formulas.append(cell.coordinate)
                if "!" in text:
                    cross_sheet.append(cell.coordinate)
                if re.search(r"\[[^\]]+\]", text):
                    external_formulas.append({"sheet": sheet.title, "cell": cell.coordinate, "formula": text})
        total_formulas += len(formulas)
        total_cross_sheet += len(cross_sheet)
        sheet_reports.append({
            "sheet": sheet.title,
            "state": sheet.sheet_state,
            "max_row": sheet.max_row,
            "max_column": sheet.max_column,
            "formula_count": len(formulas),
            "cross_sheet_formula_count": len(cross_sheet),
            "formula_examples": formulas[:5],
            "auto_filter": sheet.auto_filter.ref,
            "freeze_panes": str(sheet.freeze_panes or ""),
            "merged_range_count": len(sheet.merged_cells.ranges),
        })
    declared_external_links = len(getattr(workbook, "_external_links", []))
    calculation_mode = getattr(workbook.calculation, "calcMode", None)
    workbook.close()
    return {
        "input": str(path),
        "ooxml_zip_valid": is_zip,
        "sheet_count": len(sheet_reports),
        "formula_count": total_formulas,
        "cross_sheet_formula_count": total_cross_sheet,
        "formula_error_cells": error_cells,
        "external_link_formulas": external_formulas,
        "declared_external_link_count": declared_external_links,
        "calculation_mode": calculation_mode,
        "sheets": sheet_reports,
        "business_logic_warning": "This structural report does not validate formula meaning or population reconciliation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.workbook)
    rendered = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["ooxml_zip_valid"] and not result["formula_error_cells"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


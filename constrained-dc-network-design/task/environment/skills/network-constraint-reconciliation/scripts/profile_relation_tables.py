#!/usr/bin/env python3
"""Profile XLSX table grains and candidate key columns without interpreting them."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


def display(value: Any) -> str:
    return "" if value is None else str(value).strip()


def profile(path: Path, header_row: int, sample_rows: int) -> dict[str, Any]:
    workbook = load_workbook(path, read_only=True, data_only=False)
    sheets = []
    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        for _ in range(header_row - 1):
            next(rows, None)
        headers = [display(value) or f"column_{index + 1}" for index, value in enumerate(next(rows, ()))]
        values_by_column = [[] for _ in headers]
        formula_cells = 0
        populated_rows = 0
        for row_number, row in enumerate(rows, start=1):
            if row_number > sample_rows:
                break
            if not any(value not in (None, "") for value in row):
                continue
            populated_rows += 1
            for index in range(len(headers)):
                value = row[index] if index < len(row) else None
                if isinstance(value, str) and value.startswith("="):
                    formula_cells += 1
                if value not in (None, ""):
                    values_by_column[index].append(display(value))
        columns = []
        for name, values in zip(headers, values_by_column):
            counts = Counter(values)
            columns.append({
                "header": name,
                "nonblank_sample": len(values),
                "distinct_sample": len(counts),
                "duplicate_value_count": sum(1 for count in counts.values() if count > 1),
                "sample_unique": bool(values) and len(values) == len(counts),
                "examples": list(dict.fromkeys(values))[:3],
            })
        sheets.append({
            "sheet": sheet.title,
            "max_row_reported": sheet.max_row,
            "max_column_reported": sheet.max_column,
            "populated_rows_sampled": populated_rows,
            "formula_cells_sampled": formula_cells,
            "columns": columns,
        })
    workbook.close()
    return {
        "input": str(path),
        "header_row": header_row,
        "sample_limit_per_sheet": sample_rows,
        "sheet_count": len(sheets),
        "sheets": sheets,
        "interpretation_warning": "Candidate keys and table roles require business-semantic review.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--header-row", type=int, default=1)
    parser.add_argument("--sample-rows", type=int, default=10000)
    args = parser.parse_args()
    if args.header_row < 1 or args.sample_rows < 1:
        parser.error("--header-row and --sample-rows must be positive")
    result = profile(args.workbook, args.header_row, args.sample_rows)
    rendered = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


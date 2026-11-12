from __future__ import annotations

import re
import sys
from pathlib import Path

from openpyxl import load_workbook


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


workspace = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
input_path = workspace / "匿名体检检查明细.xlsx"
output_path = workspace / "体检总检结论.xlsx"
errors: list[str] = []

if not input_path.is_file():
    errors.append("Missing 匿名体检检查明细.xlsx")
if not output_path.is_file():
    errors.append("Missing 体检总检结论.xlsx")

if input_path.is_file() and output_path.is_file():
    source = load_workbook(input_path, read_only=True, data_only=True)
    source_cases = {text(row[0]) for row in source["病例索引"].iter_rows(min_row=2, values_only=True) if text(row[0])}
    source_rows = {text(row[0]): text(row[1]) for row in source["检查明细"].iter_rows(min_row=2, values_only=True) if text(row[0])}
    result = load_workbook(output_path, read_only=True, data_only=True)
    if not {"总检结论", "病例汇总"}.issubset(result.sheetnames):
        errors.append("The output workbook is missing required worksheets")
    else:
        summary_cases = [text(row[0]) for row in result["病例汇总"].iter_rows(min_row=2, values_only=True) if text(row[0])]
        if set(summary_cases) != source_cases or len(summary_cases) != len(source_cases):
            errors.append("病例汇总 does not cover every case exactly once")
        for row in result["总检结论"].iter_rows(min_row=2, values_only=True):
            case_id, _, conclusion, evidence = map(text, row[:4])
            if not any((case_id, conclusion, evidence)):
                continue
            if case_id not in source_cases:
                errors.append(f"Unknown case ID: {case_id}")
            if not conclusion:
                errors.append(f"{case_id} contains an empty conclusion")
            ids = [part for part in re.split(r"[;,；，\s]+", evidence) if part]
            if not ids:
                errors.append(f"{case_id}: {conclusion} is missing evidence-row IDs")
            elif any(source_rows.get(row_id) != case_id for row_id in ids):
                errors.append(f"{case_id}: {conclusion} cites invalid or cross-case evidence-row IDs")

if errors:
    print("FAIL")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)
print("PASS")

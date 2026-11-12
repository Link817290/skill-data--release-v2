from __future__ import annotations

import json
import os
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill


SOLUTION = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("AGENT_WORKSPACE", "/app/environment/workspace"))
if not WORKSPACE.exists():
    WORKSPACE = Path.cwd()


def style_header(sheet) -> None:
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


payload = json.loads((SOLUTION / "gold_payload.json").read_text(encoding="utf-8"))
workbook = openpyxl.Workbook()
conclusion_sheet = workbook.active
conclusion_sheet.title = "总检结论"
summary_sheet = workbook.create_sheet("病例汇总")
conclusion_sheet.append(["病例编号", "结论序号", "标准体检结论", "证据明细行号", "判断说明"])
summary_sheet.append(["病例编号", "结论项数", "总检状态", "复核备注"])

for case in payload["cases"]:
    for index, conclusion in enumerate(case["conclusions"], start=1):
        evidence = ";".join(conclusion["evidence"])
        conclusion_sheet.append(
            [case["case_id"], index, conclusion["label"], evidence, f"依据 {evidence} 归纳"]
        )
    summary_sheet.append(
        [
            case["case_id"],
            len(case["conclusions"]),
            case["status"],
            "已按病例完成终审结论重建与证据回指",
        ]
    )

for sheet in (conclusion_sheet, summary_sheet):
    style_header(sheet)
for index, width in enumerate([18, 12, 42, 36, 60], start=1):
    conclusion_sheet.column_dimensions[openpyxl.utils.get_column_letter(index)].width = width
for index, width in enumerate([18, 14, 20, 60], start=1):
    summary_sheet.column_dimensions[openpyxl.utils.get_column_letter(index)].width = width

WORKSPACE.mkdir(parents=True, exist_ok=True)
workbook.save(WORKSPACE / "体检总检结论.xlsx")

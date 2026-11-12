#!/usr/bin/env python3
"""Derive verifier anchors from the reference workbook, never the reverse."""
from __future__ import annotations
import json, sys
from pathlib import Path
import openpyxl

def main(workbook_path: str, output_path: str):
    wb = openpyxl.load_workbook(workbook_path, data_only=False)
    findings = {}
    ws = wb["Findings"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0]: findings[str(row[0])] = str(row[2]).upper()
    gt = {
      "required_fields": ["dead_load","live_load","dead_factor","live_factor","span","h","bw","fc","fy","As_comp","d_prime","As_tension","d_flexure","d_shear","Av","beta1","phi_flex","phi_shear","Mu_reported","Vu_reported","s_trial","s_adopted","smax_reported"],
      "findings": findings,
      "sheet_roles": ["Source_Inputs","Load_Combinations","Flexure","Shear","Findings","Summary"],
      "controlled_statuses": ["PASS","FAIL","REVIEW"],
      "numeric_tolerances": {"actions": 0.01, "capacities": 0.03, "ratios": 0.03},
      "formula_requirements": {"minimum_formula_count": 15, "minimum_cross_sheet_count": 8},
      "golden_scores": {"strict": 1.0, "lenient": 1.0}
    }
    Path(output_path).write_text(json.dumps(gt, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

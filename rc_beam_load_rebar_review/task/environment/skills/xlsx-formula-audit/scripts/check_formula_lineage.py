#!/usr/bin/env python3
"""Read-only formula lineage scan for an XLSX workbook."""
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
        wb = openpyxl.load_workbook(args.workbook, data_only=False, keep_links=True)
    except Exception as exc:
        args.output.write_text(json.dumps({"readable": False, "error": str(exc)}), encoding="utf-8")
        return
    formulas = []
    external = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    rec = {"sheet": ws.title, "cell": c.coordinate, "formula": c.value}
                    formulas.append(rec)
                    if "[" in c.value or "]" in c.value or "http:" in c.value.lower() or "https:" in c.value.lower():
                        external.append(rec)
    cross = [x for x in formulas if "!" in x["formula"]]
    args.output.write_text(json.dumps({"readable": True, "formula_count": len(formulas), "cross_sheet_count": len(cross), "external_link_count": len(external), "external_links": external}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()

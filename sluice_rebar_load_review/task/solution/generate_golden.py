#!/usr/bin/env python3
"""Derive the reference review workbook from the supplied report."""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


HERE = Path(__file__).resolve().parent
LOCAL_TASK = HERE.parent
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(LOCAL_TASK / "environment" / "workspace")))
PDF = WORKSPACE_ROOT / "materials" / "full_report_original.pdf"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "golden_deliverable.xlsx"


def report_text() -> str:
    p = subprocess.run(["pdftotext", "-layout", str(PDF), "-"], check=True, capture_output=True)
    text = p.stdout.decode("utf-8", errors="replace")
    anchors = [
        "表 2.4-4", "表格 2.4-6", "表 2.4-8", "表 2.4-9", "表 2.4-13",
        "钢筋保护层厚度、混凝土裂缝控制", "2143mm2", "4888mm2", "1725mm2",
        "2400mm2", "1522mm2", "4608mm2", "750mm2", "910mm2", "965mm",
        "243.68", "210.66", "682.95", "331.94", "574.48", "6D20/12D28", "20D25",
    ]
    missing = [a for a in anchors if a not in text]
    if missing:
        raise RuntimeError("source anchors missing: " + ", ".join(missing))
    return text


def area(count, diameter):
    return count * math.pi * diameter * diameter / 4.0


def rows():
    # Values are transcribed from the report and the derived numbers are kept as
    # visible intermediate evidence rather than hidden in the validator.
    return [
        {"check_id":"LC-01", "subject":"Edge pier anti-sliding factors", "source_locator":"§2.4, Table 2.4-4", "observed_value":"Kc 1.42, 1.96, 1.63, 1.57, 1.54, 1.84, 1.67, 1.57; allowances 1.08, 1.08, 1.08, 1.08, 1.03, 1.03, 1.03, 1.00", "expected_or_limit":"Each applicable Kc >= allowance", "derived_value":"all eight comparisons satisfy", "status":"PASS", "finding":"The reported factors meet their case-specific allowances.", "formula":"=MIN(1.42-1.08,1.96-1.08,1.63-1.08,1.57-1.08,1.54-1.03,1.84-1.03,1.67-1.03,1.57-1.00)"},
        {"check_id":"LC-02", "subject":"Edge pier maximum bearing stress", "source_locator":"§2.4, Table 2.4-4", "observed_value":"max 243.68 kPa", "expected_or_limit":"allowable 500 kPa", "derived_value":243.68, "status":"PASS", "finding":"The maximum reported bearing stress is below the stated allowable value.", "formula":"=243.68<=500"},
        {"check_id":"LC-03", "subject":"Central pier anti-sliding factors", "source_locator":"§2.4, Table 2.4-6", "observed_value":"Kc 2.03, 4.78, 2.88, 4.35, 1.86, 1.41; allowances 1.08, 1.08, 1.08, 1.03, 1.03, 1.00", "expected_or_limit":"Each applicable Kc >= allowance", "derived_value":"all six comparisons satisfy", "status":"PASS", "finding":"The reported central-pier factors meet the allowances shown for each case.", "formula":"=MIN(2.03-1.08,4.78-1.08,2.88-1.08,4.35-1.03,1.86-1.03,1.41-1.00)"},
        {"check_id":"LC-04", "subject":"Central pier maximum bearing stress", "source_locator":"§2.4, Table 2.4-6", "observed_value":"max 210.66 kPa", "expected_or_limit":"allowable 500 kPa", "derived_value":210.66, "status":"PASS", "finding":"The worst reported central-pier bearing stress remains below the allowable value.", "formula":"=210.66<=500"},
        {"check_id":"LC-05", "subject":"Small base vertical-force subtotal", "source_locator":"§2.4, Table 2.4-8", "observed_value":"downward 682.95 kN; upward 331.94 kN", "expected_or_limit":"downward = 322.75 + 360.20; upward = 331.94", "derived_value":682.95, "status":"PASS", "finding":"The downward subtotal closes to the two listed downward actions and the upward subtotal is carried separately.", "formula":"=322.75+360.20"},
        {"check_id":"LC-06", "subject":"Small base signed moment balance", "source_locator":"§2.4, Table 2.4-8", "observed_value":"water 899.78 kN·m; uplift -325.30 kN·m; resultant 574.48 kN·m", "expected_or_limit":"signed sum = resultant", "derived_value":574.48, "status":"PASS", "finding":"The uplift moment is retained with its negative sign and the signed sum matches the reported resultant.", "formula":"=899.78+(-325.30)"},
        {"check_id":"LC-07", "subject":"Load-case scope for a dash entry", "source_locator":"§2.4, text before Tables 2.4-4 to 2.4-6", "observed_value":"Kc shown as '-' for the completed case in Table 2.4-4", "expected_or_limit":"Applicability must be stated before treating dash as zero or pass", "derived_value":"scope statement does not explicitly explain this dash", "status":"REVIEW", "finding":"A dash is not a numeric zero; the report does not give a member-specific explanation for this omitted factor, so the scope basis remains open.", "formula":""},
        {"check_id":"SV-01", "subject":"Machine-bridge beam crack widths and exposure assignment", "source_locator":"§2.4, Table 2.4-9 and §2.2.4.5", "observed_value":"0.19, 0.15, 0.15, 0.13, 0.16 mm; class-II 0.30 mm and class-III 0.25 mm limits", "expected_or_limit":"member exposure must be identified before selecting the governing crack limit", "derived_value":0.19, "status":"REVIEW", "finding":"The listed widths are below both stated limits, but the table does not bind each member to an exposure class, so final approval remains open.", "formula":"=MAX(0.19,0.15,0.15,0.13,0.16)"},
        {"check_id":"SV-02", "subject":"Machine-bridge beam deflections", "source_locator":"§2.4, Table 2.4-9", "observed_value":"27.8, 28.6, 27.6, 4.7, 4.3 mm", "expected_or_limit":"L/400 = 33 mm", "derived_value":28.6, "status":"PASS", "finding":"The maximum listed beam deflection is below the table's stated 33 mm allowance.", "formula":"=MAX(27.8,28.6,27.6,4.7,4.3)<=33"},
        {"check_id":"SV-03", "subject":"Bridge slab crack width and exposure assignment", "source_locator":"§2.4, Table 2.4-9 and §2.2.4.5", "observed_value":"0.01 mm; class-II 0.30 mm and class-III 0.25 mm limits", "expected_or_limit":"member exposure must be identified before selecting the governing crack limit", "derived_value":0.01, "status":"REVIEW", "finding":"The numeric width is below both stated limits, but the member-specific exposure assignment is absent.", "formula":"=0.01"},
        {"check_id":"SV-04", "subject":"Bridge slab deflection", "source_locator":"§2.4, Table 2.4-9", "observed_value":"0.13 mm", "expected_or_limit":"L/400 = 33 mm", "derived_value":0.13, "status":"PASS", "finding":"The listed slab deflection is below the table allowance.", "formula":"=0.13<=33"},
        {"check_id":"SV-05", "subject":"Cap beam crack width and exposure assignment", "source_locator":"§2.4, Table 2.4-9 and §2.2.4.5", "observed_value":"0.04 mm; class-II 0.30 mm and class-III 0.25 mm limits", "expected_or_limit":"member exposure must be identified before selecting the governing crack limit", "derived_value":0.04, "status":"REVIEW", "finding":"The numeric width is below both stated limits, but the member-specific exposure assignment is absent.", "formula":"=0.04"},
        {"check_id":"SV-06", "subject":"Cap beam deflection", "source_locator":"§2.4, Table 2.4-9", "observed_value":"1.0 mm", "expected_or_limit":"L/400 = 33 mm", "derived_value":1.0, "status":"PASS", "finding":"The cap-beam deflection is below the table allowance.", "formula":"=1.0<=33"},
        {"check_id":"RF-01", "subject":"Edge-pier toe reinforcement demand", "source_locator":"§2.4, after Table 2.4-5", "observed_value":"required 2143 mm² per metre; provided arrangement not stated", "expected_or_limit":"Aprovided >= 2143 mm²/m", "derived_value":"provided area absent", "status":"REVIEW", "finding":"The demand is disclosed, but the report does not provide a corresponding bar arrangement or area for this location.", "formula":""},
        {"check_id":"RF-02", "subject":"Edge-pier rib reinforcement demand", "source_locator":"§2.4, after Table 2.4-5", "observed_value":"required 4888 mm²; provided arrangement not stated", "expected_or_limit":"Aprovided >= 4888 mm²", "derived_value":"provided area absent", "status":"REVIEW", "finding":"The required area is stated without a matching provided-steel record, so adequacy cannot be closed.", "formula":""},
        {"check_id":"RF-03", "subject":"Central-pier strip reinforcement demand", "source_locator":"§2.4, after Table 2.4-7", "observed_value":"required 1725 mm² per metre; provided arrangement not stated", "expected_or_limit":"Aprovided >= 1725 mm²/m", "derived_value":"provided area absent", "status":"REVIEW", "finding":"The per-metre demand is present but the supplied report does not state the provided arrangement for this strip.", "formula":""},
        {"check_id":"RF-04", "subject":"Central-pier base reinforcement demand", "source_locator":"§2.4, after Table 2.4-7", "observed_value":"required 2400 mm² per metre; provided arrangement not stated", "expected_or_limit":"Aprovided >= 2400 mm²/m", "derived_value":"provided area absent", "status":"REVIEW", "finding":"The base demand is disclosed but no corresponding provided area is supplied.", "formula":""},
        {"check_id":"RF-05", "subject":"Machine-bridge beam reinforcement capacity", "source_locator":"§2.4, Table 2.4-9", "observed_value":"bar marks shown (for example 6D20/12D28); required steel or design action not stated", "expected_or_limit":"compare provided area with the governing demand", "derived_value":"binding demand absent", "status":"REVIEW", "finding":"Bar marks can be converted to an area, but the report gives no required area or governing action for the beam rows; capacity is therefore not demonstrated.", "formula":"=6*PI()*20^2/4"},
        {"check_id":"RF-06", "subject":"Rack-column reinforcement capacity", "source_locator":"§2.4, Table 2.4-9", "observed_value":"20D25 shown; required steel or design action not stated", "expected_or_limit":"compare provided area with the governing demand", "derived_value":area(20,25), "status":"REVIEW", "finding":"The bar mark yields a mechanical area, but the required area and governing action are absent, so adequacy remains open.", "formula":"=20*PI()*25^2/4"},
        {"check_id":"RF-07", "subject":"Left-wing-wall reinforcement demand", "source_locator":"§2.4, after Table 2.4-13", "observed_value":"toe 1522 mm²/m; heel/face 1200 mm²; rib 4608 mm²; provided arrangements not stated", "expected_or_limit":"provided area must be compared at each location", "derived_value":"provided areas absent", "status":"REVIEW", "finding":"The report lists demands for the left wing wall but not the corresponding provided steel at those locations.", "formula":""},
        {"check_id":"RF-08", "subject":"Right-wing-wall reinforcement demand", "source_locator":"§2.4, after Table 2.4-13", "observed_value":"toe 750 mm²/m; heel 910 mm²; upright 965 mm²; provided arrangements not stated", "expected_or_limit":"provided area must be compared at each location", "derived_value":"provided areas absent", "status":"REVIEW", "finding":"The report lists right-wing-wall demands but omits the matching provided arrangements.", "formula":""},
        {"check_id":"CL-01", "subject":"Material and member-specific environment traceability", "source_locator":"§2.2.4.5, Table 2.2-3, and Table 2.4-9", "observed_value":"C30 is stated; class-II 0.30 mm and class-III 0.25 mm crack provisions are stated; member assignments are absent", "expected_or_limit":"the selected limit must be bound to the member environment", "derived_value":"general limits present but member mapping absent", "status":"REVIEW", "finding":"General material and exposure provisions are traceable, but they do not assign each reviewed member to an exposure class.", "formula":""},
        {"check_id":"AP-01", "subject":"Overall structural approval disposition", "source_locator":"§2.4.1, Tables 2.4-4 through 2.4-14", "observed_value":"reported comparisons close, but multiple calculation-chain and applicability inputs remain unresolved", "expected_or_limit":"approval cannot close while binding reproducibility issues remain", "derived_value":"approval blockers open", "status":"REVIEW", "finding":"Retain the overall approval disposition at REVIEW until the linked calculation-chain blockers are closed.", "formula":""},
        {"check_id":"AP-02", "subject":"Edge-pier stability calculation reproducibility", "source_locator":"§2.4.1, Table 2.4-4", "observed_value":"reported Kc includes 1.42 against 1.08; resisting and driving components and combination coefficients are absent", "expected_or_limit":"reported comparison and independent factor reproduction are separate approval layers", "derived_value":"factor input chain absent", "status":"REVIEW", "finding":"The displayed comparison passes, but the supplied report does not expose the inputs needed to reproduce the factor.", "formula":""},
        {"check_id":"AP-03", "subject":"Central-pier stability calculation reproducibility", "source_locator":"§2.4.1, Table 2.4-6", "observed_value":"reported Kc includes 2.03 against 1.08; resisting and driving components and combination coefficients are absent", "expected_or_limit":"reported comparison and independent factor reproduction are separate approval layers", "derived_value":"factor input chain absent", "status":"REVIEW", "finding":"The displayed comparisons do not provide an independently reproducible stability calculation.", "formula":""},
        {"check_id":"AP-04", "subject":"Left retaining-wall stability calculation reproducibility", "source_locator":"§2.4.1, Table 2.4-10", "observed_value":"reported sliding factor includes 1.34 against 1.08; underlying action and resistance components are absent", "expected_or_limit":"reported comparison and independent factor reproduction are separate approval layers", "derived_value":"factor input chain absent", "status":"REVIEW", "finding":"The reported factor-to-allowance comparison closes, but the calculation chain cannot be reproduced.", "formula":""},
        {"check_id":"AP-05", "subject":"Right retaining-wall stability calculation reproducibility", "source_locator":"§2.4.1, Table 2.4-11", "observed_value":"reported sliding factor includes 2.16 against 1.08; underlying action and resistance components are absent", "expected_or_limit":"reported comparison and independent factor reproduction are separate approval layers", "derived_value":"factor input chain absent", "status":"REVIEW", "finding":"The reported factor-to-allowance comparison closes, but the calculation chain cannot be reproduced.", "formula":""},
        {"check_id":"AP-06", "subject":"Spillway stability calculation reproducibility", "source_locator":"§2.4.1, Table 2.4-14", "observed_value":"reported Kc includes 3.01 against 1.05; completed-case factor is a dash; underlying factor inputs are absent", "expected_or_limit":"reported comparison, dash applicability, and independent reproduction must close separately", "derived_value":"factor input and scope chain absent", "status":"REVIEW", "finding":"Neither the completed-case dash nor the numerical factor chain is sufficiently supported for approval closure.", "formula":""},
        {"check_id":"AP-07", "subject":"Member-specific serviceability approval chain", "source_locator":"§2.2.4.5 and Table 2.4-9", "observed_value":"0.30 mm and 0.25 mm limits are stated, but Table 2.4-9 does not identify each member exposure class", "expected_or_limit":"member classification must govern the selected crack-width limit", "derived_value":"member-to-limit relation absent", "status":"REVIEW", "finding":"Do not promote the favorable crack comparisons to final approval until member exposure assignments are documented.", "formula":""},
        {"check_id":"AP-08", "subject":"Favorable stability narrative versus unresolved evidence", "source_locator":"§2.4.1 narrative and Tables 2.4-4, 2.4-6, and 2.4-14", "observed_value":"the narrative states stability is satisfied while factor inputs are absent and completed-case entries include dashes", "expected_or_limit":"a summary conclusion cannot override open row-level applicability or reproducibility", "derived_value":"summary and evidence chain do not close", "status":"REVIEW", "finding":"The favorable narrative is insufficient to close the unresolved scope and reproducibility findings.", "formula":""},
        {"check_id":"AP-09", "subject":"Approval blocker dependency closure", "source_locator":"§2.4.1, Tables 2.4-4 through 2.4-14, and §2.2.4.5", "observed_value":"open items affect stability reproduction, member exposure, reinforcement demand/provided matching, and anti-uplift approval", "expected_or_limit":"each blocker must identify its affected check and missing closure evidence", "derived_value":"linked issue register required", "status":"REVIEW", "finding":"Issue closure requires factor inputs, member exposure assignments, matching provided/demand reinforcement evidence, and an anti-uplift criterion before approval.", "formula":""},
    ]


def write_book(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Review"
    headers = ["check_id", "subject", "source_locator", "observed_value", "expected_or_limit", "derived_value", "status", "finding", "formula"]
    ws.append(headers)
    for row in rows():
        ws.append([row[h] for h in headers])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        row[6].font = Font(bold=True, color="006100") if row[6].value == "PASS" else Font(bold=True, color="9C0006")
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    widths = [12, 32, 34, 56, 42, 28, 12, 72, 34]
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.sheet_view.showGridLines = False

    readme = wb.create_sheet("Readme")
    readme.append(["Structural calculation review workbook"])
    readme.append(["Status meanings", "PASS = supplied values and governing limit close; FAIL = a supplied value violates the limit; REVIEW = a binding input or scope basis is absent."])
    readme.append(["Units", "Forces kN, moments kN·m, stresses kPa, steel areas mm² (or mm²/m), crack widths and deflections mm."])
    readme.append(["Evidence", "Each Review row names a source location in the supplied report. Formula cells are mechanical intermediates; the status is the reviewer's conclusion."])
    readme.column_dimensions["A"].width = 26
    readme.column_dimensions["B"].width = 120
    for row in readme.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    readme["A1"].font = Font(bold=True, size=14)
    wb.save(path)


if __name__ == "__main__":
    report_text()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_book(OUT)

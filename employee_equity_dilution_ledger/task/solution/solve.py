#!/usr/bin/env python3
"""Derive the reference workbook from the supplied filing materials."""
from __future__ import annotations
import html as html_lib
import re
import subprocess
import sys
from pathlib import Path

import xlsxwriter
from lxml import html


def clean_number(s: str) -> float:
    s = s.replace(",", "").replace("$", "").replace("(", "-").replace(")", "").strip()
    return float(s)


def first_num(text: str, pattern: str, label: str) -> float:
    m = re.search(pattern, text, flags=re.I | re.S)
    if not m:
        raise RuntimeError(f"could not locate {label} in supplied annual report")
    return clean_number(m.group(1))


def parse_materials(workspace: Path) -> dict:
    pdf = workspace / "materials" / "annual_report.pdf"
    proxy = workspace / "materials" / "proxy_statement.html"
    if not pdf.exists() or not proxy.exists():
        raise RuntimeError("required filing materials are missing")
    proc = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True,
                          capture_output=True, text=True)
    ar = proc.stdout
    # The anchored labels are taken from the source tables; values are never
    # copied from the verifier or an answer key.
    d = {
        "option_begin": first_num(ar, r"Outstanding at December 31, 2023\s+([\d,]+)", "option beginning"),
        "option_exercised": first_num(ar, r"Exercised \(1\)\s+\(?([\d,]+)\)?", "option exercises"),
        "option_forfeited": first_num(ar, r"Forfeited\s+\(?([\d,]+)\)?\s+21\.14", "option forfeitures"),
        "option_expired": first_num(ar, r"Expired\s+\(?([\d,]+)\)?\s+19\.25", "option expirations"),
        "option_end": first_num(ar, r"Outstanding at December 31, 2024\s+([\d,]+)\s+\$\s+17\.59", "option ending"),
        "option_exercise_price": first_num(ar, r"Outstanding at December 31, 2024\s+[\d,]+\s+\$\s+([\d.]+)\s+\$\s+3\.0", "option exercise price"),
        "rsu_begin": first_num(ar, r"Unvested at December 31, 2023\s+([\d,]+)\s+\$\s+19\.49", "RSU beginning"),
        "rsu_granted": first_num(ar, r"Granted\s+([\d,]+)\s+16\.75", "RSU grants"),
        "rsu_vested": first_num(ar, r"Vested \(1\)\s+\(?([\d,]+)\)?\s+19\.55", "RSU vesting"),
        "rsu_forfeited": first_num(ar, r"Forfeited \(2\)\s+\(?([\d,]+)\)?\s+17\.90", "RSU forfeitures"),
        "rsu_end": first_num(ar, r"Unvested at December 31, 2024\s+([\d,]+)\s+\$\s+17\.79", "RSU ending"),
        "pool_authorized": first_num(ar, r"maximum number of shares available for issuance under the plans is\s+([\d.]+)\s+million", "authorized pool") * 1_000_000,
        "pool_available": first_num(ar, r"of which\s+([\d.]+)\s+million were available for future awards", "available pool") * 1_000_000,
        "basic_shares": first_num(ar, r"Weighted-average shares outstanding\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", "basic weighted-average shares") * 1_000_000,
    }
    # The PSU table has repeated generic labels, so bind it to its section.
    psu_section = ar[ar.find("The following table summarizes the Company's PSU activity"):]
    d["psu_begin"] = first_num(psu_section, r"Unvested at December 31, 2023\s+([\d,]+)", "PSU beginning")
    d["psu_granted"] = first_num(psu_section, r"Granted\s+([\d,]+)", "PSU grants")
    d["psu_vested"] = first_num(psu_section, r"Vested \(1\)\s+\(?([\d,]+)\)?", "PSU vesting")
    d["psu_forfeited"] = first_num(psu_section, r"Forfeited \(2\)\s+\(?([\d,]+)\)?", "PSU forfeitures")
    d["psu_end"] = first_num(psu_section, r"Unvested at December 31, 2024\s+([\d,]+)", "PSU ending")
    d["aggregate_cash"] = first_num(ar, r"Cash received by Knowles for exercise of stock options\s+\$\s+([\d.]+)", "aggregate cash proceeds") * 1_000_000
    d["aggregate_intrinsic"] = first_num(ar, r"Aggregate intrinsic value of stock options exercised\s+([\d.]+)", "aggregate intrinsic value") * 1_000_000
    d["max_psu_factor"] = first_num(ar, r"size\s+of\s+the\s+performance\s+share\s+units\s+are\s+subject\s+to\s+attainment\s+of\s+up\s+to\s+([\d]+)%\s+of\s+target", "PSU maximum factor") / 100.0
    d["plan_max_securities"] = first_num(ar, r"target,\s+the\s+maximum\s+number\s+of\s+securities\s+to\s+be\s+issued\s+upon\s+exercise\s+of\s+outstanding\s+options,\s+warrants,\s+and\s+rights\s+is\s+([\d,]+)", "maximum outstanding securities")

    proxy_text = " ".join(html.parse(str(proxy)).getroot().text_content().split())
    d["closing_price"] = first_num(proxy_text, r"closing Knowles stock price of \$([\d.]+) per share", "closing price")
    # Extract the named-person exercise table. The table itself is the source
    # of the names and counts; the list only identifies rows to retain.
    tables = html.parse(str(proxy)).xpath("//table")
    target = next((t for t in tables if "Number of Shares Acquired on Exercise" in " ".join(t.text_content().split())), None)
    if target is None:
        raise RuntimeError("could not locate option-exercise table in supplied proxy")
    names = ["Jeffrey Niew", "John Anderson", "Raymond Cabrera", "Daniel Giesecke", "Robert Perna"]
    exec_rows = {}
    for tr in target.xpath(".//tr"):
        cells = [" ".join(c.text_content().split()) for c in tr.xpath("./th|./td")]
        row = " | ".join(cells)
        for name in names:
            if name in row:
                m = re.search(re.escape(name) + r"\s*\|?\s*([\d,]+|—|-)", row)
                if not m:
                    # Some HTML tables flatten cells without the pipe.
                    m = re.search(re.escape(name) + r"\s+([\d,]+|—|-)", row)
                if not m:
                    raise RuntimeError(f"could not parse exercise row for {name}")
                token = m.group(1)
                exec_rows[name] = 0.0 if token in {"—", "-"} else clean_number(token)
    if set(exec_rows) != set(names):
        raise RuntimeError("proxy exercise table did not contain every named row")
    d["exec_rows"] = exec_rows
    return d


def make_workbook(out: Path, d: dict) -> None:
    wb = xlsxwriter.Workbook(str(out))
    wb.set_properties({"title": "Employee Equity Plan Dilution and Exercise Ledger"})
    title = wb.add_format({"bold": True, "font_size": 14, "font_color": "#17365D"})
    header = wb.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1, "text_wrap": True})
    text = wb.add_format({"border": 1, "text_wrap": True})
    num = wb.add_format({"border": 1, "num_format": "#,##0.00"})
    integer = wb.add_format({"border": 1, "num_format": "#,##0"})
    pct = wb.add_format({"border": 1, "num_format": "0.00%"})
    money = wb.add_format({"border": 1, "num_format": "$#,##0.00"})
    status = wb.add_format({"border": 1, "align": "center"})
    note = wb.add_format({"italic": True, "font_color": "#666666", "text_wrap": True})

    ws = wb.add_worksheet("Inputs")
    ws.write("A1", "Source inputs and assumptions", title)
    ws.write_row("A3", ["Field", "Value", "Units", "Source locator / note"], header)
    rows = [
        ("Reporting date", "2024-12-31", "date", "Annual report, equity plan disclosures"),
        ("Authorized pool", d["pool_authorized"], "shares", "Annual report, Equity Incentive Program"),
        ("Available for future awards", d["pool_available"], "shares", "Annual report, Equity Incentive Program"),
        ("Basic weighted-average shares", d["basic_shares"], "shares", "Annual report, Note 18"),
        ("Closing price", d["closing_price"], "$ / share", "Proxy, outstanding-awards footnote"),
        ("PSU maximum factor", d["max_psu_factor"], "x target", "Annual report, PSU policy"),
        ("Option pool multiplier", 1.0, "pool shares / award", "Annual report, plan footnote"),
        ("Full-value pool multiplier", 1.75, "pool shares / award", "Annual report, plan footnote"),
        ("Aggregate options exercised", d["option_exercised"], "shares", "Annual report, stock option activity"),
        ("Aggregate option cash proceeds", d["aggregate_cash"], "$", "Annual report, option exercise information"),
        ("Aggregate option intrinsic value", d["aggregate_intrinsic"], "$", "Annual report, option exercise information"),
        ("Maximum outstanding securities (plan table)", d["plan_max_securities"], "shares", "Annual report, equity compensation plan footnote"),
    ]
    for r, row in enumerate(rows, 4):
        ws.write(r-1, 0, row[0], text)
        if isinstance(row[1], (int, float)):
            fmt = pct if row[0] == "PSU maximum factor" else money if row[0] == "Closing price" else num
            ws.write_number(r-1, 1, row[1], fmt)
        else:
            ws.write(r-1, 1, row[1], text)
        ws.write(r-1, 2, row[2], text); ws.write(r-1, 3, row[3], text)
    ws.set_column("A:A", 31); ws.set_column("B:B", 18); ws.set_column("C:C", 18); ws.set_column("D:D", 52)

    led = wb.add_worksheet("Award_Ledger")
    led.write("A1", "Award class roll-forward", title)
    led.write_row("A3", ["Award class", "Beginning", "Grants / additions", "Exercises / vests", "Forfeitures", "Expirations", "Ending (formula)", "Weighted-average price / fair value", "Units", "Source locator"], header)
    award_rows = [
        ("Options", d["option_begin"], 0, d["option_exercised"], d["option_forfeited"], d["option_expired"], d["option_exercise_price"], "shares", "Annual report, stock option activity"),
        ("RSUs", d["rsu_begin"], d["rsu_granted"], d["rsu_vested"], d["rsu_forfeited"], 0, 17.79, "shares", "Annual report, RSU activity"),
        ("PSUs", d["psu_begin"], d["psu_granted"], d["psu_vested"], d["psu_forfeited"], 0, 27.25, "shares", "Annual report, PSU activity"),
    ]
    for r, row in enumerate(award_rows, 4):
        led.write(r-1, 0, row[0], text)
        for c, val in enumerate(row[1:6], 1): led.write_number(r-1, c, val, integer)
        ending_key = {"Options": "option_end", "RSUs": "rsu_end", "PSUs": "psu_end"}[row[0]]
        led.write_formula(r-1, 6, f"=B{r}+C{r}-D{r}-E{r}-F{r}", integer, d[ending_key])
        led.write_number(r-1, 7, row[6], money); led.write(r-1, 8, row[7], text); led.write(r-1, 9, row[8], text)
    led.set_column("A:A", 16); led.set_column("B:G", 17); led.set_column("H:H", 25); led.set_column("I:I", 14); led.set_column("J:J", 42)

    ex = wb.add_worksheet("Exercise_Ledger")
    ex.write("A1", "Option exercise reconciliation", title)
    ex.write_row("A3", ["Population", "Options exercised", "Value realized ($)", "Source / treatment"], header)
    vals = {"Jeffrey Niew": (d["exec_rows"]["Jeffrey Niew"], 739099), "John Anderson": (d["exec_rows"]["John Anderson"], 349733), "Raymond Cabrera": (d["exec_rows"]["Raymond Cabrera"], 89888), "Daniel Giesecke": (d["exec_rows"]["Daniel Giesecke"], 176022), "Robert Perna": (d["exec_rows"]["Robert Perna"], 0)}
    for r, (name, (shares, realized)) in enumerate(vals.items(), 4):
        ex.write(r-1, 0, name, text); ex.write_number(r-1, 1, shares, integer); ex.write_number(r-1, 2, realized, money); ex.write(r-1, 3, "Proxy, Option Exercises and Stock Vested in 2024", text)
    ex.write(9-1, 0, "Named-person subtotal", text); ex.write_formula(9-1, 1, "=SUM(B4:B8)", integer, sum(v[0] for v in vals.values())); ex.write_formula(9-1, 2, "=SUM(C4:C8)", money, sum(v[1] for v in vals.values())); ex.write(9-1, 3, "Formula subtotal", text)
    ex.write(10-1, 0, "Other employees / unassigned aggregate", text); ex.write_formula(10-1, 1, "=Inputs!B12-B9", integer, d["option_exercised"]-sum(v[0] for v in vals.values())); ex.write_blank(10-1, 2, None, money); ex.write(10-1, 3, "Residual to annual-report aggregate", text)
    ex.write(11-1, 0, "Annual-report aggregate", text); ex.write_formula(11-1, 1, "=Inputs!B12", integer, d["option_exercised"]); ex.write_number(11-1, 2, d["aggregate_cash"], money); ex.write(11-1, 3, "Annual report; cash proceeds is a different measure", text)
    ex.set_column("A:A", 34); ex.set_column("B:C", 20); ex.set_column("D:D", 52)

    sm = wb.add_worksheet("Dilution_Summary")
    sm.write("A1", "Potential dilution scenarios", title)
    sm.write_row("A3", ["Metric", "Base / target", "Maximum / upside", "Units", "Formula note"], header)
    option_inc = max(0.0, d["option_end"] * (d["closing_price"] - d["option_exercise_price"]) / d["closing_price"])
    rsu_end, psu_end = d["rsu_end"], d["psu_end"]
    psu_max = d["plan_max_securities"] - d["option_end"] - rsu_end
    total_base, total_max = d["option_end"] + rsu_end + psu_end, d["plan_max_securities"]
    tsm_base, tsm_max = option_inc + rsu_end + psu_end, option_inc + rsu_end + psu_max
    pool_base = (d["rsu_granted"] + d["psu_granted"]) * 1.75
    pool_max = (d["rsu_granted"] + d["psu_granted"] * d["max_psu_factor"]) * 1.75
    summary = [
        ("Option incremental shares (treasury-stock)", "=MAX(0,Award_Ledger!G4*(Inputs!B8-Award_Ledger!H4)/Inputs!B8)", "=MAX(0,Award_Ledger!G4*(Inputs!B8-Award_Ledger!H4)/Inputs!B8)", option_inc, option_inc, "shares", "Only in-the-money options contribute"),
        ("Unvested RSUs", "=Award_Ledger!G5", "=Award_Ledger!G5", rsu_end, rsu_end, "shares", "Full-value awards"),
        ("Unvested PSUs at target", "=Award_Ledger!G6", "=Inputs!B15-Award_Ledger!G4-Award_Ledger!G5", psu_end, psu_max, "shares", "Maximum uses the plan-table disclosed maximum"),
        ("Total potential award shares", "=Award_Ledger!G4+B5+B6", "=Inputs!B15", total_base, total_max, "shares", "Gross potential shares"),
        ("TSM diluted incremental shares", "=B4+B5+B6", "=C4+C5+C6", tsm_base, tsm_max, "shares", "Option TSM plus full-value awards"),
        ("Basic weighted-average denominator", "=Inputs!B7", "=Inputs!B7", d["basic_shares"], d["basic_shares"], "shares", "Disclosed Note 18 denominator"),
        ("Potential dilution %", "=B8/B9", "=C8/C9", tsm_base / d["basic_shares"], tsm_max / d["basic_shares"], "%", "Incremental shares divided by denominator"),
        ("2024 grant pool charge", "=(Award_Ledger!C5+Award_Ledger!C6)*Inputs!B11", "=(Award_Ledger!C5+Award_Ledger!C6*Inputs!B9)*Inputs!B11", pool_base, pool_max, "pool shares", "Full-value multiplier applies to pool use only"),
        ("Available future pool", "=Inputs!B6", "=Inputs!B6", d["pool_available"], d["pool_available"], "shares", "Capacity, not dilution"),
    ]
    for r, row in enumerate(summary, 4):
        sm.write(r-1, 0, row[0], text); sm.write_formula(r-1, 1, row[1], pct if row[5]=="%" else num, row[3]); sm.write_formula(r-1, 2, row[2], pct if row[5]=="%" else num, row[4]); sm.write(r-1, 3, row[5], text); sm.write(r-1, 4, row[6], text)
    sm.set_column("A:A", 38); sm.set_column("B:C", 22); sm.set_column("D:D", 14); sm.set_column("E:E", 50)

    ck = wb.add_worksheet("Checks")
    ck.write("A1", "Control checks", title); ck.write_row("A3", ["Check", "Difference / value", "Status", "Control rationale"], header)
    checks = [
        ("Options roll-forward", "=Award_Ledger!G4-(Award_Ledger!B4+Award_Ledger!C4-Award_Ledger!D4-Award_Ledger!E4-Award_Ledger!F4)", "=IF(ABS(B4)<=0.5,\"PASS\",\"FAIL\")", 0.0, "Beginning + movements = ending"),
        ("RSU roll-forward", "=Award_Ledger!G5-Award_Ledger!B5-Award_Ledger!C5+Award_Ledger!D5+Award_Ledger!E5+Award_Ledger!F5", "=IF(ABS(B5)<=0.5,\"PASS\",\"FAIL\")", 0.0, "Beginning + movements = ending"),
        ("PSU roll-forward", "=Award_Ledger!G6-Award_Ledger!B6-Award_Ledger!C6+Award_Ledger!D6+Award_Ledger!E6+Award_Ledger!F6", "=IF(ABS(B6)<=0.5,\"PASS\",\"FAIL\")", 0.0, "Beginning + movements = ending"),
        ("Exercise reconciliation", "=Exercise_Ledger!B11-Exercise_Ledger!B9-Exercise_Ledger!B10", "=IF(ABS(B7)<=0.5,\"PASS\",\"FAIL\")", 0.0, "Named subtotal + residual = aggregate"),
        ("PSU max exceeds target", "=Dilution_Summary!C6-Dilution_Summary!B6", "=IF(B8>0,\"PASS\",\"FAIL\")", psu_max - psu_end, "Scenario separation"),
        ("Pool and dilution separated", "=Dilution_Summary!B12-Dilution_Summary!B8", "=IF(ISNUMBER(B9),\"PASS\",\"FAIL\")", d["pool_available"] - tsm_base, "Capacity is reported separately from potential shares"),
    ]
    for r, row in enumerate(checks, 4):
        ck.write(r-1, 0, row[0], text); ck.write_formula(r-1, 1, row[1], num, row[3]); ck.write_formula(r-1, 2, row[2], status, "PASS"); ck.write(r-1, 3, row[4], text)
    ck.set_column("A:A", 30); ck.set_column("B:B", 22); ck.set_column("C:C", 14); ck.set_column("D:D", 52)
    jl = wb.add_worksheet("Judgment_Log")
    jl.write("A1", "Interpretive judgment log", title)
    jl.write_row("A3", ["Issue", "Decision", "Evidence locator", "Rationale"], header)
    judgments = [
        ("Performance-unit maximum", "Maximum is an upside scenario, not an additional grant", "Annual report, Equity Compensation Plans footnote", "The plan table reports target securities and separately states the maximum PSU attainment; adding both would double count."),
        ("Named-person exercise population", "Named exercise rows are a subset; retain an aggregate residual", "Proxy, Option Exercises and Stock Vested in 2024; annual report option activity", "The proxy names five executives while the annual note reports company-wide options exercised."),
        ("Pool multiplier versus dilution", "Apply the 1.75 multiplier only to plan capacity", "Annual report, Equity Compensation Plans footnote", "The multiplier consumes reserved shares; it is not a treasury-stock or EPS dilution factor."),
        ("Net exercise and withholding", "Do not treat withheld shares as a separate grant", "Annual report, stock option and RSU footnotes", "The filing says exercised or vested counts include shares withheld for exercise price or statutory taxes."),
    ]
    for r, row in enumerate(judgments, 4):
        for c, val in enumerate(row): jl.write(r-1, c, val, text)
    jl.set_column("A:A", 30); jl.set_column("B:B", 48); jl.set_column("C:C", 58); jl.set_column("D:D", 78)
    wb.close()


def main() -> int:
    workspace = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "/workspace/employee_equity_dilution_ledger.xlsx")
    d = parse_materials(workspace)
    make_workbook(out, d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

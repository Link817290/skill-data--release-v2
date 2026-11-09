#!/usr/bin/env python3
"""The shortlist workbook: its layout, how to write it, and how to read it back.

The deliverable is an Excel workbook because that is what goes to an investment
committee. Scoring therefore has to survive the ways two analysts writing the
same answer will lay out the same workbook: a renamed sheet, a title row above
the header, reordered columns, a differently-worded column label.

The reader below follows the same defence the reference benchmarks use — resolve
sheets and columns through alias sets, search for the header row rather than
assuming row 1, and fall back on value shape when a label is unrecognisable. It
is shared by the oracle (which writes the gold workbook) and the validator (which
reads a submission), so the two can never drift apart.
"""

from __future__ import annotations

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation

# Sheet purpose -> the names a submission might reasonably use.
SHEET_ALIASES = {
    "screen": ("screen", "shortlist", "selection", "results", "screening", "verdicts", "summary"),
    "conventions": ("conventions", "assumptions", "calibration", "bars", "settings", "methodology"),
}

# Column purpose -> substrings that identify it, lower-cased and space-stripped.
COLUMN_ALIASES = {
    "company_id": ("companyid", "ticker", "code", "证券代码", "股票代码", "secucode", "symbol"),
    "status": ("status", "verdict", "call", "decision", "result", "conclusion", "结论", "判定"),
    "growth_2019": ("2019growth", "growth2019", "assetgrowth2019", "2019总资产增速", "totalassetgrowth2019"),
    "growth_2020": ("2020growth", "growth2020", "assetgrowth2020", "2020总资产增速", "totalassetgrowth2020"),
    "growth_2021": ("2021growth", "growth2021", "assetgrowth2021", "2021总资产增速", "totalassetgrowth2021"),
    "coverage_mean": ("coveragemean", "cashtodebt", "debtcoverage", "货币资金有息债务", "覆盖"),
    "efficiency_mean": ("efficiencymean", "revenuetofixedassets", "assetturnover", "投资效率", "固定资产周转"),
    "profit_quality_mean": ("profitqualitymean", "cfotonetprofit", "cashconversion", "盈利质量", "现金流净利润"),
}

SHEET_LAYOUT = {
    "Screen": ["company_id", "status", "growth_2019", "growth_2020", "growth_2021",
               "coverage_mean", "efficiency_mean", "profit_quality_mean"],
}
SHEET_KEY = {"Screen": "screen"}

HEADER_SCAN_ROWS = 12       # a title block above the header is normal
MIN_HEADER_MATCHES = 2      # a row must resolve at least this many known columns


def _flat(v) -> str:
    return "".join(str(v).split()).lower().replace("_", "").replace("-", "") if v is not None else ""


# 按内容认表所需的列：一张表能同时解析出这些列，它就是那张表，与叫什么名字无关。
SHEET_SIGNATURE = {
    "screen": ("company_id", "status"),
    "conventions": (),
}


def resolve_sheet(book, purpose: str):
    """Find the sheet serving `purpose`, by alias then by header content.

    别名表只收了几个拉丁词，一份叫「筛选结果」或「Committee list」的合规交付物
    会一个都命中不上，整份作答被判零分——测的就成了命名习惯而不是专业结论。
    别名认不出来时改按内容认：能解析出这张表该有的关键列，它就是那张表。
    """
    wanted = SHEET_ALIASES[purpose]
    for name in book.sheetnames:
        flat = _flat(name)
        if any(_flat(a) in flat or flat in _flat(a) for a in wanted):
            return book[name]

    signature = SHEET_SIGNATURE.get(purpose) or ()
    if not signature:
        return None
    best, best_score = None, 0
    for name in book.sheetnames:
        sheet = book[name]
        rows = [[cell.value for cell in row] for row in sheet.iter_rows()][:HEADER_SCAN_ROWS]
        _, found = resolve_columns(rows)
        if not all(column in found for column in signature):
            continue
        if len(found) > best_score:
            best, best_score = sheet, len(found)
    return best


def resolve_columns(rows, wanted=None) -> tuple[int, dict]:
    """Locate the header row and map column purpose -> column index.

    Scans the first HEADER_SCAN_ROWS rows instead of trusting row 1, because a
    workbook built for humans usually opens with a title and a blank line.

    `wanted` restricts resolution to the columns that sheet is supposed to carry.
    Without it the aliases collide across sheets -- "call" is a plausible name for
    a screen verdict *and* for the three-state treatment, and "year" appears in
    both the signed-profit year and the goodwill window years."""
    candidates = {p: a for p, a in COLUMN_ALIASES.items() if wanted is None or p in wanted}
    best = (None, {})
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        found = {}
        for position, cell in enumerate(row):
            flat = _flat(cell)
            if not flat:
                continue
            exact = next((p for p, aliases in candidates.items()
                          if p not in found and flat in {_flat(a) for a in aliases}), None)
            loose = next((p for p, aliases in candidates.items()
                          if p not in found and any(a in flat or flat in a for a in aliases)), None)
            purpose = exact or loose
            if purpose:
                found[purpose] = position
        if len(found) > len(best[1]):
            best = (index, found)
    return best if len(best[1]) >= MIN_HEADER_MATCHES else (None, {})


def read_table(path, purpose: str) -> list[dict]:
    """Every data row of one sheet, keyed by column purpose."""
    try:
        book = load_workbook(path, data_only=True, read_only=True)
    except Exception:
        return []
    sheet = resolve_sheet(book, purpose)
    if sheet is None:
        return []
    rows = [list(r) for r in sheet.iter_rows(values_only=True)]
    layout = next((c for name, c in SHEET_LAYOUT.items() if SHEET_KEY.get(name) == purpose), None)
    header_index, columns = resolve_columns(rows, layout)
    if header_index is None:
        return []
    out = []
    for row in rows[header_index + 1:]:
        record = {p: (row[i] if i < len(row) else None) for p, i in columns.items()}
        if any(v not in (None, "") for v in record.values()):
            out.append(record)
    return out


VERDICTS = ("PASS", "FAIL", "REVIEW")


def write_workbook(path, tables: dict, conventions: dict) -> None:
    """Write a workbook in the layout the template ships.

    The status column carries a validation list. Which verdicts exist is the
    schema of the deliverable, not a hint about how to reach them -- a template
    handed to an analyst says what may go in the cell and says nothing about
    when. Leaving it out made a third of the pool unreachable: nothing else in
    the task names REVIEW, so a screen would have been written as a binary."""
    book = Workbook()
    book.remove(book.active)
    for sheet_name, columns in SHEET_LAYOUT.items():
        sheet = book.create_sheet(sheet_name)
        sheet.append(columns)
        for record in tables.get(sheet_name, []):
            sheet.append([record.get(c) for c in columns])
        if "status" in columns:
            letter = chr(ord("A") + columns.index("status"))
            rule = DataValidation(type="list", formula1='"%s"' % ",".join(VERDICTS),
                                  allow_blank=True, showDropDown=False)
            rule.prompt = "One of: " + ", ".join(VERDICTS)
            rule.promptTitle = "Verdict"
            sheet.add_data_validation(rule)
            rule.add(f"{letter}2:{letter}{max(sheet.max_row, 2)}")
    sheet = book.create_sheet("Conventions")
    sheet.append(["item", "value"])
    for key, value in conventions.items():
        sheet.append([key, str(value)])
    book.save(path)

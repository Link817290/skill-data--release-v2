#!/usr/bin/env python3
"""Minimal XLSX reader/writer for the A-share regime-map workbook.

Standard library only, so the Harbor container needs no openpyxl at runtime. The reader
handles plain cells, shared strings, inlineStr, shifted title rows, renamed sheets,
reordered columns and Chinese headers. The Chinese terms in the lookup tables below are
matching aliases for Chinese-language answers and must not be translated away.
"""
from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

SHEET_ALIASES = {
    "regime_map": ("regime map", "regime_map", "results", "result", "summary", "map", "研判", "结果", "状态图", "regime"),
    "conventions": ("conventions", "assumptions", "notes", "说明", "约定", "方法"),
}

COLUMN_ALIASES = {
    "sample_id": ("sampleid", "sample_id", "id", "样本", "样本编号", "窗口", "编号"),
    "regime_label": ("regimelabel", "regime", "label", "状态", "市场状态", "信号噪声", "判定"),
    "action": ("action", "allocationaction", "response", "操作", "动作", "配置动作", "建议"),
    "evidence_ids": ("evidence", "evidenceids", "anchors", "evidenceanchors", "证据", "证据id", "锚点", "依据"),
    "contradiction_flag": ("contradiction", "contradictionflag", "conflict", "矛盾", "冲突"),
    "review_flag": ("review", "reviewflag", "needsreview", "复核", "审查", "需复核"),
    "rationale": ("rationale", "reason", "notes", "理由", "说明", "备注"),
}

SHEET_LAYOUT = {
    "Regime Map": ["sample_id", "regime_label", "action", "evidence_ids", "contradiction_flag", "review_flag", "rationale"],
}
SHEET_KEY = {"Regime Map": "regime_map"}
HEADER_SCAN_ROWS = 15
MIN_HEADER_MATCHES = 3
REGIME_ENUM = ("SIGNAL", "NOISE", "MIXED", "REVIEW")
ACTION_ENUM = ("ADD_RISK", "REDUCE_RISK", "HOLD", "ROTATE_STYLE", "ROTATE_INDUSTRY", "REVIEW_ONLY")
BOOL_ENUM = ("TRUE", "FALSE")


def _flat(v) -> str:
    return "".join(str(v).split()).lower().replace("_", "").replace("-", "") if v is not None else ""


def resolve_columns(rows, wanted=None):
    candidates = {p: a for p, a in COLUMN_ALIASES.items() if wanted is None or p in wanted}
    best = (None, {})
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        found = {}
        for pos, cell in enumerate(row):
            flat = _flat(cell)
            if not flat:
                continue
            exact = next((p for p, aliases in candidates.items() if p not in found and flat in {_flat(a) for a in aliases}), None)
            loose = next((p for p, aliases in candidates.items() if p not in found and any(_flat(a) in flat or flat in _flat(a) for a in aliases)), None)
            purpose = exact or loose
            if purpose:
                found[purpose] = pos
        if len(found) > len(best[1]):
            best = (index, found)
    return best if len(best[1]) >= MIN_HEADER_MATCHES else (None, {})


def _col_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref or "")
    if not letters:
        return 0
    n = 0
    for ch in letters.group(0):
        n = n * 26 + ord(ch) - ord("A") + 1
    return n - 1


def _col_name(index: int) -> str:
    index += 1
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(ord("A") + rem) + out
    return out


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    ns = {"m": NS_MAIN}
    strings = []
    for si in root.findall("m:si", ns):
        texts = [t.text or "" for t in si.findall(".//m:t", ns)]
        strings.append("".join(texts))
    return strings


def _workbook_sheets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall(f"{{{NS_PKG_REL}}}Relationship")}
    sheets = []
    for s in wb.findall(f".//{{{NS_MAIN}}}sheet"):
        name = s.attrib.get("name", "")
        rid = s.attrib.get(f"{{{NS_REL}}}id")
        target = relmap.get(rid, "")
        if target.startswith("/"):
            path = target.lstrip("/")
        elif target.startswith("xl/"):
            path = target
        else:
            path = "xl/" + target
        sheets.append((name, path))
    return sheets


def _read_sheet(zf: zipfile.ZipFile, path: str, shared: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(path))
    rows = []
    for row_el in root.findall(f".//{{{NS_MAIN}}}row"):
        cells = []
        for c in row_el.findall(f"{{{NS_MAIN}}}c"):
            idx = _col_index(c.attrib.get("r", ""))
            while len(cells) <= idx:
                cells.append("")
            t = c.attrib.get("t")
            value = ""
            if t == "inlineStr":
                texts = [x.text or "" for x in c.findall(f".//{{{NS_MAIN}}}t")]
                value = "".join(texts)
            else:
                v = c.find(f"{{{NS_MAIN}}}v")
                raw = v.text if v is not None else ""
                if t == "s" and raw != "":
                    try:
                        value = shared[int(raw)]
                    except Exception:
                        value = raw
                else:
                    value = raw or ""
            cells[idx] = value
        rows.append(cells)
    return rows


def read_table(path, purpose: str) -> list[dict]:
    try:
        with zipfile.ZipFile(path) as zf:
            shared = _read_shared_strings(zf)
            all_sheets = []
            for name, sheet_path in _workbook_sheets(zf):
                try:
                    rows = _read_sheet(zf, sheet_path, shared)
                except Exception:
                    continue
                all_sheets.append((name, rows))
    except Exception:
        return []

    wanted = SHEET_ALIASES[purpose]
    chosen = None
    for name, rows in all_sheets:
        flat = _flat(name)
        if any(_flat(a) in flat or flat in _flat(a) for a in wanted):
            chosen = rows
            break
    if chosen is None:
        best = (None, -1)
        layout = next((cols for name, cols in SHEET_LAYOUT.items() if SHEET_KEY.get(name) == purpose), None)
        for _, rows in all_sheets:
            _, cols = resolve_columns(rows, layout)
            if len(cols) > best[1]:
                best = (rows, len(cols))
        chosen = best[0] if best[1] >= MIN_HEADER_MATCHES else None
    if chosen is None:
        return []

    layout = next((cols for name, cols in SHEET_LAYOUT.items() if SHEET_KEY.get(name) == purpose), None)
    header_index, columns = resolve_columns(chosen, layout)
    if header_index is None:
        return []
    out = []
    for row in chosen[header_index + 1:]:
        rec = {p: (row[i] if i < len(row) else "") for p, i in columns.items()}
        if any(v not in (None, "") for v in rec.values()):
            out.append(rec)
    return out


def _sheet_xml(rows: list[list[str]]) -> str:
    parts = [f'<worksheet xmlns="{NS_MAIN}"><sheetData>']
    for r_idx, row in enumerate(rows, 1):
        parts.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row, 1):
            if value is None or value == "":
                continue
            ref = f"{_col_name(c_idx - 1)}{r_idx}"
            text = html.escape(str(value), quote=False)
            parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def write_workbook(path, rows: list[dict], conventions: dict | None = None, *, sheet_name: str = "Regime Map", columns: list[str] | None = None, title_rows: list[list[str]] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = columns or SHEET_LAYOUT["Regime Map"]
    data_rows = []
    if title_rows:
        data_rows.extend(title_rows)
    data_rows.append(columns)
    for rec in rows:
        data_rows.append([rec.get(c, "") for c in columns])

    conv_rows = [["item", "value"]]
    for key, value in (conventions or {}).items():
        conv_rows.append([key, str(value)])

    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}"><sheets>
<sheet name="{html.escape(sheet_name, quote=True)}" sheetId="1" r:id="rId1"/>
<sheet name="Conventions" sheetId="2" r:id="rId2"/>
</sheets></workbook>'''
    workbook_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{NS_PKG_REL}">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>'''
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", _sheet_xml(data_rows))
        zf.writestr("xl/worksheets/sheet2.xml", _sheet_xml(conv_rows))

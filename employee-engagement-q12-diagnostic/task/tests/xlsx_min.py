#!/usr/bin/env python3
"""Small dependency-free XLSX reader/writer used by the offline task."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
import math
import re

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": MAIN_NS, "r": REL_NS}
RNS = {"p": PKG_REL_NS}


def _column_index(ref: str) -> int:
    match = re.match(r"([A-Z]+)", ref or "")
    if not match:
        return 0
    value = 0
    for char in match.group(1):
        value = value * 26 + ord(char) - 64
    return value - 1


def _column_name(index: int) -> str:
    index += 1
    chars: list[str] = []
    while index:
        index, rem = divmod(index - 1, 26)
        chars.append(chr(65 + rem))
    return "".join(reversed(chars))


def list_sheets(path: str | Path) -> list[tuple[str, str]]:
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        return [(sheet.attrib["name"], sheet.attrib.get("state", "visible")) for sheet in workbook.find("a:sheets", NS)]


def read_sheet(path: str | Path, sheet_name: str) -> list[list[Any]]:
    """Read displayed/cached XLSX cell values without external packages."""
    with ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//a:t", NS)) for item in root.findall("a:si", NS)]

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {node.attrib["Id"]: node.attrib["Target"] for node in relationships.findall("p:Relationship", RNS)}
        sheet = next((node for node in workbook.find("a:sheets", NS) if node.attrib["name"] == sheet_name), None)
        if sheet is None:
            raise KeyError(f"sheet not found: {sheet_name}")
        rel_id = sheet.attrib[f"{{{REL_NS}}}id"]
        member = targets[rel_id].lstrip("/")
        if not member.startswith("xl/"):
            member = "xl/" + member
        worksheet = ET.fromstring(archive.read(member))

        rows: list[list[Any]] = []
        for row_node in worksheet.findall(".//a:sheetData/a:row", NS):
            row: list[Any] = []
            for cell in row_node.findall("a:c", NS):
                index = _column_index(cell.attrib.get("r", ""))
                while len(row) <= index:
                    row.append("")
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    value: Any = "".join(node.text or "" for node in cell.findall(".//a:t", NS))
                else:
                    value_node = cell.find("a:v", NS)
                    value = "" if value_node is None or value_node.text is None else value_node.text
                    if cell_type == "s" and value != "":
                        value = shared[int(value)]
                    elif cell_type == "b" and value != "":
                        value = value == "1"
                    elif cell_type in (None, "n") and value != "":
                        try:
                            number = float(value)
                            value = int(number) if number.is_integer() else number
                        except ValueError:
                            pass
                row[index] = value
            while row and row[-1] == "":
                row.pop()
            rows.append(row)
        return rows


def excel_serial_to_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(value))
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date: {value!r}")


def _cell_xml(ref: str, value: Any, style: int = 0) -> str:
    style_attr = f' s="{style}"' if style else ""
    if value is None or value == "":
        return f'<c r="{ref}"{style_attr}/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style_attr}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return f'<c r="{ref}"{style_attr}/>'
        return f'<c r="{ref}" t="n"{style_attr}><v>{value:.15g}</v></c>'
    text = str(value)
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t{preserve}>{escape(text)}</t></is></c>'


def _zip_write(archive: ZipFile, name: str, data: str) -> None:
    info = ZipInfo(name, date_time=(2026, 9, 4, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data.encode("utf-8"))


def write_xlsx(
    path: str | Path,
    sheets: Iterable[tuple[str, list[list[Any]]]],
    *,
    title: str = "Q12 analysis dataset",
    percent_columns: dict[str, set[int]] | None = None,
    decimal_columns: dict[str, set[int]] | None = None,
) -> None:
    """Write a standards-compliant, formula-free XLSX with cached numeric values."""
    sheet_list = list(sheets)
    if not sheet_list:
        raise ValueError("at least one sheet is required")
    if len({name for name, _ in sheet_list}) != len(sheet_list):
        raise ValueError("duplicate sheet names")
    percent_columns = percent_columns or {}
    decimal_columns = decimal_columns or {}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    content_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheet_list) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f'{content_overrides}</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        '</Relationships>'
    )
    sheet_nodes = "".join(
        f'<sheet name={quoteattr(name[:31])} sheetId="{i}" r:id="rId{i}"/>' for i, (name, _) in enumerate(sheet_list, 1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><workbookPr/>'
        f'<sheets>{sheet_nodes}</sheets><calcPr calcId="0" fullCalcOnLoad="1" forceFullCalc="1"/></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="{REL_NS}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheet_list) + 1)
        )
        + f'<Relationship Id="rId{len(sheet_list) + 1}" Type="{REL_NS}/styles" Target="styles.xml"/>'
        + '</Relationships>'
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{MAIN_NS}">'
        '<numFmts count="2"><numFmt numFmtId="164" formatCode="0.00%"/><numFmt numFmtId="165" formatCode="0.0000"/></numFmts>'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )
    timestamp = "2026-09-04T00:00:00Z"
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:creator>Dataset Maintainer</dc:creator><cp:lastModifiedBy>Dataset Maintainer</cp:lastModifiedBy>'
        f'<dc:title>{escape(title)}</dc:title><dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified></cp:coreProperties>'
    )
    app = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        '<Application>Offline Q12 Dataset Builder</Application><AppVersion>5.0</AppVersion></Properties>'
    )

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        _zip_write(archive, "[Content_Types].xml", content_types)
        _zip_write(archive, "_rels/.rels", root_rels)
        _zip_write(archive, "docProps/core.xml", core)
        _zip_write(archive, "docProps/app.xml", app)
        _zip_write(archive, "xl/workbook.xml", workbook)
        _zip_write(archive, "xl/_rels/workbook.xml.rels", workbook_rels)
        _zip_write(archive, "xl/styles.xml", styles)
        for sheet_index, (sheet_name, rows) in enumerate(sheet_list, 1):
            max_columns = max((len(row) for row in rows), default=1)
            max_rows = max(len(rows), 1)
            row_xml: list[str] = []
            pct = percent_columns.get(sheet_name, set())
            dec = decimal_columns.get(sheet_name, set())
            for row_index, row in enumerate(rows, 1):
                cells: list[str] = []
                for column_index, value in enumerate(row):
                    style = 1 if row_index == 1 else (2 if column_index in pct else (3 if column_index in dec else 0))
                    cells.append(_cell_xml(f"{_column_name(column_index)}{row_index}", value, style))
                row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
            widths = "".join(
                f'<col min="{i}" max="{i}" width="{42 if i == 1 else 18}" customWidth="1"/>' for i in range(1, max_columns + 1)
            )
            dimension = f"A1:{_column_name(max_columns - 1)}{max_rows}"
            worksheet = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<worksheet xmlns="{MAIN_NS}"><dimension ref="{dimension}"/>'
                '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
                f'<cols>{widths}</cols><sheetData>{"".join(row_xml)}</sheetData>'
                f'<autoFilter ref="{dimension}"/></worksheet>'
            )
            _zip_write(archive, f"xl/worksheets/sheet{sheet_index}.xml", worksheet)


def validate_xlsx(path: str | Path) -> list[str]:
    errors: list[str] = []
    try:
        with ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"CRC failure: {bad}")
            for member in archive.namelist():
                if member.endswith(('.xml', '.rels')):
                    try:
                        ET.fromstring(archive.read(member))
                    except ET.ParseError as exc:
                        errors.append(f"invalid XML {member}: {exc}")
        for name, _ in list_sheets(path):
            read_sheet(path, name)
    except Exception as exc:
        errors.append(str(exc))
    return errors

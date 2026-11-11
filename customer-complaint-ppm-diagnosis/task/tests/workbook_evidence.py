#!/usr/bin/env python3
"""Bounded XLSX evidence extraction and safe arithmetic; never executes macros."""

import ast
import json
import operator
import posixpath
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zipfile import BadZipFile, ZipFile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


class InvalidWorkbook(ValueError):
    pass


class Workbook:
    def __init__(self, path):
        self.sheets = {}
        self.parts = {}
        self._active = set()
        self._recalculating = False
        self.date1904 = False
        try:
            with ZipFile(path) as z:
                if sum(info.file_size for info in z.infolist()) > 64 * 1024 * 1024:
                    raise InvalidWorkbook("Workbook exceeds the 64 MiB evidence limit")
                if len(z.infolist()) != len(set(z.namelist())):
                    raise InvalidWorkbook("Duplicate XLSX archive members")
                if z.testzip() is not None:
                    raise InvalidWorkbook("Corrupt XLSX archive")
                strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    strings = ["".join(node.itertext()) for node in ET.fromstring(z.read("xl/sharedStrings.xml"))]
                formats = {0: "General", 1: "0", 2: "0.00", 9: "0%", 10: "0.00%",
                           14: "mm-dd-yy", 15: "d-mmm-yy", 16: "d-mmm", 17: "mmm-yy"}
                styles = [0]
                if "xl/styles.xml" in z.namelist():
                    style = ET.fromstring(z.read("xl/styles.xml"))
                    for fmt in style.findall("s:numFmts/s:numFmt", NS):
                        formats[int(fmt.get("numFmtId"))] = fmt.get("formatCode")
                    styles = [int(node.get("numFmtId", "0")) for node in style.findall("s:cellXfs/s:xf", NS)] or [0]
                rels = {node.get("Id"): node.get("Target") for node in
                        ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
                        if node.get("TargetMode") != "External"}
                workbook = ET.fromstring(z.read("xl/workbook.xml"))
                properties = workbook.find("s:workbookPr", NS)
                self.date1904 = properties is not None and properties.get("date1904") in {"1", "true"}
                for sheet in workbook.findall("s:sheets/s:sheet", NS):
                    target = rels[sheet.get(RID)]
                    target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
                    cells = {}
                    for cell in ET.fromstring(z.read(target)).findall(".//s:c", NS):
                        value_node = cell.find("s:v", NS)
                        value = value_node.text if value_node is not None else None
                        kind = cell.get("t", "n")
                        if kind == "s" and value is not None:
                            value = strings[int(value)]
                        elif kind == "inlineStr":
                            inline = cell.find("s:is", NS)
                            value = "".join(inline.itertext()) if inline is not None else ""
                        formula = cell.find("s:f", NS)
                        if value is not None or formula is not None:
                            if cell.get("r") in cells:
                                raise InvalidWorkbook("Duplicate worksheet cell")
                            cells[cell.get("r")] = {
                                "value": value, "type": kind,
                                "formula": formula.text if formula is not None else None,
                                "format": formats.get(styles[int(cell.get("s", "0"))], "General"),
                            }
                    rels_path = posixpath.join(posixpath.dirname(target), "_rels", posixpath.basename(target) + ".rels")
                    if rels_path in z.namelist():
                        for relation in ET.fromstring(z.read(rels_path)):
                            if relation.get("TargetMode") == "External" or not relation.get("Type", "").endswith("/comments"):
                                continue
                            comment_target = relation.get("Target")
                            comments_path = (comment_target.lstrip("/") if comment_target.startswith("/") else
                                             posixpath.normpath(posixpath.join(posixpath.dirname(target), comment_target)))
                            comments = ET.fromstring(z.read(comments_path))
                            for comment in comments.findall(".//s:comment", NS):
                                address = comment.get("ref", "").replace("$", "").upper()
                                if not re.fullmatch(r"[A-Z]+[1-9]\d*", address):
                                    raise InvalidWorkbook("Invalid comment cell reference")
                                record = cells.setdefault(address, {
                                    "value": None, "type": "n", "formula": None, "format": "General",
                                })
                                record["comment"] = "".join(comment.itertext())
                    if sheet.get("name") in self.sheets:
                        raise InvalidWorkbook("Duplicate worksheet name")
                    self.sheets[sheet.get("name")] = cells
                if not self.sheets:
                    raise InvalidWorkbook("Workbook has no worksheets")
                for name in z.namelist():
                    if name.startswith(("xl/charts/", "xl/drawings/", "xl/comments", "xl/threadedComments/")) and name.endswith(".xml"):
                        node = ET.fromstring(z.read(name))
                        self.parts["part:" + name] = {"text": " ".join(node.itertext()),
                                                      "xml": z.read(name).decode("utf-8")}
        except (BadZipFile, KeyError, IndexError, ET.ParseError, ValueError) as error:
            raise InvalidWorkbook(f"Cannot read workbook: {error}") from error

    def cell(self, location):
        if not isinstance(location, str):
            raise ValueError("Cell locator must be text")
        sheet, sep, address = location.rpartition("!")
        if not sep:
            raise ValueError(f"Not a cell locator: {location}")
        sheet = sheet.strip("'").replace("''", "'")
        if not re.fullmatch(r"\$?[A-Za-z]+\$?[1-9]\d*", address):
            raise ValueError(f"Invalid cell address: {location}")
        return sheet, address.replace("$", "").upper(), self.sheets[sheet][address.replace("$", "").upper()]

    def quote_exists(self, location, quote):
        if location.startswith("part:"):
            record = self.parts.get(location, {})
            text = record.get("text", "") + " " + record.get("xml", "")
        else:
            _, _, cell = self.cell(location)
            text = " ".join(str(cell.get(field) or "") for field in ("value", "formula", "comment"))
        return isinstance(quote, str) and bool(quote.strip()) and quote in text

    def numeric(self, location):
        sheet, address, cell = self.cell(location)
        if cell["type"] == "e":
            raise ValueError(f"Displayed spreadsheet error at {location}")
        value = cell["value"]
        if cell["formula"] and (value is None or self._recalculating):
            key = (sheet, address)
            if key in self._active:
                raise ValueError("Circular formula")
            self._active.add(key)
            try:
                if len(self._active) > 200:
                    raise ValueError("Formula recursion exceeds bound")
                return self.formula(sheet, cell["formula"])
            finally:
                self._active.remove(key)
        if value is None:
            raise ValueError(f"Empty numeric cell: {location}")
        text = str(value).strip().replace(",", "").replace("\u00d7", "x")
        if text.endswith("%"):
            return Decimal(text[:-1].strip()) / 100
        return Decimal(text.removesuffix("x").removesuffix("X").strip())

    def formula(self, sheet, text):
        if len(text) > 16384:
            raise ValueError("Formula length exceeds bound")
        text = text.lstrip("=").replace("$", "").replace("^", "**")
        text = re.sub(r"(?:'((?:[^']|'')+)'|([\w\u0080-\uffff]+))!([A-Za-z]+\d+):([A-Za-z]+\d+)",
                      lambda m: "RANGE(" + json.dumps((m[1] or m[2]).replace("''", "'")) + ", "
                      + json.dumps(m[3].upper()) + ", " + json.dumps(m[4].upper()) + ")", text)
        text = re.sub(r"(?:'((?:[^']|'')+)'|([\w\u0080-\uffff]+))!([A-Za-z]+\d+)",
                      lambda m: "CELL(" + json.dumps((m[1] or m[2]).replace("''", "'")) + ", "
                      + json.dumps(m[3].upper()) + ")", text)
        text = re.sub(r"\b([A-Z]+\d+):([A-Z]+\d+)\b", r'RANGE("\1", "\2")', text)
        # Quoted cell addresses are already range arguments and must not be rewritten.
        chunks = re.split(r'("[^"]*")', text)
        text = "".join(chunk if index % 2 else re.sub(r"\b([A-Za-z]+\d+)\b", r'CELL("\1")', chunk)
                       for index, chunk in enumerate(chunks))
        text = re.sub(r"(?<=\d)%", "/100", text)

        def column(name):
            value = 0
            for char in name:
                value = value * 26 + ord(char) - 64
            return value

        def letters(value):
            result = ""
            while value:
                value, remainder = divmod(value - 1, 26)
                result = chr(65 + remainder) + result
            return result

        def evaluate(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str)):
                return node.value if isinstance(node.value, str) else Decimal(str(node.value))
            if isinstance(node, ast.BinOp) and type(node.op) in {ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow}:
                left, right = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 100:
                    raise ValueError("Formula exponent exceeds bound")
                return {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                        ast.Div: operator.truediv, ast.Pow: operator.pow}[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
                return -evaluate(node.operand) if isinstance(node.op, ast.USub) else evaluate(node.operand)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                values = [evaluate(arg) for arg in node.args]
                name = node.func.id.upper()
                if name == "CELL" and len(values) == 1:
                    return self.numeric(f"{sheet}!{values[0]}")
                if name == "CELL" and len(values) == 2:
                    return self.numeric(f"{values[0]}!{values[1]}")
                if name == "RANGE" and len(values) in {2, 3}:
                    range_sheet = values[0] if len(values) == 3 else sheet
                    first, last = [re.fullmatch(r"([A-Z]+)(\d+)", value).groups() for value in values[-2:]]
                    size = (column(last[0]) - column(first[0]) + 1) * (int(last[1]) - int(first[1]) + 1)
                    if not 0 <= size <= 10000:
                        raise ValueError("Formula range exceeds bound")
                    return [self.numeric(f"{range_sheet}!{letters(col)}{row}")
                            if f"{letters(col)}{row}" in self.sheets[range_sheet] else Decimal(0)
                            for col in range(column(first[0]), column(last[0]) + 1)
                            for row in range(int(first[1]), int(last[1]) + 1)]
                if name == "SUM":
                    return sum((sum(value) if isinstance(value, list) else value for value in values), Decimal(0))
                if name == "ROUND" and len(values) == 2 and abs(values[1]) <= 20:
                    return values[0].quantize(Decimal(10) ** -int(values[1]), rounding=ROUND_HALF_UP)
            raise ValueError("Uncached formula needs evaluator-side recalculation")

        previous = self._recalculating
        self._recalculating = True
        try:
            return evaluate(ast.parse(text, mode="eval").body)
        finally:
            self._recalculating = previous

    def evidence(self):
        return {"worksheets": self.sheets, "other_parts": self.parts}


def source_facts(workbook):
    sheet = next(iter(workbook.sheets))
    number = lambda col, row: workbook.numeric(f"{sheet}!{col}{row}")
    months, products = [], {}
    for month, col in enumerate("CDEFGHIJ", 1):
        sales, complaints = number(col, 2), number(col, 3)
        row = {"month": month, "sales": str(sales), "complaints": str(complaints),
               "overall_ppm": str(complaints / sales * 1000000), "product_ppm": {}}
        for product, source_row in zip("ABCD", (5, 8, 11, 14)):
            ps, pc = number(col, source_row), number(col, source_row + 1)
            row["product_ppm"][product] = str(pc / ps * 1000000)
            totals = products.setdefault(product, {"sales": Decimal(0), "complaints": Decimal(0)})
            totals["sales"] += ps
            totals["complaints"] += pc
        months.append(row)
    total_sales = sum(Decimal(row["sales"]) for row in months)
    total_complaints = sum(Decimal(row["complaints"]) for row in months)
    overall = total_complaints / total_sales * 1000000
    for totals in products.values():
        totals["ppm"] = totals["complaints"] / totals["sales"] * 1000000
        totals["share"] = totals["complaints"] / total_complaints
        totals["relative"] = totals["ppm"] / overall
    return {"months": months, "products": {key: {k: str(v) for k, v in values.items()}
                                            for key, values in products.items()},
            "total_sales": str(total_sales), "total_complaints": str(total_complaints),
            "overall_ppm": str(overall)}

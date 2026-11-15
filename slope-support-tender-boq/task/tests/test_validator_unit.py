from pathlib import Path
import importlib.util
import json
import shutil
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile
from openpyxl import load_workbook


VALIDATOR = Path(__file__).with_name("validator.py")
SPEC = importlib.util.spec_from_file_location("validator", VALIDATOR)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)

GOLD = VALIDATOR.parents[1] / "solution" / "golden_output.xlsx"
TRUTH = VALIDATOR.with_name("ground_truth.json")
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def rewrite_cell(source: Path, destination: Path, reference: str, value: str, *, formula: bool = False) -> None:
    with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(destination, "w") as outgoing:
        for info in incoming.infolist():
            data = incoming.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(data)
                cell = root.find(f".//{{{MAIN_NS}}}c[@r='{reference}']")
                if cell is None:
                    row_number = "".join(ch for ch in reference if ch.isdigit())
                    row = root.find(f".//{{{MAIN_NS}}}row[@r='{row_number}']")
                    assert row is not None
                    cell = ET.SubElement(row, f"{{{MAIN_NS}}}c", {"r": reference})
                cell.clear()
                cell.attrib["r"] = reference
                if formula:
                    ET.SubElement(cell, f"{{{MAIN_NS}}}f").text = value
                else:
                    cell.attrib["t"] = "inlineStr"
                    inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
                    ET.SubElement(inline, f"{{{MAIN_NS}}}t").text = value
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            outgoing.writestr(info, data)


def write_two_sheet_workbook(path: Path) -> None:
    headers = ["Sequence", "Item name", "Item characteristics", "Measurement rule", "Unit", "Quantity", "Pre-tax unit price", "Pre-tax total"]
    def row_xml(values: list[str]) -> str:
        cells = []
        for index, value in enumerate(values, 1):
            column = chr(64 + index)
            cells.append(f'<c r="{column}1" t="inlineStr"><is><t>{value}</t></is></c>')
        return '<row r="1">' + ''.join(cells) + '</row>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Cover" sheetId="1" r:id="rId1"/><sheet name="BOQ" sheetId="2" r:id="rId2"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", f'<?xml version="1.0"?><worksheet xmlns="{MAIN_NS}"><sheetData>{row_xml(["Cover page"])}</sheetData></worksheet>')
        archive.writestr("xl/worksheets/sheet2.xml", f'<?xml version="1.0"?><worksheet xmlns="{MAIN_NS}"><sheetData>{row_xml(headers)}</sheetData></worksheet>')


def write_single_sheet_rows(path: Path, rows: list[list[object]]) -> None:
    xml_rows = []
    for row_number, values in enumerate(rows, 1):
        cells = []
        for index, value in enumerate(values):
            reference = f"{chr(65 + index)}{row_number}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>')
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    worksheet = f'<?xml version="1.0"?><worksheet xmlns="{MAIN_NS}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="BOQ" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def write_section_sheets_from_truth(
    path: Path,
    *,
    reverse_sequences: bool = False,
    prefixed_sequences: bool = False,
) -> None:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    headers = [
        "施工段",
        "序号",
        "项目名称",
        "项目特征",
        "计量规则",
        "单位",
        "工程量",
        "除税单价",
        "除税合价",
        "证据引用",
        "工程量依据",
        "依据状态",
    ]

    def cell_xml(reference: str, value: object) -> str:
        if isinstance(value, (int, float)):
            return f'<c r="{reference}"><v>{value}</v></c>'
        if isinstance(value, str) and value.startswith("="):
            return f'<c r="{reference}"><f>{value[1:]}</f></c>'
        escaped = (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return f'<c r="{reference}" t="inlineStr"><is><t>{escaped}</t></is></c>'

    worksheets: list[tuple[str, bytes]] = []
    roman_prefixes = ("Ⅰ", "Ⅱ", "Ⅲ")
    for section_index, section in enumerate(truth["sections"]):
        rows: list[list[object]] = [headers]
        item_count = len(section["items"])
        for index, item in enumerate(section["items"], start=2):
            sequence = item_count - item["sequence"] + 1 if reverse_sequences else item["sequence"]
            if prefixed_sequences:
                sequence = f"{roman_prefixes[section_index]}-{sequence:02d}"
            rows.append([
                section["name"],
                sequence,
                item["name"],
                item["characteristics"],
                item["measurement_rule"],
                item["unit"],
                item["quantity"],
                "",
                f"=G{index}*H{index}",
                "基坑支护说明 剖面大样图.dwg / applicable support detail",
                f"Calculated design quantity = {item['quantity']} {item['unit']}",
                "calculated",
            ])
        xml_rows = []
        for row_number, values in enumerate(rows, start=1):
            cells = "".join(
                cell_xml(f"{chr(65 + column)}{row_number}", value)
                for column, value in enumerate(values)
            )
            xml_rows.append(f'<row r="{row_number}">{cells}</row>')
        worksheet = (
            f'<?xml version="1.0"?><worksheet xmlns="{MAIN_NS}"><sheetData>'
            f'{"".join(xml_rows)}</sheetData></worksheet>'
        ).encode("utf-8")
        worksheets.append((section["name"], worksheet))

    audit_headers = ["Record type", "Record ID", "Construction section", "Linked BOQ items", "Source or input", "Adopted value or issue", "Check or action", "Status"]
    audit_rows: list[list[object]] = [audit_headers]
    for index, section in enumerate(truth["sections"], 1):
        parameter_links = [1, 2, 3, 4]
        if reverse_sequences:
            parameter_links = [len(section["items"]) - value + 1 for value in parameter_links]
        audit_rows.append([
            "parameter", f"P-{index}", section["name"], ";".join(map(str, parameter_links)),
            "基坑支护说明 剖面大样图.dwg / pile detail",
            "Pile diameter = 1000 mm", "Propagate the diameter through linked quantities", "verified",
        ])
    audit_rows.append([
        "uncertainty", "U-1", "all", "*",
        "招标范围及方案版本分段说明.md / scope section list",
        "Revision boundary may affect quantities", "Keep affected quantities review-required", "review-required",
    ])
    closure_pairs = ((14, 24), (11, 20), (11, 20))
    for index, (section, pair) in enumerate(zip(truth["sections"], closure_pairs), 1):
        quantities = {
            item["sequence"]: item["quantity"]
            for item in section["items"]
        }
        left, right = quantities[pair[0]], quantities[pair[1]]
        linked_pair = pair
        if reverse_sequences:
            linked_pair = tuple(len(section["items"]) - value + 1 for value in pair)
        audit_rows.append([
            "closure", f"C-{index}", section["name"], f"{linked_pair[0]};{linked_pair[1]}",
            "BOQ linked quantities", f"Actual linked quantities: {left} m2 and {right} m2",
            f"Completed comparison: {left} - {right} = {abs(left - right)} m2; PASS", "verified",
        ])
    audit_xml_rows = []
    for row_number, values in enumerate(audit_rows, 1):
        cells = "".join(cell_xml(f"{chr(65 + column)}{row_number}", value) for column, value in enumerate(values))
        audit_xml_rows.append(f'<row r="{row_number}">{cells}</row>')
    audit_worksheet = f'<?xml version="1.0"?><worksheet xmlns="{MAIN_NS}"><sheetData>{"".join(audit_xml_rows)}</sheetData></worksheet>'.encode("utf-8")
    worksheets.append(("Audit register", audit_worksheet))

    sheet_nodes = []
    relationship_nodes = []
    content_nodes = []
    with zipfile.ZipFile(path, "w") as archive:
        for index, (name, worksheet) in enumerate(worksheets, start=1):
            sheet_nodes.append(f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>')
            relationship_nodes.append(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            )
            content_nodes.append(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", worksheet)
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(content_nodes)
            + "</Types>",
        )
        archive.writestr(
            "xl/workbook.xml",
            f'<?xml version="1.0"?><workbook xmlns="{MAIN_NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{"".join(sheet_nodes)}</sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(relationship_nodes)
            + "</Relationships>",
        )


def prepend_full_header_template(source: Path, destination: Path) -> None:
    headers = ["Sequence", "Item name", "Item characteristics", "Measurement rule", "Unit", "Quantity", "Pre-tax unit price", "Pre-tax total"]
    cells = "".join(f'<c r="{chr(65 + index)}1" t="inlineStr"><is><t>{value}</t></is></c>' for index, value in enumerate(headers))
    template = f'<?xml version="1.0"?><worksheet xmlns="{MAIN_NS}"><sheetData><row r="1">{cells}</row></sheetData></worksheet>'.encode()
    with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(destination, "w") as outgoing:
        for info in incoming.infolist():
            data = incoming.read(info.filename)
            if info.filename == "xl/workbook.xml":
                root = ET.fromstring(data)
                sheets = root.find(f"{{{MAIN_NS}}}sheets")
                assert sheets is not None
                template_sheet = ET.Element(f"{{{MAIN_NS}}}sheet", {"name": "Empty template", "sheetId": "99", "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id": "rId99"})
                sheets.insert(0, template_sheet)
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            elif info.filename == "xl/_rels/workbook.xml.rels":
                root = ET.fromstring(data)
                ET.SubElement(root, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship", {"Id": "rId99", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", "Target": "worksheets/template.xml"})
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            elif info.filename == "[Content_Types].xml":
                root = ET.fromstring(data)
                ET.SubElement(root, "{http://schemas.openxmlformats.org/package/2006/content-types}Override", {"PartName": "/xl/worksheets/template.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"})
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            outgoing.writestr(info, data)
        outgoing.writestr("xl/worksheets/template.xml", template)


class HeaderMatchingTests(unittest.TestCase):
    def test_natural_section_and_tax_exclusive_headers_are_recognized(self):
        rows = [[
            "施工段",
            "序号",
            "项目名称",
            "项目特征",
            "计量规则",
            "单位",
            "工程量",
            "除税单价",
            "除税合价",
        ]]

        _, mapping = validator.find_headers(rows)

        self.assertEqual(mapping["section"], 0)
        self.assertEqual(mapping["unit_price"], 7)
        self.assertEqual(mapping["total"], 8)

    def test_tax_before_and_evidence_location_headers_are_recognized(self):
        rows = [[
            "施工段", "序号", "项目名称", "项目特征", "计量规则", "单位", "工程量",
            "税前单价（元）", "税前合价（元）", "证据定位", "工程量依据", "依据状态",
        ]]

        _, mapping = validator.find_headers(rows)

        self.assertEqual(mapping["unit_price"], 7)
        self.assertEqual(mapping["total"], 8)
        self.assertEqual(mapping["evidence"], 9)

    def test_optional_explicit_section_header_is_recognized_without_becoming_scored_core(self):
        rows = [[
            "施工区段",
            "序号",
            "项目名称",
            "项目特征",
            "计量规则",
            "单位",
            "工程量",
            "不含税单价",
            "不含税合价",
        ]]

        _, mapping = validator.find_headers(rows)

        self.assertEqual(mapping["section"], 0)
        self.assertEqual(set(validator.PRICING_HEADERS), set(mapping) - {"section"})

    def test_overlapping_chinese_headers_choose_exact_quantity_column(self):
        rows = [[
            "序号",
            "项目名称",
            "项目特征",
            "工程量计算规则",
            "计量单位",
            "工程数量",
            "不含税综合单价",
            "不含税合价",
        ]]

        _, mapping = validator.find_headers(rows)

        self.assertEqual(mapping["rule"], 3)
        self.assertEqual(mapping["quantity"], 5)

    def test_workbook_rows_selects_boq_after_cover_sheet(self):
        with tempfile.TemporaryDirectory() as temporary:
            workbook = Path(temporary) / "two-sheets.xlsx"
            write_two_sheet_workbook(workbook)

            rows = validator.workbook_rows(workbook)
            _, mapping = validator.find_headers(rows)

            self.assertEqual(set(mapping), set(validator.PRICING_HEADERS))

    def test_populated_boq_wins_over_empty_fully_headed_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "template-before-boq.xlsx"
            prepend_full_header_template(GOLD, candidate)

            result = validator.score(candidate, TRUTH)

            self.assertEqual(result["rewards"]["strict"], 1.0)

    def test_section_per_sheet_layout_preserves_full_gold_score(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "section-per-sheet.xlsx"
            write_section_sheets_from_truth(candidate)

            result = validator.score(candidate, TRUTH)

        self.assertEqual(result["counts"]["candidate_item_rows"], 95)
        self.assertEqual(result["counts"]["recognized_sections"], 3)
        self.assertEqual(result["rewards"]["strict"], 1.0)
        self.assertEqual(result["rewards"]["lenient"], 1.0)

    def test_consolidated_audit_index_does_not_displace_section_boq_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "section-boqs-with-audit-index.xlsx"
            write_section_sheets_from_truth(candidate)
            book = load_workbook(candidate)
            index = book.create_sheet("审计关联索引", 0)
            index.append(["施工段", "序号", "项目名称", "证据定位"])
            truth = json.loads(TRUTH.read_text(encoding="utf-8"))
            for section in truth["sections"]:
                for repeat in range(5):
                    for item in section["items"]:
                        index.append([section["name"], item["sequence"], item["name"], "索引记录"])
            book.save(candidate)

            result = validator.score(candidate, TRUTH)

        self.assertEqual(result["counts"]["candidate_item_rows"], 95)
        self.assertEqual(result["counts"]["duplicate_keys"], 0)
        self.assertEqual(result["rewards"]["strict"], 1.0)
        self.assertEqual(result["rewards"]["lenient"], 1.0)

    def test_unique_sequence_renumbering_does_not_change_item_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "renumbered-section-sheets.xlsx"
            write_section_sheets_from_truth(candidate, reverse_sequences=True)

            result = validator.score(candidate, TRUTH)

        self.assertEqual(result["counts"]["matched_items"], 95)
        self.assertEqual(result["rewards"]["strict"], 1.0)
        self.assertEqual(result["rewards"]["lenient"], 1.0)

    def test_prefixed_sequences_remain_content_scoreable_but_unmodified_links_do_not_resolve(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "prefixed-section-sheets.xlsx"
            write_section_sheets_from_truth(candidate, prefixed_sequences=True)

            result = validator.score(candidate, TRUTH)

        self.assertEqual(result["counts"]["candidate_item_rows"], 95)
        self.assertEqual(result["counts"]["matched_items"], 95)
        self.assertEqual(result["counts"]["invalid_sequence_rows"], 95)
        self.assertEqual(result["counts"]["valid_control_records"], 1)
        self.assertGreater(result["rewards"]["strict"], 0.87)
        self.assertLess(result["rewards"]["strict"], 0.89)
        self.assertEqual(result["rewards"]["lenient"], 0.0)
        self.assertTrue(any("exact sequence-label audit links" in line for line in result["diagnostics"]))

    def test_prefixed_sequence_link_resolves_when_exact_token_is_preserved(self):
        candidate = {
            ("原方案一期", "invalid:i01"): {
                "raw_sequence": "Ⅰ-01",
            }
        }

        keys, declared, resolved = validator.linked_item_resolution(
            "Ⅰ-01", "原方案一期", candidate, [{"name": "原方案一期"}]
        )

        self.assertEqual(keys, {("原方案一期", "invalid:i01")})
        self.assertEqual((declared, resolved), (1, 1))

    def test_one_physical_column_cannot_satisfy_two_semantic_fields(self):
        rows = [["Sequence", "Item name", "Item characteristics", "Measurement rule quantity", "Unit", "Pre-tax unit price", "Pre-tax total"]]

        _, mapping = validator.find_headers(rows)

        self.assertEqual(len(set(mapping.values())), len(mapping))
        self.assertLess(len(mapping), len(validator.CORE_HEADERS))


class PricingReadinessTests(unittest.TestCase):
    def test_numeric_quantity_remains_parseable(self):
        self.assertEqual(validator.as_number(252.0), 252.0)

    def test_formula_quantity_uses_recalculated_cache_without_losing_formula_text(self):
        value = validator.FormulaValue("=Parameters!B2*2", 252.0)

        self.assertEqual(str(value), "=Parameters!B2*2")
        self.assertEqual(validator.as_number(value), 252.0)

    def test_filled_bidder_unit_price_lowers_pricing_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "filled-price.xlsx"
            rewrite_cell(GOLD, candidate, "G5", "123.45")

            result = validator.score(candidate, TRUTH)

            self.assertLess(result["group_points"]["pricing_readiness"], 1.0)

    def test_plain_text_total_is_not_calculation_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "text-total.xlsx"
            rewrite_cell(GOLD, candidate, "H5", "TBD")

            result = validator.score(candidate, TRUTH)

            self.assertLess(result["group_points"]["pricing_readiness"], 1.0)

    def test_unrelated_multiplication_formula_is_not_calculation_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "unrelated-formula.xlsx"
            rewrite_cell(GOLD, candidate, "H5", "A1*B1", formula=True)

            result = validator.score(candidate, TRUTH)

        self.assertAlmostEqual(result["group_points"]["pricing_readiness"], 1.0 - 0.4 / 95, places=6)

    def test_tax_exclusive_chinese_headers_preserve_gold_score(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "unit-price-header.xlsx"
            candidate = Path(temporary) / "tax-exclusive-headers.xlsx"
            rewrite_cell(GOLD, first, "G3", "除税单价")
            rewrite_cell(first, candidate, "H3", "除税合价")

            result = validator.score(candidate, TRUTH)

        self.assertEqual(result["rewards"]["strict"], 1.0)
        self.assertEqual(result["group_points"]["pricing_readiness"], 1.0)


class SectionBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        truth = json.loads(TRUTH.read_text(encoding="utf-8"))
        cls.sections = truth["sections"]
        cls.valid_section = cls.sections[0]["name"]
        cls.mapping = {"section": 0, "sequence": 1, "name": 2}

    def test_explicit_valid_section_is_used_for_item_key(self):
        rows = [["施工区段", "序号", "项目名称"], [self.valid_section, 1, "测试项目"]]

        items, duplicates, exact_repeats, _, item_rows = validator.parse_candidate(
            rows, 0, self.mapping, self.sections
        )

        self.assertIn((self.valid_section, 1), items)
        self.assertEqual(duplicates, [])
        self.assertEqual(exact_repeats, 0)
        self.assertEqual(item_rows, 1)

    def test_unrelated_explicit_discipline_does_not_receive_positional_fallback(self):
        rows = [["施工区段", "序号", "项目名称"], ["基坑监测工程", 1, "测试项目"]]

        items, _, _, _, _ = validator.parse_candidate(rows, 0, self.mapping, self.sections)

        self.assertNotIn((self.valid_section, 1), items)
        self.assertEqual({key[0] for key in items}, {"基坑监测工程"})

    def test_distinct_unresolved_sections_do_not_collapse_into_duplicate_keys(self):
        rows = [
            ["施工段", "序号", "项目名称"],
            ["第一施工段", 1, "项目一"],
            ["第二施工段", 1, "项目二"],
            ["第三施工段", 1, "项目三"],
        ]

        items, duplicates, exact_repeats, recognized, item_rows = validator.parse_candidate(
            rows, 0, self.mapping, self.sections
        )

        self.assertEqual(len(items), 3)
        self.assertEqual(duplicates, [])
        self.assertEqual(exact_repeats, 0)
        self.assertEqual(recognized, 0)
        self.assertEqual(item_rows, 3)

    def test_threefold_dump_with_distinct_nonblank_prices_gets_continuous_integrity_reduction(self):
        headers = ["施工段", "序号", "项目名称", "项目特征", "计量规则", "单位", "工程量", "除税单价", "除税合价"]
        rows = [headers]
        for index in range(285):
            sequence = index % 95 + 1
            rows.append([
                self.valid_section,
                sequence,
                f"项目{sequence}",
                "技术特征",
                "按实计量",
                "m",
                sequence,
                index + 1,
                "",
            ])
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "distinct-price-dump.xlsx"
            write_single_sheet_rows(candidate, rows)

            result = validator.score(candidate, TRUTH)

        self.assertEqual(result["counts"]["duplicate_keys"], 190)
        self.assertEqual(result["counts"]["exact_repeated_rows"], 190)
        self.assertAlmostEqual(result["integrity"]["factor"], 95 / (95 + 190), places=6)
        self.assertGreater(result["rewards"]["strict"], 0.0)
        self.assertLess(result["rewards"]["strict"], 0.35)
        self.assertEqual(result["rewards"]["lenient"], 0.0)

    def test_generic_and_ambiguous_section_fragments_are_not_mapped(self):
        self.assertEqual(validator.canonical_section("基坑支护", self.sections, None), "")
        self.assertEqual(validator.canonical_section("原方案", self.sections, None), "")

    def test_near_match_section_name_is_not_accepted_as_a_contract_boundary(self):
        exact = self.valid_section
        near_match = exact[:-1]

        self.assertEqual(validator.canonical_section(exact, self.sections, None), exact)
        self.assertEqual(validator.canonical_section(near_match, self.sections, None), "")

    def test_unrelated_standalone_heading_does_not_receive_positional_fallback(self):
        rows = [
            ["序号", "项目名称"],
            ["基坑监测工程", ""],
            [1, "测试项目"],
        ]
        mapping = {"sequence": 0, "name": 1}

        items, _, _, _, _ = validator.parse_candidate(rows, 0, mapping, self.sections)

        self.assertEqual({key[0] for key in items}, {"基坑监测工程"})

    def test_duplicate_explicit_section_sequence_is_reported(self):
        rows = [
            ["施工区段", "序号", "项目名称"],
            [self.valid_section, 1, "项目一"],
            [self.valid_section, 1, "项目二"],
        ]

        _, duplicates, exact_repeats, _, _ = validator.parse_candidate(rows, 0, self.mapping, self.sections)

        self.assertEqual(duplicates, [(self.valid_section, 1)])
        self.assertEqual(exact_repeats, 0)

    def test_identical_complete_row_is_counted_as_an_exact_repeat(self):
        rows = [
            ["施工段", "序号", "项目名称"],
            [self.valid_section, 1, "项目一"],
            [self.valid_section, 1, "项目一"],
        ]

        _, duplicates, exact_repeats, _, _ = validator.parse_candidate(
            rows, 0, self.mapping, self.sections
        )

        self.assertEqual(duplicates, [(self.valid_section, 1)])
        self.assertEqual(exact_repeats, 1)

    def test_constant_product_formula_is_not_calculation_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "constant-product.xlsx"
            rewrite_cell(GOLD, candidate, "H5", "PRODUCT(1,1)", formula=True)

            result = validator.score(candidate, TRUTH)

            self.assertAlmostEqual(result["group_points"]["pricing_readiness"], 1.0 - 0.4 / 95, places=6)

    def test_malformed_current_row_formula_is_not_calculation_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "malformed-formula.xlsx"
            rewrite_cell(GOLD, candidate, "H5", "F5*G5+", formula=True)

            result = validator.score(candidate, TRUTH)

            self.assertAlmostEqual(result["group_points"]["pricing_readiness"], 1.0 - 0.4 / 95, places=6)


class ResultContractTests(unittest.TestCase):
    def test_quantity_and_scope_are_the_largest_professional_components(self):
        self.assertEqual(validator.STRICT_WEIGHTS, {'coverage': 0.10, 'line_identity_and_unit': 0.05, 'technical_characteristics_and_rules': 0.10, 'quantity_accuracy': 0.25, 'pricing_readiness': 0.05, 'scope_completeness': 0.20, 'traceability': 0.10, 'control_ledger': 0.15})
        self.assertEqual(sum(validator.STRICT_WEIGHTS.values()), 1.0)

    def test_scope_row_requires_professional_content(self):
        complete = {
            "name": "成井",
            "characteristics": "井径及深度按设计",
            "rule": "按验收记录计量",
            "unit": "m",
        }

        self.assertTrue(validator.scope_line_usable(complete))
        for field in complete:
            with self.subTest(field=field):
                self.assertFalse(validator.scope_line_usable({**complete, field: ""}))

    def test_wrong_unit_blocks_quantity_credit(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "wrong-unit.xlsx"
            rewrite_cell(GOLD, candidate, "E5", "m3")

            result = validator.score(candidate, TRUTH)

        self.assertAlmostEqual(result["group_points"]["quantity_accuracy"], 1.0 - 1.0 / 95, places=6)

    def test_traceability_only_counts_professionally_matched_items(self):
        sources = ["计算书.docx"]
        complete = {
            "evidence": "计算书.docx / section 2",
            "quantity_basis": "10 × 2 m = 20 m",
            "basis_status": "calculated",
        }
        candidates = {("A", 1): complete, ("A", 2): complete}

        score, completed = validator.matched_traceability_score(candidates, {("A", 1)}, 2, sources)

        self.assertEqual(score, 0.5)
        self.assertEqual(completed, 1)

    def test_closure_requires_a_quantitative_comparison(self):
        items = [{"quantity": 2058.42, "unit": "m2"}, {"quantity": 2058.42, "unit": "m2"}]
        self.assertTrue(validator.closure_comparison_valid("2058.42 m2 compared with 2058.42 m2", "Difference = 0 m2", items))
        self.assertFalse(validator.closure_comparison_valid("Linked quantities", "Difference = 0", items))
        self.assertFalse(validator.closure_comparison_valid("Linked quantities", "Compare before issue"))

    def test_traceability_requires_source_locator_quantity_basis_and_state(self):
        sources = ["项目基坑支---计算书.docx", "基坑支护说明 剖面大样图.dwg"]
        complete = {
            "evidence": "项目基坑支---计算书.docx / section 4.2",
            "quantity_basis": "12 piles × 18.5 m = 222 m",
            "basis_status": "calculated",
        }
        missing_locator = {**complete, "evidence": "项目基坑支---计算书.docx"}

        self.assertEqual(validator.traceability_line_score(complete, sources), 1.0)
        self.assertLess(validator.traceability_line_score(missing_locator, sources), 1.0)

    def test_gold_scores_full_traceability_and_control_ledger(self):
        result = validator.score(GOLD, TRUTH)

        self.assertEqual(result["group_points"]["traceability"], 1.0)
        self.assertEqual(result["group_points"]["control_ledger"], 1.0)

    def test_identity_assignment_maximizes_coverage_before_similarity(self):
        gold = [{"name": f"g{index}", "unit": "m"} for index in range(6)]
        candidates = [{"name": f"c{index}", "unit": "m"} for index in range(6)]
        scores = {(f"c{index}", f"g{index}"): 0.35 for index in range(6)}
        scores.update({(f"c{index - 1}", f"g{index}"): 1.0 for index in range(1, 6)})

        with mock.patch.object(validator, "similarity", side_effect=lambda left, right: scores.get((left, right), 0.0)):
            pairs = validator.maximum_identity_pairs(gold, candidates)

        self.assertEqual(len(pairs), 6)

    def test_scope_completion_requires_all_sections_and_80_percent_of_expected_rows(self):
        expected = {"A": 41, "B": 26, "C": 28}
        self.assertAlmostEqual(validator.scope_completion_score({"A": 41, "B": 26, "C": 21}, expected), 0.9375)
        self.assertEqual(validator.scope_completion_score({"A": 33, "B": 21, "C": 23}, expected), 1.0)

    def test_scope_completion_cannot_be_reached_by_overfilling_other_sections(self):
        expected = {"A": 41, "B": 26, "C": 28}
        candidate = {"A": 70, "B": 24, "C": 16}

        self.assertEqual(sum(candidate.values()) >= 0.8 * sum(expected.values()), True)
        self.assertAlmostEqual(validator.scope_completion_score(candidate, expected), 16 / (28 * 0.80))
        self.assertLess(validator.scope_completion_score(candidate, expected), 1.0)

    def test_scope_completion_is_bounded_by_the_weakest_matched_section(self):
        expected = {"A": 38, "B": 29, "C": 28}

        score = validator.scope_completion_score({"A": 20, "B": 20, "C": 7}, expected)

        self.assertLess(score, 0.32)

    def test_full_section_plus_prefixed_sequence_link_is_accepted(self):
        section = "基坑支护-原方案一期部分"
        candidate = {(section, "invalid:i01"): {"raw_sequence": "Ⅰ-01"}}

        keys, declared, resolved = validator.linked_item_resolution(
            f"{section} Ⅰ-01", section, candidate, [{"name": section}]
        )

        self.assertEqual(keys, {(section, "invalid:i01")})
        self.assertEqual((declared, resolved), (1, 1))

    def test_lenient_completion_is_binary_and_requires_every_contract_milestone(self):
        self.assertEqual(validator.lenient_completion_score(1.0, 76, 3, 76, 95, 3), 1.0)
        self.assertEqual(validator.lenient_completion_score(0.99, 76, 3, 76, 95, 3), 0.0)
        self.assertEqual(validator.lenient_completion_score(1.0, 75, 3, 76, 95, 3), 0.0)
        self.assertEqual(validator.lenient_completion_score(1.0, 76, 2, 76, 95, 3), 0.0)
        self.assertEqual(validator.lenient_completion_score(1.0, 76, 3, 75, 95, 3), 0.0)
        self.assertEqual(validator.lenient_completion_score(1.0, 76, 3, 76, 95, 3, quantity_accuracy=0.79), 0.0)

    def test_success_result_declares_distinct_strict_and_lenient_formulas(self):
        result = validator.score(GOLD, TRUTH)

        formulas = result["reward_formulas"]
        self.assertTrue(formulas["strict"].strip())
        self.assertTrue(formulas["lenient"].strip())
        self.assertNotEqual(formulas["strict"], formulas["lenient"])

    def test_unreadable_result_still_declares_score_formulas(self):
        result = validator.score(Path("candidate-does-not-exist.xlsx"), TRUTH)

        formulas = result["reward_formulas"]
        self.assertTrue(formulas["strict"].strip())
        self.assertTrue(formulas["lenient"].strip())
        self.assertNotEqual(formulas["strict"], formulas["lenient"])


if __name__ == "__main__":
    unittest.main()

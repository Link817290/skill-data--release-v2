#!/usr/bin/env python3
from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL_NS = {"p": "http://schemas.openxmlformats.org/package/2006/relationships"}
HEADER_ALIASES = {
    "sequence": ("sequence", "seq", "序号", "编号"),
    "name": ("itemname", "item", "项目名称", "清单名称"),
    "characteristics": ("itemcharacteristics", "characteristics", "项目特征", "特征描述"),
    "rule": ("measurementrule", "measurementbasis", "计量规则", "工程量计算规则"),
    "unit": ("unit", "单位", "计量单位"),
    "quantity": ("quantity", "工程量", "工程数量", "数量"),
    "unit_price": ("pretaxunitprice", "unitprice", "不含税综合单价", "不含税单价", "除税综合单价", "除税单价", "税前综合单价", "税前单价"),
    "total": ("pretaxtotal", "extendedprice", "不含税合价", "不含税总价", "除税合价", "除税总价", "税前合价", "税前总价"),
    "evidence": ("evidencereference", "sourcereference", "evidence", "来源依据", "证据引用", "资料依据", "证据定位", "来源定位"),
    "quantity_basis": ("quantitybasis", "calculationbasis", "量基", "工程量依据", "工程量计算依据", "工程量计算式", "数量依据"),
    "basis_status": ("basisstatus", "evidencestatus", "依据状态", "量基状态", "状态"),
}
OPTIONAL_HEADER_ALIASES = {
    "section": (
        "constructionsection",
        "section",
        "施工段",
        "施工区段",
        "施工阶段",
        "施工分区",
        "分区",
        "分部",
        "标段",
    ),
}
CORE_HEADERS = tuple(HEADER_ALIASES)
PRICING_HEADERS = ("sequence", "name", "characteristics", "rule", "unit", "quantity", "unit_price", "total")
BOQ_DISCOVERY_HEADERS = ("sequence", "name", "characteristics", "rule", "unit", "quantity")
CONTROL_HEADER_ALIASES = {
    "record_type": ("recordtype", "type", "记录类型", "类型"),
    "record_id": ("recordid", "id", "记录编号", "编号"),
    "section": ("constructionsection", "section", "施工段", "适用施工段"),
    "linked_items": ("linkedboqitems", "linkeditems", "关联清单项", "关联项目"),
    "source": ("sourceorinput", "source", "来源或输入", "来源"),
    "value_issue": ("adoptedvalueorissue", "valueorissue", "采用值或问题", "参数值或问题"),
    # Chinese action headers combine several review verbs, action nouns, and
    # optional joiners. Enumerate the cross-product so ordinary wording does
    # not decide whether an otherwise complete control table is measurable.
    "action": tuple(
        ["checkoraction", "action"]
        + [verb + joiner + noun
           for verb in ("检查", "核查", "校核", "复核", "核对")
           for joiner in ("或", "与", "及", "/", "")
           for noun in ("行动", "处理", "处置", "动作", "措施", "处理动作", "处理措施", "处置措施")]
    ),
    "status": ("status", "状态"),
}
# Scope completeness and control integrity carry equal top weight. A tender list
# that omits work and a tender list nobody can audit fail the procurement in the
# same way: the first is priced short and claimed later, the second is priced on
# figures no reviewer can trace back to the design. Neither compensates for the
# other, so neither outranks the other.
#
# The remaining components are consequences of those two. Coverage and line
# identity describe how far the list got; traceability and technical
# characteristics describe how well an individual line holds up; quantity
# accuracy and pricing readiness are bounded mechanical checks that a correct
# list passes almost incidentally.
SCORER_VERSION = "slope-support-bench"

STRICT_WEIGHTS = {
    "coverage": 0.10,
    "line_identity_and_unit": 0.05,
    "technical_characteristics_and_rules": 0.10,
    "quantity_accuracy": 0.25,
    "pricing_readiness": 0.05,
    "scope_completeness": 0.20,
    "traceability": 0.10,
    "control_ledger": 0.15,
}
REWARD_FORMULAS = {
    "strict": "(0.10*coverage + 0.05*line_identity_and_unit + 0.10*technical_characteristics_and_rules + 0.25*quantity_accuracy + 0.05*pricing_readiness + 0.20*scope_completeness + 0.10*traceability + 0.15*control_ledger) * 95/(95+exact repeated selected-BOQ rows); control_ledger is 0.25*declared-link integrity + 0.25*parameter coverage + 0.15*material-uncertainty control + 0.35*quantitative-closure coverage",
    "lenient": "1 iff all required headers, each section at least 80% expected usable rows, at least 80% expected features, quantities and complete traceability, and full control-ledger contract; otherwise 0",
}


class FormulaValue(str):
    """Formula text with the recalculated cached value retained for measurement."""

    def __new__(cls, formula: str, cached: object = None):
        value = super().__new__(cls, formula)
        value.cached = cached
        return value


def strict_score(group_points: dict[str, float]) -> float:
    return sum(STRICT_WEIGHTS[name] * float(group_points[name]) for name in STRICT_WEIGHTS)


def scope_completion_score(candidate_section_rows: dict[str, int], expected_section_rows: dict[str, int]) -> float:
    """Score progress toward 80% professionally matched coverage in the weakest section."""
    if not expected_section_rows:
        return 0.0
    return min(
        1.0,
        min(
            candidate_section_rows.get(section, 0) / max(expected * 0.80, 1.0)
            for section, expected in expected_section_rows.items()
        ),
    )


def scope_line_usable(item: dict) -> bool:
    return (
        len(normalize(item.get("name"))) >= 2
        and bool(normalize(item.get("characteristics")))
        and bool(normalize(item.get("rule")))
        and bool(normalize(item.get("unit")))
    )


def lenient_completion_score(
    header_completeness: float,
    item_rows: int,
    recognized_sections: int,
    nonblank_characteristics: int,
    total: int,
    section_total: int,
    traceability_completion: float = 1.0,
    quantity_accuracy: float = 1.0,
    control_ledger: float = 1.0,
    scope_completeness: float | None = 1.0,
) -> float:
    """Public issuance contract: all columns, 80% in every section and complete controls."""
    return float(
        header_completeness >= 1.0 - 1e-9
        and item_rows >= total * 0.8
        and recognized_sections >= section_total
        and nonblank_characteristics >= total * 0.8
        and traceability_completion >= 0.8
        and quantity_accuracy >= 0.8
        and control_ledger >= 1.0 - 1e-9
        and scope_completeness is not None and scope_completeness >= 1.0 - 1e-9
    )


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(ch for ch in text if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def similarity(left: object, right: object) -> float:
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def source_reference_valid(value: object, sources: list[str]) -> bool:
    raw = str(value or "")
    normalized = normalize(raw)
    for source in sources:
        source_text = str(source)
        if normalize(source_text) not in normalized:
            continue
        remainder = raw.replace(source_text, " ")
        if re.search(r"(?:page|section|clause|detail|drawing|table|axis|页|章|节|条|图号|详图|剖面|表|轴|说明|§)\s*[\w.\-]*", remainder, re.IGNORECASE):
            return True
    return False


def canonical_basis_status(value: object) -> str:
    key = normalize(value)
    aliases = {
        "source-stated": ("sourcestated", "stated", "原文明确", "资料明确"),
        "calculated": ("calculated", "derived", "计算", "推导"),
        "provisional": ("provisional", "estimated", "暂估", "暂定"),
        "review-required": ("reviewrequired", "pendingreview", "待复核", "待确认"),
    }
    for canonical, values in aliases.items():
        if key in {normalize(item) for item in values}:
            return canonical
    return ""


def quantity_basis_valid(value: object) -> bool:
    raw = str(value or "").strip()
    normalized = normalize(raw)
    if len(normalized) < 6:
        return False
    return bool(
        re.search(r"\d", raw)
        or re.search(r"[=+×*÷/]", raw)
        or any(marker in normalized for marker in ("按图示", "按实", "暂估", "设计数量", "现场收方", "applicablesectiongeometry", "designquantity"))
    )


def traceability_line_score(item: dict, sources: list[str]) -> float:
    return (
        0.4 * float(source_reference_valid(item.get("evidence"), sources))
        + 0.4 * float(quantity_basis_valid(item.get("quantity_basis")))
        + 0.2 * float(bool(canonical_basis_status(item.get("basis_status"))))
    )


def matched_traceability_score(
    candidates: dict[tuple[str, int], dict],
    eligible_keys: set[tuple[str, int]],
    total: int,
    sources: list[str],
) -> tuple[float, int]:
    scores = [traceability_line_score(candidates[key], sources) for key in eligible_keys if key in candidates]
    return min(1.0, sum(scores) / max(total, 1)), sum(score == 1.0 for score in scores)


def column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    result = 0
    for char in letters.group(0):
        result = result * 26 + ord(char) - 64
    return result - 1


def _worksheet_rows(archive: zipfile.ZipFile, sheet_path: str, shared: list[str]) -> list[list[object]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows: list[list[object]] = []
    for row in root.findall(".//m:sheetData/m:row", NS):
        row_number = int(row.attrib.get("r", len(rows) + 1))
        while len(rows) < row_number - 1:
            rows.append([])
        values: dict[int, object] = {}
        for cell in row.findall("m:c", NS):
            index = column_number(cell.attrib.get("r", "A1"))
            kind = cell.attrib.get("t")
            formula = cell.find("m:f", NS)
            value_node = cell.find("m:v", NS)
            if formula is not None:
                cached: object = None
                if value_node is not None and value_node.text not in (None, ""):
                    raw_cached = value_node.text or ""
                    try:
                        cached = float(raw_cached)
                    except ValueError:
                        cached = raw_cached
                value = FormulaValue("=" + (formula.text or ""), cached)
            elif kind == "inlineStr":
                value = "".join(node.text or "" for node in cell.iterfind(".//m:t", NS))
            elif value_node is None:
                value = ""
            elif kind == "s":
                value = shared[int(value_node.text or 0)]
            elif kind == "b":
                value = value_node.text == "1"
            else:
                raw = value_node.text or ""
                try:
                    value = float(raw)
                except ValueError:
                    value = raw
            values[index] = value
        width = max(values, default=-1) + 1
        rows.append([values.get(index, "") for index in range(width)])
    return rows


def _header_analysis(rows: list[list[object]]) -> tuple[int, dict[str, int], int]:
    best_row, best_map, best_strength = -1, {}, 0
    aliases_by_field = {**HEADER_ALIASES, **OPTIONAL_HEADER_ALIASES}
    field_order = {field: index for index, field in enumerate(aliases_by_field)}
    for row_index, row in enumerate(rows[:30]):
        candidates: list[tuple[int, str, int]] = []
        for field, aliases in aliases_by_field.items():
            normalized_aliases = tuple(normalize(alias) for alias in aliases)
            for column, value in enumerate(row):
                candidate = normalize(value)
                if not candidate:
                    continue
                if candidate in normalized_aliases:
                    candidates.append((2, field, column))
                elif any(alias in candidate for alias in normalized_aliases):
                    candidates.append((1, field, column))
        mapping: dict[str, int] = {}
        used_columns: set[int] = set()
        strength = 0
        for match_strength, field, column in sorted(candidates, key=lambda item: (-item[0], field_order[item[1]], item[2])):
            if field in mapping or column in used_columns:
                continue
            mapping[field] = column
            used_columns.add(column)
            strength += match_strength
        if (len(mapping), strength, -row_index) > (len(best_map), best_strength, -best_row):
            best_row, best_map, best_strength = row_index, mapping, strength
    return best_row, best_map, best_strength


def workbook_tables(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                shared.append("".join(node.text or "" for node in item.iterfind(".//m:t", NS)))
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets: dict[str, str] = {}
        for relation in rels.findall("p:Relationship", REL_NS):
            identifier = relation.attrib.get("Id")
            target = relation.attrib.get("Target")
            if identifier and target:
                targets[identifier] = target
        candidates: list[dict] = []
        for sheet in book.findall("m:sheets/m:sheet", NS):
            rel_id = sheet.attrib.get(f"{{{NS['r']}}}id", "")
            target = targets.get(rel_id)
            if not target:
                continue
            sheet_path = "xl/" + target.lstrip("/").removeprefix("xl/")
            rows = _worksheet_rows(archive, sheet_path, shared)
            header_row, mapping, strength = _header_analysis(rows)
            usable = 0
            if header_row >= 0 and "sequence" in mapping and "name" in mapping:
                for row in rows[header_row + 1:]:
                    sequence = row[mapping["sequence"]] if mapping["sequence"] < len(row) else ""
                    name = row[mapping["name"]] if mapping["name"] < len(row) else ""
                    # Table discovery must not turn a sequence-format defect into an
                    # unreadable-workbook result. Sequence conformance is scored after
                    # the observable BOQ rows have been parsed.
                    usable += int(bool(str(sequence or "").strip()) and bool(str(name or "").strip()))
            candidates.append({
                "name": sheet.attrib.get("name", ""),
                "rows": rows,
                "header_row": header_row,
                "mapping": mapping,
                "strength": strength,
                "usable": usable,
            })
        return candidates


def workbook_rows(path: Path) -> list[list[object]]:
    candidates = workbook_tables(path)
    best = max(
        candidates,
        key=lambda table: (
            len(table["mapping"]),
            bool(table["usable"]),
            table["strength"],
            table["usable"],
        ),
        default=None,
    )
    return best["rows"] if best else []


def find_headers(rows: list[list[object]]) -> tuple[int, dict[str, int]]:
    best_row, best_map, _ = _header_analysis(rows)
    return best_row, best_map


def get(row: list[object], index: int | None) -> object:
    return row[index] if index is not None and index < len(row) else ""


def as_sequence(value: object) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() and number > 0 else None


def sequence_key(value: object) -> int | str | None:
    """Return a linkable integer key or an observable nonconforming row key."""
    valid = as_sequence(value)
    if valid is not None:
        return valid
    raw = normalize(value)
    return f"invalid:{raw}" if raw else None


def as_number(value: object) -> float | None:
    if isinstance(value, FormulaValue):
        value = value.cached
    elif isinstance(value, str) and value.startswith("="):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def column_letters(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def pricing_line_ready(unit_price: object, total: object, row_number: int, quantity_column: int | None, price_column: int | None) -> bool:
    price_is_blank = unit_price is None or str(unit_price).strip() == ""
    if not price_is_blank or quantity_column is None or price_column is None:
        return False
    formula = re.sub(r"\s+|\$", "", str(total or "")).upper()
    if not formula.startswith("=") or any(marker in formula for marker in ("[", "]", "!")):
        return False
    quantity_ref = f"{column_letters(quantity_column)}{row_number}"
    price_ref = f"{column_letters(price_column)}{row_number}"
    product = rf"(?:{quantity_ref}\*{price_ref}|{price_ref}\*{quantity_ref}|PRODUCT\({quantity_ref},{price_ref}\)|PRODUCT\({price_ref},{quantity_ref}\))"
    accepted = (
        rf"={product}",
        rf"=ROUND\({product},\d+\)",
        rf'=IF\(OR\((?:{quantity_ref}="",{price_ref}=""|{price_ref}="",{quantity_ref}="")\),"",ROUND\({product},\d+\)\)',
    )
    return any(re.fullmatch(pattern, formula) for pattern in accepted)


def canonical_section(text: str, sections: list[dict], fallback: int | None) -> str:
    key = normalize(text)
    for section in sections:
        if key and key == normalize(section["name"]):
            return section["name"]
    return ""


def parse_candidate(
    rows: list[list[object]],
    header_row: int,
    mapping: dict[str, int],
    sections: list[dict],
    default_section: str = "",
) -> tuple[dict[tuple[str, int | str], dict], list[tuple[str, int | str]], int, int, int]:
    items: dict[tuple[str, int | str], dict] = {}
    duplicates: list[tuple[str, int | str]] = []
    seen_signatures: set[tuple[object, ...]] = set()
    exact_repeats = 0
    current_canonical = canonical_section(default_section, sections, None) if default_section else ""
    current_raw = default_section
    recognized_sections: set[str] = set()
    if current_canonical:
        recognized_sections.add(current_canonical)
    item_rows = 0
    for row_number, row in enumerate(rows[header_row + 1:], start=header_row + 2):
        raw_sequence = get(row, mapping.get("sequence"))
        valid_sequence = as_sequence(raw_sequence)
        name = str(get(row, mapping.get("name")) or "").strip()
        # A nonnumeric value in the sequence column is often a standalone
        # section heading. It becomes a scoreable nonconforming item key only
        # when the row also has an item name.
        if valid_sequence is None and not name:
            section_text = " ".join(str(value) for value in row[:3] if value not in (None, ""))
            if section_text:
                current_raw = section_text.strip()
                current_canonical = canonical_section(section_text, sections, None)
                if current_canonical:
                    recognized_sections.add(current_canonical)
            continue
        sequence = valid_sequence if valid_sequence is not None else sequence_key(raw_sequence)
        if sequence is None:
            continue
        section_column = mapping.get("section")
        if section_column is not None:
            explicit_section = str(get(row, section_column) or "").strip()
            if explicit_section:
                current_raw = explicit_section
                current_canonical = canonical_section(explicit_section, sections, None)
                if current_canonical:
                    recognized_sections.add(current_canonical)
        item_rows += 1
        key_section = current_canonical or normalize(current_raw)
        key = (key_section, sequence)
        item = {
            "section": key_section,
            "sequence": sequence,
            "raw_sequence": raw_sequence,
            "sequence_valid": isinstance(sequence, int),
            "name": name,
            "characteristics": get(row, mapping.get("characteristics")),
            "rule": get(row, mapping.get("rule")),
            "unit": get(row, mapping.get("unit")),
            "quantity": get(row, mapping.get("quantity")),
            "unit_price": get(row, mapping.get("unit_price")),
            "total": get(row, mapping.get("total")),
            "evidence": get(row, mapping.get("evidence")),
            "quantity_basis": get(row, mapping.get("quantity_basis")),
            "basis_status": get(row, mapping.get("basis_status")),
            "row_number": row_number,
            "pricing_ready": pricing_line_ready(
                get(row, mapping.get("unit_price")),
                get(row, mapping.get("total")),
                row_number,
                mapping.get("quantity"),
                mapping.get("unit_price"),
            ),
        }
        signature = (
            key_section,
            sequence,
            normalize(item["name"]),
            normalize(item["characteristics"]),
            normalize(item["rule"]),
            normalize(item["unit"]),
            normalize(item["quantity"]),
            item["unit_price"] is not None and str(item["unit_price"]).strip() != "",
        )
        if signature in seen_signatures:
            exact_repeats += 1
        else:
            seen_signatures.add(signature)
        if key in items:
            duplicates.append(key)
        else:
            items[key] = item
    return items, duplicates, exact_repeats, len(recognized_sections), item_rows


def select_boq_tables(tables: list[dict], sections: list[dict]) -> list[dict]:
    """Select one consolidated BOQ table or a non-overlapping section-sheet set."""
    expected_sections = {section["name"] for section in sections}
    parsed: list[dict] = []
    for table in tables:
        if table["header_row"] < 0 or not table["usable"]:
            continue
        items, duplicates, exact_repeats, section_count, item_rows = parse_candidate(
            table["rows"],
            table["header_row"],
            table["mapping"],
            sections,
            table["name"],
        )
        parsed.append({
            **table,
            "items": items,
            "duplicates": duplicates,
            "exact_repeats": exact_repeats,
            "section_count": section_count,
            "item_rows": item_rows,
            "recognized": {key[0] for key in items if key[0] in expected_sections},
            "boq_core_count": sum(field in table["mapping"] for field in BOQ_DISCOVERY_HEADERS),
        })
    # A sheet with only section/sequence/name columns is an index, not a priced
    # BOQ. Prefer tables that expose the physical quantity and technical fields
    # required to describe a payable line before considering section coverage.
    qualified = [
        table for table in parsed
        if all(field in table["mapping"] for field in BOQ_DISCOVERY_HEADERS)
    ]
    if qualified:
        parsed = qualified
    consolidated = [table for table in parsed if table["recognized"] >= expected_sections]
    if consolidated:
        return [max(consolidated, key=lambda table: (table["boq_core_count"], len(table["mapping"]), table["strength"], table["item_rows"]))]
    selected: list[dict] = []
    covered: set[str] = set()
    for table in sorted(
        parsed,
        key=lambda item: (len(item["recognized"]), item["boq_core_count"], len(item["mapping"]), item["strength"], item["item_rows"]),
        reverse=True,
    ):
        if table["recognized"] - covered:
            selected.append(table)
            covered.update(table["recognized"])
    if selected:
        return selected
    return [max(parsed, key=lambda table: (table["boq_core_count"], len(table["mapping"]), table["strength"], table["item_rows"]))] if parsed else []


def maximum_identity_pairs(gold_items: list[dict], candidate_items: list[dict]) -> list[tuple[dict, dict, float]]:
    """Return a maximum-cardinality, maximum-similarity one-to-one assignment."""
    if not gold_items or not candidate_items:
        return []
    row_count = len(gold_items)
    column_count = len(candidate_items) + row_count
    weights: list[list[float]] = []
    similarities: list[list[float]] = []
    cardinality_bonus = 2.0 * row_count
    for gold in gold_items:
        sims = [similarity(candidate["name"], gold["name"]) for candidate in candidate_items]
        similarities.append(sims)
        weights.append([
            (cardinality_bonus + score + 0.1 * float(normalize(candidate["unit"]) == normalize(gold["unit"]))) if score >= 0.35 else 0.0
            for score, candidate in zip(sims, candidate_items)
        ] + [0.0] * row_count)

    # Rectangular Hungarian assignment. Dummy columns allow an unmatched gold row.
    u = [0.0] * (row_count + 1)
    v = [0.0] * (column_count + 1)
    p = [0] * (column_count + 1)
    way = [0] * (column_count + 1)
    for row in range(1, row_count + 1):
        p[0] = row
        minimum = [float("inf")] * (column_count + 1)
        used = [False] * (column_count + 1)
        column0 = 0
        while True:
            used[column0] = True
            row0 = p[column0]
            delta = float("inf")
            column1 = 0
            for column in range(1, column_count + 1):
                if used[column]:
                    continue
                cost = -weights[row0 - 1][column - 1]
                current = cost - u[row0] - v[column]
                if current < minimum[column]:
                    minimum[column] = current
                    way[column] = column0
                if minimum[column] < delta:
                    delta = minimum[column]
                    column1 = column
            for column in range(column_count + 1):
                if used[column]:
                    u[p[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            column0 = column1
            if p[column0] == 0:
                break
        while True:
            column1 = way[column0]
            p[column0] = p[column1]
            column0 = column1
            if column0 == 0:
                break

    assignment = [-1] * row_count
    for column in range(1, column_count + 1):
        if p[column]:
            assignment[p[column] - 1] = column - 1
    pairs: list[tuple[dict, dict, float]] = []
    for gold_index, candidate_index in enumerate(assignment):
        if candidate_index < len(candidate_items):
            score = similarities[gold_index][candidate_index]
            if score >= 0.35:
                pairs.append((gold_items[gold_index], candidate_items[candidate_index], score))
    return pairs


CHARACTERISTIC_ELEMENT = re.compile(r"(?:^|[\n;；])\s*\d+\s*[.、．]\s*([^：:\n]{2,16})[：:]")


def characteristic_elements(text: object) -> list[str]:
    """The element names a characteristics cell declares, in the pricing code's form."""
    return [normalize(name) for name in CHARACTERISTIC_ELEMENT.findall(str(text or "")) if normalize(name)]


def characteristic_coverage(candidate: object, gold: object) -> float:
    """How much of the reference element set the submitted cell actually carries.

    Character similarity is the wrong instrument here. The pricing code fixes
    which elements a characteristics cell must declare, not the words that
    describe them: a line stating the ground class as the strata the
    investigation actually logs, rather than as the code's shorthand class,
    has priced the same risk and named the same element. Measured by string
    overlap those two cells score about one half, which is indistinguishable
    from a cell that omits half the elements.

    So the element names carry the score, and the text of each element is
    compared only to separate a filled element from an empty one. Where the
    reference cell is unstructured prose, fall back to similarity — there is no
    element list to compare against.
    """
    expected = characteristic_elements(gold)
    if not expected:
        return similarity(candidate, gold)
    actual = characteristic_elements(candidate)
    if not actual:
        # Prose against a structured reference: the elements may still be
        # present as running text, so fall back rather than scoring zero.
        return similarity(candidate, gold)
    actual_set = set(actual)
    hit = sum(
        1.0 if name in actual_set else max(
            (0.6 for other in actual_set if name and (name in other or other in name)), default=0.0
        )
        for name in expected
    )
    recall = hit / len(expected)
    precision = hit / len(actual) if actual else 0.0
    if recall <= 0 or precision <= 0:
        return 0.0
    # Harmonic mean: neither omitting elements nor padding the cell with
    # unrelated ones can buy credit.
    return 2 * recall * precision / (recall + precision)


def technical_score(candidate: dict, gold: dict) -> float:
    characteristics = characteristic_coverage(candidate["characteristics"], gold["characteristics"])
    rule = similarity(candidate["rule"], gold["measurement_rule"])
    if normalize(candidate["rule"]) and rule < 0.2:
        rule = 0.2
    return min(1.0, 0.8 * characteristics + 0.2 * rule)


def control_header_analysis(rows: list[list[object]]) -> tuple[int, dict[str, int], int]:
    best_row, best_map, best_strength = -1, {}, 0
    field_order = {field: index for index, field in enumerate(CONTROL_HEADER_ALIASES)}
    for row_index, row in enumerate(rows[:30]):
        choices: list[tuple[int, str, int]] = []
        for field, aliases in CONTROL_HEADER_ALIASES.items():
            normalized_aliases = tuple(normalize(alias) for alias in aliases)
            for column, value in enumerate(row):
                candidate = normalize(value)
                if not candidate:
                    continue
                if candidate in normalized_aliases:
                    choices.append((2, field, column))
                elif any(alias in candidate for alias in normalized_aliases):
                    choices.append((1, field, column))
        mapping: dict[str, int] = {}
        used: set[int] = set()
        strength = 0
        for match_strength, field, column in sorted(choices, key=lambda item: (-item[0], field_order[item[1]], item[2])):
            if field in mapping or column in used:
                continue
            mapping[field] = column
            used.add(column)
            strength += match_strength
        if (len(mapping), strength, -row_index) > (len(best_map), best_strength, -best_row):
            best_row, best_map, best_strength = row_index, mapping, strength
    return best_row, best_map, best_strength


def canonical_record_type(value: object) -> str:
    key = normalize(value)
    aliases = {
        "parameter": ("parameter", "param", "参数"),
        "uncertainty": ("uncertainty", "assumption", "conflict", "假设", "冲突", "不确定项"),
        "closure": ("closure", "reconciliation", "check", "闭合", "校核"),
    }
    for canonical, values in aliases.items():
        if any(normalize(item) in key for item in values):
            return canonical
    return ""


def control_status_valid(record_type: str, value: object) -> bool:
    key = normalize(value)
    # The instruction does not prescribe a separate control-status vocabulary.
    # Accept professional equivalents of adopted, verified, calculated,
    # source-stated, provisional, and review-required states.
    accepted = {
        "parameter": ("adopted", "verified", "calculated", "sourcestated", "confirmed",
                      "采用", "已采用", "已核定", "已验证", "已计算", "已确认", "源文件明确"),
        "uncertainty": ("provisional", "reviewrequired", "resolved", "excluded", "open",
                        "fortenderreview", "暂估", "待复核", "待确认", "已解决", "已排除",
                        "未决", "提交评标复核"),
        "closure": ("pass", "verified", "reviewrequired", "closed", "calculated",
                    "通过", "已验证", "待复核", "待确认", "已闭合"),
    }
    return any(normalize(item) in key for item in accepted.get(record_type, ()))


def closure_comparison_valid(value_issue: object, action: object, linked_items: list[dict] | None = None) -> bool:
    raw = f"{value_issue or ''} {action or ''}"
    has_comparison = bool(re.search(r"(?:=|≠|≤|≥|<|>|difference|variance|ratio|compare|差值|偏差|比例|对比|比较)", raw, re.IGNORECASE))
    numbers = [float(value) for value in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", raw)]
    if not has_comparison or not numbers:
        return False
    if not linked_items:
        return len(numbers) >= 3
    quantities = [as_number(item.get("quantity")) for item in linked_items]
    units = {normalize(item.get("unit")) for item in linked_items}
    if len(quantities) < 2 or any(value is None for value in quantities) or len(units) != 1:
        return False
    comparison_text = re.split(r"(?:difference|variance|差值|偏差)", str(value_issue or ""), maxsplit=1, flags=re.IGNORECASE)[0]
    remaining = [float(value) for value in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", comparison_text)]
    for quantity in quantities:
        match = next((index for index, value in enumerate(remaining) if abs(value - quantity) <= 0.01), None)
        if match is None:
            return False
        remaining.pop(match)
    if len(quantities) == 2:
        difference = abs(quantities[0] - quantities[1])
        result_text = raw[len(comparison_text):]
        result_numbers = [float(value) for value in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", result_text)]
        if not any(abs(value - difference) <= 0.01 for value in result_numbers):
            return False
    return True


def linked_item_resolution(
    value: object,
    section_value: object,
    candidates: dict[tuple[str, int | str], dict],
    sections: list[dict],
) -> tuple[set[tuple[str, int | str]], int, int]:
    """Resolve explicit audit links and retain broken links in the denominator."""
    raw = str(value or "").strip()
    section_text = str(section_value or "").strip()
    canonical = canonical_section(section_text, sections, None)
    if normalize(raw) in {"all", "全部", "全段", "所有清单项"} or raw == "*":
        keys = {key for key in candidates if not canonical or key[0] == canonical}
        count = len(keys)
        return keys, count, count

    aliases: dict[tuple[str, str], tuple[str, int | str]] = {}
    global_aliases: dict[str, list[tuple[str, int | str]]] = {}
    for key, item in candidates.items():
        sequence_label = normalize(item.get("raw_sequence"))
        if sequence_label:
            aliases[(key[0], sequence_label)] = key
            global_aliases.setdefault(sequence_label, []).append(key)
        if isinstance(key[1], int):
            for sequence_alias in (str(key[1]), normalize(f"序号{key[1]}"), normalize(f"序{key[1]}"),
                                   normalize(f"第{key[1]}项"), normalize(f"第 {key[1]} 项")):
                aliases[(key[0], sequence_alias)] = key
                global_aliases.setdefault(sequence_alias, []).append(key)

    keys: set[tuple[str, int | str]] = set()
    declared = 0
    resolved = 0
    for link_part in re.split(r"[,;，；、\n]+", raw):
        link_part = link_part.strip()
        if not link_part:
            continue
        declared += 1
        linked_section = canonical
        sequence_label = link_part
        if "#" in link_part or "＃" in link_part:
            parts = re.split(r"[#＃]", link_part, maxsplit=1)
            linked_section = canonical_section(parts[0].strip(), sections, None)
            sequence_label = parts[1].strip() if len(parts) > 1 else ""
        else:
            explicit_sections = [section["name"] for section in sections if section["name"] in link_part]
            if len(explicit_sections) == 1:
                linked_section = explicit_sections[0]
                sequence_label = link_part.replace(linked_section, "", 1).strip()
        normalized_sequence = normalize(sequence_label)
        key = aliases.get((linked_section, normalized_sequence)) if linked_section else None
        if key is None and not linked_section:
            global_matches = list(dict.fromkeys(global_aliases.get(normalized_sequence, [])))
            key = global_matches[0] if len(global_matches) == 1 else None
        if key is not None:
            keys.add(key)
            resolved += 1
    return keys, declared, resolved


def control_ledger_score(
    tables: list[dict],
    candidates: dict[tuple[str, int | str], dict],
    sections: list[dict],
    sources: list[str],
) -> tuple[float, int, dict[str, float | int]]:
    expected_sections = {section["name"] for section in sections}
    best_score = 0.0
    best_valid = 0
    best_details: dict[str, float | int] = {
        "link_integrity": 0.0,
        "parameter_coverage": 0.0,
        "uncertainty_control": 0.0,
        "closure_coverage": 0.0,
        "declared_links": 0,
        "resolved_links": 0,
    }
    for table in tables:
        header_row, mapping, _ = control_header_analysis(table["rows"])
        if header_row < 0 or len(mapping) < len(CONTROL_HEADER_ALIASES):
            continue
        parameter_sections: set[str] = set()
        closure_sections: set[str] = set()
        uncertainty_valid = False
        valid_records = 0
        declared_links = 0
        resolved_links = 0
        record_link_scores: list[float] = []
        seen_ids: set[str] = set()
        for row in table["rows"][header_row + 1:]:
            record_type = canonical_record_type(get(row, mapping.get("record_type")))
            record_id = normalize(get(row, mapping.get("record_id")))
            section_raw = get(row, mapping.get("section"))
            section = canonical_section(str(section_raw or ""), sections, None)
            is_all = normalize(section_raw) in {"all", "全部", "全项目"}
            links, declared, resolved = linked_item_resolution(get(row, mapping.get("linked_items")), section_raw, candidates, sections)
            source = get(row, mapping.get("source"))
            value_issue = str(get(row, mapping.get("value_issue")) or "").strip()
            action = str(get(row, mapping.get("action")) or "").strip()
            status = get(row, mapping.get("status"))
            if not record_type or not record_id or record_id in seen_ids or not value_issue or not action or not control_status_valid(record_type, status):
                continue
            declared_links += declared
            resolved_links += resolved
            record_link_scores.append(resolved / declared if declared else 0.0)
            if not links:
                continue
            if record_type in {"parameter", "uncertainty"} and not source_reference_valid(source, sources):
                continue
            if record_type == "parameter" and not re.search(r"\d", value_issue):
                continue
            if record_type == "closure" and len(links) < 2:
                continue
            if record_type == "closure" and not closure_comparison_valid(value_issue, action, [candidates[key] for key in links]):
                continue
            seen_ids.add(record_id)
            valid_records += 1
            declared_sections = {
                expected for expected in expected_sections
                if expected in str(section_raw or "")
            }
            linked_sections = {key[0] for key in links if key[0] in expected_sections}
            covered_sections = linked_sections if is_all else linked_sections & declared_sections
            if record_type == "parameter":
                parameter_sections.update(covered_sections)
            elif record_type == "closure":
                closure_sections.update(covered_sections)
            else:
                uncertainty_valid = True
        parameter_coverage = len(parameter_sections & expected_sections) / max(len(expected_sections), 1)
        uncertainty_control = float(uncertainty_valid)
        closure_coverage = len(closure_sections & expected_sections) / max(len(expected_sections), 1)
        link_integrity = sum(record_link_scores) / len(record_link_scores) if record_link_scores else 0.0
        score = 0.25 * link_integrity + 0.25 * parameter_coverage + 0.15 * uncertainty_control + 0.35 * closure_coverage
        if score > best_score:
            best_score, best_valid = score, valid_records
            best_details = {
                "link_integrity": link_integrity,
                "parameter_coverage": parameter_coverage,
                "uncertainty_control": uncertainty_control,
                "closure_coverage": closure_coverage,
                "declared_links": declared_links,
                "resolved_links": resolved_links,
            }
    return best_score, best_valid, best_details


def score(path: Path, truth_path: Path) -> dict:
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    sources = list(truth.get("audit_contract", {}).get("sources", []))
    gold_items = [item for section in truth["sections"] for item in section["items"]]
    total = len(gold_items)
    diagnostics: list[str] = []
    if not path.is_file() or path.suffix.lower() != ".xlsx":
        diagnostics.append("The required XLSX deliverable was not found.")
        return empty_result(path, diagnostics)
    try:
        tables = workbook_tables(path)
    except Exception as exc:
        diagnostics.append(f"The workbook could not be read: {type(exc).__name__}.")
        return empty_result(path, diagnostics)
    selected_tables = select_boq_tables(tables, truth["sections"])
    if not selected_tables:
        diagnostics.append("No recognizable BOQ header row was found.")
        return empty_result(path, diagnostics)

    candidates: dict[tuple[str, int], dict] = {}
    duplicates: list[tuple[str, int]] = []
    exact_repeats = 0
    item_rows = 0
    recognized_sections: set[str] = set()
    contract_header_weight = 0.0
    pricing_header_weight = 0.0
    for table in selected_tables:
        item_rows += table["item_rows"]
        exact_repeats += table["exact_repeats"]
        duplicates.extend(table["duplicates"])
        contract_header_completeness = len(set(table["mapping"]) & set(CORE_HEADERS)) / len(CORE_HEADERS)
        pricing_header_completeness = len(set(table["mapping"]) & set(PRICING_HEADERS)) / len(PRICING_HEADERS)
        contract_header_weight += contract_header_completeness * table["item_rows"]
        pricing_header_weight += pricing_header_completeness * table["item_rows"]
        for key, item in table["items"].items():
            if key in candidates:
                duplicates.append(key)
                continue
            candidates[key] = item
            if key[0] in {section["name"] for section in truth["sections"]}:
                recognized_sections.add(key[0])
    section_count = len(recognized_sections)

    covered = 0
    identity_sum = technical_sum = quantity_sum = calculation_ready = 0.0
    matched_keys: set[tuple[str, int]] = set()
    matched_candidate_keys: set[tuple[str, int | str]] = set()
    for section in truth["sections"]:
        section_gold = [item for item in gold_items if item["section"] == section["name"]]
        section_candidates = [item for item in candidates.values() if item["section"] == section["name"]]
        for gold, candidate, name_similarity in maximum_identity_pairs(section_gold, section_candidates):
            covered += 1
            matched_keys.add((gold["section"], gold["sequence"]))
            matched_candidate_keys.add((candidate["section"], candidate["sequence"]))
            identity_sum += 0.8 * name_similarity + 0.2 * float(normalize(candidate["unit"]) == normalize(gold["unit"]))
            technical_sum += technical_score(candidate, gold)
            observed = as_number(candidate["quantity"])
            expected = float(gold["quantity"])
            tolerance = max(float(truth["quantity_tolerance"]["absolute"]), abs(expected) * float(truth["quantity_tolerance"]["relative"]))
            if observed is not None and normalize(candidate["unit"]) == normalize(gold["unit"]):
                error = abs(observed - expected)
                quantity_sum += 1.0 if error <= tolerance else max(0.0, 1.0 - error / max(abs(expected) * 0.10, tolerance))
            if candidate["pricing_ready"]:
                calculation_ready += 1.0

    missing = [
        f"{gold['section']}#{gold['sequence']}"
        for gold in gold_items
        if (gold["section"], gold["sequence"]) not in matched_keys
    ]

    unmatched_claimed = [item for key, item in candidates.items() if key not in matched_candidate_keys and item.get("evidence")]
    unmatched_populated = [item for key, item in candidates.items()
                           if key not in matched_candidate_keys
                           and all(str(item.get(field) or "").strip() for field in ("name", "unit", "quantity"))]
    precision = total / (total + len(unmatched_claimed))
    coverage = covered / total * precision
    identity = identity_sum / total
    technical = technical_sum / total
    quantity = quantity_sum / total
    header_completeness = contract_header_weight / item_rows if item_rows else 0.0
    pricing_header_completeness = pricing_header_weight / item_rows if item_rows else 0.0
    pricing = 0.6 * pricing_header_completeness + 0.4 * calculation_ready / total
    expected_section_rows = {section["name"]: len(section["items"]) for section in truth["sections"]}
    candidate_section_rows = {
        section["name"]: sum(key[0] == section["name"] and scope_line_usable(item) for key, item in candidates.items())
        for section in truth["sections"]
    }
    matched_section_rows = {
        section["name"]: sum(
            key[0] == section["name"] and scope_line_usable(candidates[key])
            for key in matched_candidate_keys
            if key in candidates
        )
        for section in truth["sections"]
    }
    scope_completeness = scope_completion_score(matched_section_rows, expected_section_rows)
    traceability, complete_traceability_items = matched_traceability_score(candidates, matched_candidate_keys, total, sources)
    # Unsupported populated rows reduce issuance readiness even when they do
    # not carry an evidence string; otherwise blank-evidence filler could pad
    # every section past the lenient row-count threshold.
    traceability_completion = min(1.0, complete_traceability_items / max(total, 1))
    eligible_candidates = {key: candidates[key] for key in matched_candidate_keys}
    control_ledger, valid_control_records, control_details = control_ledger_score(tables, eligible_candidates, truth["sections"], sources)
    invalid_sequence_rows = sum(not item["sequence_valid"] for item in candidates.values())
    integrity_factor = total / (total + exact_repeats)
    strict = strict_score({
        "coverage": coverage,
        "line_identity_and_unit": identity,
        "technical_characteristics_and_rules": technical,
        "quantity_accuracy": quantity,
        "pricing_readiness": pricing,
        "scope_completeness": scope_completeness,
        "traceability": traceability,
        "control_ledger": control_ledger,
    }) * integrity_factor
    nonblank_characteristics = sum(bool(normalize(item["characteristics"])) for item in candidates.values())
    lenient = lenient_completion_score(
        header_completeness,
        item_rows,
        section_count,
        nonblank_characteristics,
        total,
        len(truth["sections"]),
        traceability_completion,
        quantity,
        control_ledger,
        scope_completion_score(candidate_section_rows, expected_section_rows),
    )
    if len(unmatched_populated) / max(len(candidates), 1) > 0.2:
        lenient = 0.0
    if exact_repeats:
        lenient = 0.0
    if missing:
        diagnostics.append(f"{len(missing)} expected line items were missing or not identifiable.")
    if duplicates:
        diagnostics.append(f"{len(duplicates)} duplicate section/sequence keys were ignored.")
    if invalid_sequence_rows:
        diagnostics.append(
            f"{invalid_sequence_rows} BOQ rows used non-integer sequence values; "
            "they remain content-scoreable and require exact sequence-label audit links."
        )
    if exact_repeats:
        diagnostics.append(f"{exact_repeats} exact repeated selected-BOQ rows reduced the continuous integrity factor.")
    return {
        "schema_version": 1,
        "scoring_version": SCORER_VERSION,
        "precision": {"unmatched_claimed_rows": len(unmatched_claimed), "factor": precision},
        "reward": round(strict, 6),
        "rewards": {"strict": round(strict, 6), "lenient": lenient},
        "reward_formulas": dict(REWARD_FORMULAS),
        "group_points": {
            "coverage": round(coverage, 6),
            "line_identity_and_unit": round(identity, 6),
            "technical_characteristics_and_rules": round(technical, 6),
            "quantity_accuracy": round(quantity, 6),
            "pricing_readiness": round(pricing, 6),
            "scope_completeness": round(scope_completeness, 6),
            "traceability": round(traceability, 6),
            "control_ledger": round(control_ledger, 6),
        },
        "control_details": {key: round(value, 6) if isinstance(value, float) else value for key, value in control_details.items()},
        "counts": {"expected_items": total, "matched_items": covered, "candidate_item_rows": item_rows, "candidate_rows_by_section": candidate_section_rows, "matched_usable_rows_by_section": matched_section_rows, "recognized_sections": section_count, "complete_traceability_items": complete_traceability_items, "valid_control_records": valid_control_records, "invalid_sequence_rows": invalid_sequence_rows, "duplicate_keys": len(duplicates), "exact_repeated_rows": exact_repeats},
        "integrity": {"factor": round(integrity_factor, 6), "exact_repeated_selected_boq_rows": exact_repeats},
        "infrastructure_error": False,
        "diagnostics": diagnostics,
    }


def empty_result(path: Path, diagnostics: list[str]) -> dict:
    return {
        "schema_version": 1,
        "scoring_version": SCORER_VERSION,
        "precision": {"unmatched_claimed_rows": 0, "factor": 1.0},
        "reward": 0.0,
        "rewards": {"strict": 0.0, "lenient": 0.0},
        "reward_formulas": dict(REWARD_FORMULAS),
        "group_points": {"coverage": 0.0, "line_identity_and_unit": 0.0, "technical_characteristics_and_rules": 0.0, "quantity_accuracy": 0.0, "pricing_readiness": 0.0, "scope_completeness": 0.0, "traceability": 0.0, "control_ledger": 0.0},
        "counts": {"expected_items": 95, "matched_items": 0, "candidate_item_rows": 0, "candidate_rows_by_section": {}, "recognized_sections": 0, "complete_traceability_items": 0, "valid_control_records": 0, "invalid_sequence_rows": 0, "duplicate_keys": 0, "exact_repeated_rows": 0},
        "integrity": {"factor": 1.0, "exact_repeated_selected_boq_rows": 0},
        "infrastructure_error": False,
        "diagnostics": diagnostics,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    artifact = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/边坡支护专业分包招标清单.xlsx")
    truth = Path(__file__).with_name("ground_truth.json")
    print(json.dumps(score(artifact, truth), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

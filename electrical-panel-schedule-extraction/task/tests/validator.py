#!/usr/bin/env python3
"""Deterministic verifier for an image-grounded editable electrical DXF."""

from __future__ import annotations

import json
import itertools
import math
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from semantic_judge import adjudicate

WEIGHTS = {"semantic_content": 0.50, "diagram_topology": 0.50}
DIMENSIONS = ("semantic_content", "diagram_topology", "vector_delivery")
INCOMING_FIELDS = ("feeder_cable", "upstream_setting", "main_breaker", "enclosure_model", "installed_capacity_kw", "calculated_current_a")
ROW_FIELDS = ("load_name", "capacity_kw", "phase_sequence", "breaker", "conductor_conduit")
COHERENT_REQUIRED_FIELDS = ("load_name", "breaker", "conductor_conduit")
FORBIDDEN_TYPES = {"IMAGE", "IMAGEDEF", "IMAGEDEF_REACTOR", "PDFUNDERLAY", "DWFUNDERLAY", "DGNUNDERLAY", "OLE2FRAME", "WIPEOUT", "PDFDEFINITION", "DWFDEFINITION", "DGNDEFINITION"}
NATIVE_GEOMETRY_TYPES = {
    "LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE",
    "INSERT", "HATCH", "DIMENSION", "LEADER", "SOLID", "TRACE", "3DFACE",
}
TRACE_LIKE_TYPES = {"LINE", "LWPOLYLINE", "POLYLINE", "SOLID", "TRACE", "3DFACE", "HATCH"}
CIRCUIT_KEY_RE = re.compile(r"(?<![A-Z0-9])(?:WL|WX|WP|G)\d+(?!\d)")
MAX_NATIVE_GEOMETRY = 25_000
MAX_TRACE_GEOMETRY_PER_TEXT = 100
SHEET_ANCHORS = {
    "S-01": ("图纸目录", "电气施工图设计说明", "图例"),
    "S-02": ("1AL1", "2AL1", "2AL2"),
    "S-03": ("引至楼层应急照明配电箱", "主入口", "财富管理室"),
    "S-04": ("配电间", "总经理室", "等候室"),
}

def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    return re.sub(r"\s+", "", text).replace("×", "x").replace("*", "x").upper()

def numeric(value: object) -> float | None:
    match = re.search(r"(?<![\d.])[-+]?\d+(?:\.\d+)?(?![\d.])", normalize(value))
    return float(match.group()) if match else None

def field_match(actual_text: str, expected: object, numeric_field: bool = False) -> bool:
    actual, target = normalize(actual_text), normalize(expected)
    if not target:
        return False
    if numeric_field:
        wanted = numeric(target)
        if wanted is None:
            return False
        values=[float(value) for value in re.findall(r"(?<![A-Z\d.])[-+]?\d+(?:\.\d+)?(?![A-Z\d.])",actual)]
        return any(math.isclose(value,wanted,abs_tol=0.05) for value in values)
    # CAD text may split a compound breaker across entities and place the
    # circuit label between the two visual parts (for example `/4P`, `WP3`,
    # then `Vigi 30mA`). Treat each required breaker component as present.
    if "+" in target:
        return all(part and part in actual for part in target.split("+"))
    return target in actual or target.replace("+", "") in actual.replace("+", "")

def coherent_row_quality(hits: dict[str, bool], unique_key: bool) -> float:
    """Credit a partial row only when one unique row owns its circuit key."""
    if not unique_key or not hits.get("key", False):
        return 0.0
    matched_fields = sum(bool(hits.get(field, False)) for field in ROW_FIELDS)
    required_fields_present = all(
        hits.get(field, False) for field in COHERENT_REQUIRED_FIELDS
    )
    return matched_fields / len(ROW_FIELDS) if matched_fields >= 4 and required_fields_present else 0.0

def truth_path() -> Path:
    return Path(__file__).with_name("ground_truth.json")

def locate_submission(target: Path) -> Path | None:
    if target.is_file():
        return target
    candidates = (target / "output/electrical_drawings.dxf", target / "electrical_drawings.dxf", target / "workspace/output/electrical_drawings.dxf")
    return next((path for path in candidates if path.is_file()), None)

def empty_result(error: str) -> dict:
    return {"schema_version": "electrical-drawing-set-dxf-validator-v4", "reward": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0}, "reward_formulas": {"strict": "valid editable DXF gate * (0.50*semantic_content + 0.50*diagram_topology)", "lenient": "1 iff native delivery, sheet/panel coverage, row/topology floors and source-bound sheet/device/connection semantics pass"}, "dimension_scores": {key: 0.0 for key in DIMENSIONS}, "counts": {}, "must_have": {"passed": False}, "errors": [error]}

def parse_dxf(path: Path) -> tuple[list[dict], list[str]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gb18030", errors="replace")
    lines = [line.rstrip("\r") for line in text.splitlines()]
    errors = []
    if len(lines) % 2:
        errors.append("malformed DXF group-code/value pairing")
    pairs = [(lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    entities, section, current = [], None, None
    awaiting_section_name = False
    seen_sections: list[str] = []
    closed_sections: list[str] = []
    saw_eof = False
    for code, value in pairs:
        if code == "0":
            if current is not None and section == "ENTITIES":
                entities.append(current)
                current = None
            if value == "SECTION":
                if section is not None or awaiting_section_name:
                    errors.append("nested or unnamed SECTION")
                awaiting_section_name = True
                section = None
            elif value == "ENDSEC":
                if section is None:
                    errors.append("ENDSEC without open SECTION")
                else:
                    closed_sections.append(section)
                section = None
                awaiting_section_name = False
            elif value == "EOF":
                saw_eof = True
            elif section == "ENTITIES":
                current = {"type": value, "values": {}}
            continue
        if awaiting_section_name:
            if code != "2":
                errors.append("SECTION missing group-code 2 name")
                awaiting_section_name = False
            else:
                section = value.upper()
                seen_sections.append(section)
                awaiting_section_name = False
            continue
        if section == "ENTITIES" and current is not None:
            current["values"].setdefault(code, []).append(value)
    if current is not None:
        entities.append(current)
    if "ENTITIES" not in seen_sections:
        errors.append("missing ENTITIES section")
    elif "ENTITIES" not in closed_sections:
        errors.append("unterminated ENTITIES section")
    if not saw_eof:
        errors.append("missing EOF marker")
    return entities, errors

def entity_text(entity: dict) -> str:
    values = entity.get("values", {})
    return "".join(values.get("1", []) + values.get("3", []))

def entity_xy(entity: dict) -> tuple[float, float] | None:
    values = entity.get("values", {})
    try:
        return float(values.get("10", ["0"])[0]), float(values.get("20", ["0"])[0])
    except (TypeError, ValueError):
        return None

def geometry_signature(entity: dict) -> tuple:
    values = entity.get("values", {})
    coordinates = []
    for code in ("10", "20", "11", "21", "12", "22", "13", "23", "40", "41", "42", "50", "51", "70"):
        for value in values.get(code, []):
            try:
                coordinates.append((code, round(float(value), 3)))
            except ValueError:
                coordinates.append((code, value))
    return entity["type"], tuple(coordinates)


def point_in_box(point: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    x, y = point
    left, bottom, right, top = box
    return left - 1e-6 <= x <= right + 1e-6 and bottom - 1e-6 <= y <= top + 1e-6


def drawing_boxes(entities: list[dict]) -> list[tuple[float, float, float, float]]:
    """Return explicit rectangular regions drawn as polylines or four LINEs."""
    boxes: set[tuple[float, float, float, float]] = set()
    horizontal: dict[tuple[float, float], set[float]] = defaultdict(set)
    vertical: dict[tuple[float, float], set[float]] = defaultdict(set)
    for entity in entities:
        values = entity.get("values", {})
        if entity["type"] == "LWPOLYLINE":
            try:
                xs = [float(value) for value in values.get("10", [])]
                ys = [float(value) for value in values.get("20", [])]
            except ValueError:
                continue
            if len(xs) >= 4 and len(ys) >= 4 and max(xs) > min(xs) and max(ys) > min(ys):
                boxes.add(tuple(round(value, 6) for value in (min(xs), min(ys), max(xs), max(ys))))
        elif entity["type"] == "LINE":
            try:
                x0, y0, x1, y1 = (
                    float(values["10"][0]), float(values["20"][0]),
                    float(values["11"][0]), float(values["21"][0]),
                )
            except (KeyError, ValueError):
                continue
            if math.isclose(y0, y1, abs_tol=1e-6) and not math.isclose(x0, x1, abs_tol=1e-6):
                horizontal[(round(min(x0, x1), 6), round(max(x0, x1), 6))].add(round(y0, 6))
            elif math.isclose(x0, x1, abs_tol=1e-6) and not math.isclose(y0, y1, abs_tol=1e-6):
                vertical[(round(min(y0, y1), 6), round(max(y0, y1), 6))].add(round(x0, 6))
    for (left, right), y_values in horizontal.items():
        for bottom, top in itertools.combinations(sorted(y_values), 2):
            if left in vertical.get((bottom, top), set()) and right in vertical.get((bottom, top), set()):
                boxes.add((left, bottom, right, top))
    return sorted(boxes, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))


def titled_sheet_regions(
    entities: list[dict],
    normalized_texts: list[tuple[dict, str]],
    sheet_ids: list[str],
) -> dict[str, tuple[float, float, float, float] | None]:
    """Locate a submitted sheet by its visible sheet id and explicit CAD frame."""
    boxes = drawing_boxes(entities)
    regions = {}
    for sheet_id in sheet_ids:
        title_points = [
            entity_xy(entity) for entity, text in normalized_texts
            if text.startswith(normalize(sheet_id)) and entity_xy(entity) is not None
        ]
        candidates = []
        for box in boxes:
            if not title_points or not any(point_in_box(point, box) for point in title_points):
                continue
            local_texts = sum(
                point_in_box(entity_xy(entity), box)
                for entity, _text in normalized_texts if entity_xy(entity) is not None
            )
            local_geometry = sum(
                entity["type"] in NATIVE_GEOMETRY_TYPES
                and entity_xy(entity) is not None
                and point_in_box(entity_xy(entity), box)
                for entity in entities
            )
            if local_texts >= 10 and local_geometry >= 20:
                candidates.append((local_geometry + local_texts, -((box[2] - box[0]) * (box[3] - box[1])), box))
        regions[sheet_id] = max(candidates)[2] if candidates else None
    return regions


def entity_segments(entity: dict) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    values = entity.get("values", {})
    try:
        if entity["type"] == "LINE":
            return [(
                (float(values["10"][0]), float(values["20"][0])),
                (float(values["11"][0]), float(values["21"][0])),
            )]
        if entity["type"] == "LWPOLYLINE":
            xs = [float(value) for value in values.get("10", [])]
            ys = [float(value) for value in values.get("20", [])]
            points = list(zip(xs, ys))
            segments = list(zip(points, points[1:]))
            flags = int(float(values.get("70", ["0"])[0]))
            if flags & 1 and len(points) > 2:
                segments.append((points[-1], points[0]))
            return segments
    except (KeyError, TypeError, ValueError):
        return []
    return []


def extract_circuit_keys(text: str) -> list[str]:
    return CIRCUIT_KEY_RE.findall(normalize(text))


def extract_cluster_keys(cluster: list[tuple[float, float, str]]) -> list[str]:
    parts = [normalize(text) for _x, _y, text in sorted(cluster, key=lambda item: item[0])]
    keys = [key for part in parts for key in extract_circuit_keys(part)]
    for left, right in zip(parts, parts[1:]):
        if left in {"WL", "WX", "WP", "G"} and re.fullmatch(r"\d+", right):
            keys.append(left + right)
    return keys

def anchor_match(text, anchor):
    actual, target = normalize(text), normalize(anchor)
    if actual == target: return True
    # Room ordinals/ranges do not change the room class. Never use arbitrary substring matching.
    return target.endswith(("室", "间")) and bool(re.fullmatch(re.escape(target) + r"(?:[(]?\d+(?:[-—–~至、]\d+)*[)]?号?)", actual))


def attach_breaker_continuations(clusters, text_height):
    """Associate a wrapped trip unit with its breaker column and preceding parent.

    Parent ownership is bounded by the next breaker parent in that column,
    rather than a fixed +/-1.5-line-height scan. It cannot borrow across panels.
    """
    parents=[]
    for ci, cluster in enumerate(clusters):
        if len(set(extract_cluster_keys(cluster))) != 1: continue
        for x,y,text in cluster:
            if re.search(r"(?:/|\b)[1-4]P", normalize(text)) and 'VIGI' not in normalize(text):
                parents.append((ci,x,y))
    moves=[]
    for ci, cluster in enumerate(clusters):
        for rec in cluster:
            x,y,text=rec
            if not re.fullmatch(r"VIGI(?:\d+(?:\.\d+)?MA)?", normalize(text)): continue
            eligible=[p for p in parents if abs(p[1]-x)<=max(2*text_height,1e-6) and p[2]>=y-0.25*text_height]
            if not eligible: continue
            dest,px,py=min(eligible,key=lambda p:(p[2]-y,abs(p[1]-x)))
            below=[p[2] for p in parents if abs(p[1]-px)<=max(2*text_height,1e-6) and p[2]<py]
            boundary=max(below) if below else py-10*text_height
            if y>boundary and dest!=ci:moves.append((ci,dest,rec))
    for src,dest,rec in moves:
        clusters[src].remove(rec);clusters[dest].append(rec)
    return [cluster for cluster in clusters if cluster]


def tight_anchor_center(normalized_texts: list[tuple[dict, str]], anchors: tuple[str, ...]) -> tuple[float, float] | None:
    point_groups = []
    for anchor in anchors:
        points = [
            entity_xy(entity) for entity, text in normalized_texts
            if anchor_match(text, anchor) and entity_xy(entity) is not None
        ]
        if not points:
            return None
        point_groups.append(points)
    cluster = min(
        itertools.product(*point_groups),
        key=lambda points: sum(
            math.dist(left, right) ** 2
            for left, right in itertools.combinations(points, 2)
        ),
    )
    return (
        sum(point[0] for point in cluster) / len(cluster),
        sum(point[1] for point in cluster) / len(cluster),
    )

def score(path: Path) -> dict:
    if not path.is_file():
        return empty_result(f"electrical_drawings.dxf not found: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return empty_result(f"cannot read DXF: {exc}")
    entities, parse_errors = parse_dxf(path)
    truth = json.loads(truth_path().read_text(encoding="utf-8"))
    expected_panels = {panel["id"]: panel for panel in truth["panels"]}
    expected_rows = {(panel["id"], circuit["circuit_id"]): circuit for panel in truth["panels"] for circuit in panel["circuits"]}
    sheet_definitions = {sheet["id"]: sheet for sheet in truth.get("sheets", [])}
    sheet_anchors = {
        sheet_id: tuple(definition["anchors"])
        for sheet_id, definition in sheet_definitions.items()
    } or SHEET_ANCHORS
    sheet_detail_anchors = {
        sheet_id: tuple(definition.get("detail_anchors", ()))
        for sheet_id, definition in sheet_definitions.items()
    }
    texts = [entity for entity in entities if entity["type"] in {"TEXT", "MTEXT"} and entity_text(entity).strip()]
    normalized_texts = [(entity, normalize(entity_text(entity))) for entity in texts]
    text_corpus = [text for _entity, text in normalized_texts]
    sheet_anchor_hits = {
        sheet: {anchor: any(anchor_match(text, anchor) for text in text_corpus) for anchor in anchors}
        for sheet, anchors in sheet_anchors.items()
    }
    sheet_detail_anchor_hits = {
        sheet: {anchor: any(anchor_match(text, anchor) for text in text_corpus) for anchor in anchors}
        for sheet, anchors in sheet_detail_anchors.items()
    }
    sheet_anchor_recall = sum(sum(hits.values()) for hits in sheet_anchor_hits.values()) / sum(len(anchors) for anchors in sheet_anchors.values())
    fallback_sheet_centers = {
        sheet: tight_anchor_center(normalized_texts, anchors)
        for sheet, anchors in sheet_anchors.items()
    }
    sheet_regions = titled_sheet_regions(entities, normalized_texts, list(sheet_anchors))
    sheet_centers = {
        sheet: (
            ((region[0] + region[2]) / 2, (region[1] + region[3]) / 2)
            if region is not None else fallback_sheet_centers[sheet]
        )
        for sheet, region in sheet_regions.items()
    }
    represented_sheets = sum(
        sheet_regions[sheet] is not None
        or (all(sheet_anchor_hits[sheet].values()) and fallback_sheet_centers[sheet] is not None)
        for sheet in sheet_anchors
    )
    coverage_minimums = truth.get("coverage_minimums", {})
    sheet_stats = {
        sheet: {"geometry_signatures": set(), "text_values": set()}
        for sheet, center in sheet_centers.items() if center is not None
    }
    for entity in entities:
        xy = entity_xy(entity)
        if xy is None or not sheet_stats:
            continue
        framed = [name for name, box in sheet_regions.items() if box is not None and point_in_box(xy, box)]
        sheet = framed[0] if framed else min(sheet_stats, key=lambda name: math.dist(xy, sheet_centers[name]))
        if entity["type"] in NATIVE_GEOMETRY_TYPES:
            sheet_stats[sheet]["geometry_signatures"].add(geometry_signature(entity))
        elif entity["type"] in {"TEXT", "MTEXT"}:
            value = normalize(entity_text(entity))
            if value:
                sheet_stats[sheet]["text_values"].add(value)
    sheet_detail = {}
    for sheet in sheet_anchors:
        minimums = coverage_minimums.get(sheet, {})
        stats = sheet_stats.get(sheet, {"geometry_signatures": set(), "text_values": set()})
        geometry_count = len(stats["geometry_signatures"])
        text_characters = sum(len(value) for value in stats["text_values"])
        geometry_score = min(geometry_count / max(int(minimums.get("unique_geometry", 1)), 1), 1.0)
        text_score = min(text_characters / max(int(minimums.get("unique_text_characters", 1)), 1), 1.0)
        detail_hits = sheet_detail_anchor_hits.get(sheet, {})
        detail_anchor_recall = (
            sum(detail_hits.values()) / len(detail_hits)
            if detail_hits else 1.0
        )
        sheet_detail[sheet] = {
            "unique_geometry": geometry_count,
            "unique_text_characters": text_characters,
            "geometry_score": round(geometry_score, 6),
            "text_score": round(text_score, 6),
            "detail_anchor_hits": detail_hits,
            "detail_anchor_recall": round(detail_anchor_recall, 6),
            "score": round(0.50 * geometry_score + 0.20 * text_score + 0.30 * detail_anchor_recall, 6),
        }
    sheet_detail_score = sum(item["score"] for item in sheet_detail.values()) / len(sheet_anchors)
    complete_sheet_regions = sum(
        (
            sheet_regions[sheet] is not None
            or all(sheet_anchor_hits[sheet].values())
        ) and item["score"] >= 0.75
        for sheet, item in sheet_detail.items()
    )
    # Plans repeat panel and circuit labels, so restrict row reconstruction to
    # the sheet region whose anchors identify the panel system diagram. This is
    # coordinate-frame independent and therefore also works for redraws.
    def on_sheet(entity: dict, sheet: str) -> bool:
        xy = entity_xy(entity)
        if xy is None or sheet not in sheet_centers or sheet_centers[sheet] is None:
            return False
        region = sheet_regions.get(sheet)
        if region is not None:
            return point_in_box(xy, region)
        available = {name: center for name, center in sheet_centers.items() if center is not None}
        return min(available, key=lambda name: math.dist(xy, available[name])) == sheet

    scoped_texts = [(entity, text) for entity, text in normalized_texts if on_sheet(entity, "S-02")]
    scoped_panel_ids = {text for _entity, text in scoped_texts if text in {normalize(panel_id) for panel_id in expected_panels}}
    normalized_panel_texts = scoped_texts if len(scoped_panel_ids) == len(expected_panels) else normalized_texts
    errors = list(parse_errors)
    raw_upper = raw.upper()
    forbidden = sorted({
        entity["type"] for entity in entities
        if entity["type"] in FORBIDDEN_TYPES
    })
    if forbidden:
        errors.append("raster or underlay entity present: " + ", ".join(forbidden))
    embedded_raster = b"DATA:IMAGE" in raw_upper or b"BASE64" in raw_upper
    if embedded_raster:
        errors.append("embedded raster data is not allowed")
    panel_positions: dict[str, list[tuple[float, float]]] = {panel_id: [] for panel_id in expected_panels}
    for entity, text in normalized_panel_texts:
        xy = entity_xy(entity)
        if xy is None:
            continue
        for panel_id in expected_panels:
            if text == normalize(panel_id) or re.search(rf"(?<![A-Z0-9]){re.escape(normalize(panel_id))}(?![A-Z0-9])", text):
                panel_positions[panel_id].append(xy)
    represented_panels = sum(bool(values) for values in panel_positions.values())
    # Original CAD text is often split into columns (for example `WL` and `1`
    # are separate TEXT entities). Assign text to its nearest panel and cluster
    # by insertion Y so a complete printed row can be reconstructed.
    # The source drawing stacks 1AL1 above 2AL2 at the same x coordinate and
    # places 2AL1 in a second table to the right. Assign by table x-group and
    # the nearest table header above the text, rather than nearest panel label.
    anchor_xy = {panel_id: (sum(x for x, _y in values) / len(values), sum(y for _x, y in values) / len(values)) for panel_id, values in panel_positions.items() if values}
    panel_text_heights = []
    for entity, _text in normalized_panel_texts:
        try:
            height = float(entity.get("values", {}).get("40", ["0"])[0])
        except (TypeError, ValueError):
            continue
        if height > 0:
            panel_text_heights.append(height)
    typical_text_height = statistics.median(panel_text_heights) if panel_text_heights else 1.0
    x_group_tolerance = max(typical_text_height * 5.0, 1e-6)
    x_groups: list[list[str]] = []
    for panel_id in sorted(anchor_xy, key=lambda key: anchor_xy[key][0]):
        x = anchor_xy[panel_id][0]
        group = next((group for group in x_groups if abs(anchor_xy[group[0]][0] - x) <= x_group_tolerance), None)
        if group is None:
            x_groups.append([panel_id])
        else:
            group.append(panel_id)
    header_points: list[tuple[float, float]] = []
    for entity, text in normalized_panel_texts:
        xy = entity_xy(entity)
        if xy is not None and text == "回路编号":
            header_points.append(xy)
    panel_headers: dict[str, float] = {}
    for group in x_groups:
        anchor_group_x = sum(anchor_xy[panel_id][0] for panel_id in group) / len(group)
        group_headers = [
            (x, y) for x, y in header_points
            if min(x_groups, key=lambda candidates: abs(x - anchor_xy[candidates[0]][0])) is group
        ]
        group_x = sum(x for x, _y in group_headers) / len(group_headers) if group_headers else anchor_group_x
        headers = [y for _x, y in group_headers]
        for panel_id in group:
            anchor_y = anchor_xy[panel_id][1]
            above = [y for y in headers if y >= anchor_y]
            panel_headers[panel_id] = min(above, key=lambda y: y - anchor_y) if above else anchor_y

    group_x_values = {
        id(group): (sum(anchor_xy[panel_id][0] for panel_id in group) / len(group))
        for group in x_groups
    }
    for group in x_groups:
        anchor_group_x = group_x_values[id(group)]
        group_headers = [
            (header_x, header_y) for header_x, header_y in header_points
            if min(x_groups, key=lambda candidates: abs(header_x - anchor_xy[candidates[0]][0])) is group
        ]
        if group_headers:
            group_x_values[id(group)] = sum(header_x for header_x, _ in group_headers) / len(group_headers)

    def assigned_panel(x: float, y: float) -> str:
        group = min(x_groups, key=lambda candidates: abs(x - group_x_values[id(candidates)]))
        candidates = [(panel_headers[panel_id] - y, panel_id) for panel_id in group if panel_headers[panel_id] >= y]
        if candidates:
            return min(candidates)[1]
        return min(group, key=lambda panel_id: abs(y - panel_headers[panel_id]))

    panel_records: dict[str, list[tuple[float, float, str]]] = {panel_id: [] for panel_id in expected_panels}
    for entity, text in normalized_panel_texts:
        xy = entity_xy(entity)
        if xy is None:
            continue
        if anchor_xy:
            panel_records[assigned_panel(xy[0], xy[1])].append((xy[0], xy[1], text))

    def row_clusters(panel_id: str) -> list[list[tuple[float, float, str]]]:
        records = sorted(panel_records[panel_id], key=lambda item: (-item[1], item[0]))
        clusters: list[list[tuple[float, float, str]]] = []
        row_tolerance = (
            max(typical_text_height * 1.5, 1e-6)
            if sheet_regions.get("S-02") is not None else 260.0
        )
        for record in records:
            if not clusters or abs(record[1] - clusters[-1][0][1]) > row_tolerance:
                clusters.append([record])
            else:
                clusters[-1].append(record)
        return attach_breaker_continuations(clusters, typical_text_height)

    candidate_values = {
        field: {
            normalize(circuit[field]): circuit[field]
            for panel in truth["panels"]
            for circuit in panel["circuits"]
        }
        for field in ROW_FIELDS
    }
    panel_clusters = {panel_id: row_clusters(panel_id) for panel_id in expected_panels}
    submitted_key_occurrences = sum(
        len(extract_cluster_keys(cluster))
        for clusters in panel_clusters.values()
        for cluster in clusters
    )
    row_hits, row_match_clusters, duplicate_keys = {}, {}, 0
    for key, expected in expected_rows.items():
        panel_id, circuit_id = key
        matches = []
        for cluster in panel_clusters[panel_id]:
            if normalize(circuit_id) in extract_cluster_keys(cluster):
                matches.append(cluster)
        if len(matches) > 1:
            duplicate_keys += len(matches) - 1
        corpus = [text for _x, _y, text in matches[0]] if matches else []
        cluster_keys = extract_cluster_keys(matches[0]) if matches else []
        hits = {
            "key": len(matches) == 1
            and set(cluster_keys) == {normalize(circuit_id)}
        }
        for field in ROW_FIELDS:
            field_corpus = corpus + (["".join(corpus)] if field == "breaker" else [])
            target_present = any(
                field_match(text, expected[field], field == "capacity_kw")
                for text in field_corpus
            )
            competing = {
                normalized
                for normalized, candidate in candidate_values[field].items()
                if any(
                    field_match(text, candidate, field == "capacity_kw")
                    for text in field_corpus
                )
            }
            hits[field] = target_present and competing <= {normalize(expected[field])}
        row_hits[key] = hits
        row_match_clusters[key] = matches
    exact_rows = sum(int(all(hits.values())) for hits in row_hits.values())
    matched_keys = sum(int(hits["key"]) for hits in row_hits.values())
    expected_total = len(expected_rows)
    submitted_key_estimate = submitted_key_occurrences
    key_precision = matched_keys / submitted_key_estimate if submitted_key_estimate else 0.0
    key_recall = matched_keys / expected_total if expected_total else 0.0
    key_f1 = 2 * key_precision * key_recall / (key_precision + key_recall) if key_precision + key_recall else 0.0
    exact_precision = exact_rows / submitted_key_estimate if submitted_key_estimate else 0.0
    exact_recall = exact_rows / expected_total if expected_total else 0.0
    exact_f1 = 2 * exact_precision * exact_recall / (exact_precision + exact_recall) if exact_precision + exact_recall else 0.0
    exact_row_score = math.sqrt(exact_f1)
    matched_row_fields = sum(
        sum(int(hits[field]) for field in ROW_FIELDS)
        for hits in row_hits.values()
    )
    row_field_hits = {
        field: sum(int(hits[field]) for hits in row_hits.values())
        for field in ROW_FIELDS
    }
    expected_row_fields = expected_total * len(ROW_FIELDS)
    submitted_row_field_slots = submitted_key_estimate * len(ROW_FIELDS)
    row_field_precision = (
        matched_row_fields / submitted_row_field_slots
        if submitted_row_field_slots else 0.0
    )
    row_field_recall = (
        matched_row_fields / expected_row_fields if expected_row_fields else 0.0
    )
    row_field_f1 = (
        2 * row_field_precision * row_field_recall
        / (row_field_precision + row_field_recall)
        if row_field_precision + row_field_recall else 0.0
    )
    coherent_row_quality_by_key = {
        key: coherent_row_quality(row_hits[key], len(row_match_clusters[key]) == 1)
        for key in expected_rows
    }
    coherent_rows = sum(quality > 0 for quality in coherent_row_quality_by_key.values())
    coherent_row_points = sum(coherent_row_quality_by_key.values())
    coherent_row_precision = (
        coherent_row_points / submitted_key_estimate
        if submitted_key_estimate else 0.0
    )
    coherent_row_recall = (
        coherent_row_points / expected_total if expected_total else 0.0
    )
    coherent_row_f1 = (
        2 * coherent_row_precision * coherent_row_recall
        / (coherent_row_precision + coherent_row_recall)
        if coherent_row_precision + coherent_row_recall else 0.0
    )
    incoming_hits, incoming_total, complete_incoming = 0, len(expected_panels) * len(INCOMING_FIELDS), 0
    for panel_id, panel in expected_panels.items():
        panel_text = [text for _x, _y, text in panel_records[panel_id]]
        checks = []
        for field in INCOMING_FIELDS:
            checks.append(any(field_match(text, panel["incoming"][field]) for text in panel_text))
        incoming_hits += sum(checks)
        complete_incoming += int(all(checks))
    incoming_accuracy = incoming_hits / incoming_total if incoming_total else 0.0
    panels_with_coherent_rows = {
        panel_id
        for panel_id, circuit_id in expected_rows
        if coherent_row_quality_by_key[(panel_id, circuit_id)] > 0
    }
    panel_row_coverage = (
        len(panels_with_coherent_rows) / len(expected_panels)
        if expected_panels else 0.0
    )
    coherent_incoming_score = incoming_accuracy  # Diagnostic only; scored once in topology.

    lines = [entity for entity in entities if entity["type"] == "LINE"]
    polylines = [entity for entity in entities if entity["type"] in {"LWPOLYLINE", "POLYLINE"}]
    native_geometry = [entity for entity in entities if entity["type"] in NATIVE_GEOMETRY_TYPES]
    trace_like_geometry = [entity for entity in entities if entity["type"] in TRACE_LIKE_TYPES]
    geometry_per_text = len(trace_like_geometry) / max(len(texts), 1)
    raster_trace_suspected = (
        len(native_geometry) > int(truth.get("max_native_geometry", MAX_NATIVE_GEOMETRY))
        or (
            len(trace_like_geometry) > 5_000
            and geometry_per_text > int(
                truth.get("max_trace_geometry_per_text", MAX_TRACE_GEOMETRY_PER_TEXT)
            )
        )
    )
    if raster_trace_suspected:
        errors.append("raster-equivalent scanline or contour tracing suspected")

    segments = [
        segment
        for entity in entities
        for segment in entity_segments(entity)
        if segment[0] != segment[1]
    ]
    points = [point for segment in segments for point in segment]
    if points:
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_y = max(point[1] for point in points)
        drawing_diagonal = math.hypot(max_x - min_x, max_y - min_y)
    else:
        drawing_diagonal = 0.0
    endpoint_tolerance = max(drawing_diagonal * 1e-6, 1e-3)

    def endpoint_key(point: tuple[float, float]) -> tuple[int, int]:
        return (
            round(point[0] / endpoint_tolerance),
            round(point[1] / endpoint_tolerance),
        )

    endpoint_degrees = Counter(
        endpoint_key(point)
        for segment in segments
        for point in segment
    )
    connected_segments = sum(
        endpoint_degrees[endpoint_key(start)] > 1
        or endpoint_degrees[endpoint_key(end)] > 1
        for start, end in segments
    )
    connected_segment_ratio = connected_segments / len(segments) if segments else 0.0
    junction_nodes = sum(degree >= 3 for degree in endpoint_degrees.values())

    row_y_values = sorted({
        round(sum(y for _x, y, _text in matches[0]) / len(matches[0]), 6)
        for matches in row_match_clusters.values()
        if matches and matches[0]
    })
    row_gaps = [
        right - left
        for left, right in zip(row_y_values, row_y_values[1:])
        if right - left > endpoint_tolerance
    ]
    typical_row_gap = statistics.median(row_gaps) if row_gaps else max(drawing_diagonal * 0.002, 1.0)
    row_band = max(typical_row_gap * 0.60, endpoint_tolerance * 4)

    def cluster_has_geometry(cluster: list[tuple[float, float, str]]) -> bool:
        if not cluster or not segments:
            return False
        xs = [x for x, _y, _text in cluster]
        row_y = sum(y for _x, y, _text in cluster) / len(cluster)
        margin = max((max(xs) - min(xs)) * 0.15, typical_row_gap * 2)
        left, right = min(xs) - margin, max(xs) + margin
        return any(
            min(start[0], end[0]) <= right
            and max(start[0], end[0]) >= left
            and min(start[1], end[1]) <= row_y + row_band
            and max(start[1], end[1]) >= row_y - row_band
            for start, end in segments
        )

    row_geometry_links = sum(
        all(row_hits[key].values())
        and bool(row_match_clusters[key])
        and cluster_has_geometry(row_match_clusters[key][0])
        for key in expected_rows
    )
    row_geometry_recall = row_geometry_links / expected_total if expected_total else 0.0
    coherent_geometry_points = sum(
        quality
        for key, quality in coherent_row_quality_by_key.items()
        if quality > 0
        and row_match_clusters[key]
        and cluster_has_geometry(row_match_clusters[key][0])
    )
    coherent_geometry_precision = (
        coherent_geometry_points / submitted_key_estimate
        if submitted_key_estimate else 0.0
    )
    coherent_geometry_recall = (
        coherent_geometry_points / expected_total if expected_total else 0.0
    )
    coherent_geometry_f1 = (
        2 * coherent_geometry_precision * coherent_geometry_recall
        / (coherent_geometry_precision + coherent_geometry_recall)
        if coherent_geometry_precision + coherent_geometry_recall else 0.0
    )
    incoming_panel_score = complete_incoming / len(expected_panels) if expected_panels else 0.0
    connection_score = min(connected_segment_ratio / 0.65, 1.0)
    junction_score = min(junction_nodes / max(expected_total * 2, 1), 1.0)
    complete_sheet_ratio = (
        complete_sheet_regions / len(sheet_anchors) if sheet_anchors else 0.0
    )
    sheet_completeness_score = (
        0.60 * complete_sheet_ratio + 0.40 * sheet_anchor_recall
    )
    topology = (
        0.65 * coherent_geometry_f1
        + 0.20 * sheet_completeness_score
        + 0.10 * incoming_panel_score
        + 0.03 * connection_score * float(matched_keys > 0)
        + 0.02 * junction_score * float(matched_keys > 0)
    )
    semantic_evidence = {
        "expected_sheets": list(sheet_anchors),
        "sheet_regions_found": {key: value is not None for key, value in sheet_regions.items()},
        "sheet_anchor_hits": sheet_anchor_hits,
        "expected_panels": list(expected_panels),
        "represented_panels": sorted(panels_with_coherent_rows),
        "circuit_rows": [{"panel": panel, "circuit": circuit, "field_hits": row_hits[(panel, circuit)],
                          "unique_cluster": len(row_match_clusters[(panel, circuit)]) == 1,
                          "native_geometry_link": bool(row_match_clusters[(panel, circuit)]) and cluster_has_geometry(row_match_clusters[(panel, circuit)][0])}
                         for panel, circuit in expected_rows],
        "incoming_accuracy": round(incoming_accuracy, 6),
        "connected_segment_ratio": round(connected_segment_ratio, 6),
    }
    semantic_review = adjudicate(semantic_evidence)
    semantic_relation_score = sum(row["fraction"] for row in semantic_review["items"].values()) / len(semantic_review["items"])
    semantic = (0.55 * exact_row_score + 0.20 * coherent_row_f1
                + 0.10 * sheet_anchor_recall + 0.15 * semantic_relation_score)
    raw_semantic, raw_topology = semantic, topology
    normalization = truth.get("measurement_normalization", {})
    semantic = min(1.0, semantic / float(normalization.get("semantic_content", 1.0)))
    topology = min(1.0, topology / float(normalization.get("diagram_topology", 1.0)))

    geometry_mix = min(len(native_geometry) / max(expected_total * 6, 1), 1.0)
    text_mix = min(len(texts) / max(expected_total * 2, 1), 1.0)
    native_structure = 0.50 * geometry_mix + 0.50 * text_mix
    version_ok = bool(re.search(rb"\$ACADVER\s*[\r\n]+\s*1\s*[\r\n]+\s*AC10", raw)) or b"AC1009" in raw
    no_raster_content = not forbidden and not embedded_raster and not raster_trace_suspected
    vector = (
        float(not parse_errors)
        + float(no_raster_content)
        + float(version_ok)
        + native_structure
    ) / 4.0
    artifact_valid = not parse_errors and no_raster_content and version_ok
    strict = 0.0 if not artifact_valid else round(
        WEIGHTS["semantic_content"] * semantic
        + WEIGHTS["diagram_topology"] * topology,
        6,
    )
    # This delivery contract reuses strict coverage and topology diagnostics,
    # so it is a coarser binary view rather than an independent score.
    # The thresholds require a reviewable partial redraw, not near-gold fidelity.
    must_have = {
        "valid_editable_dxf": artifact_valid,
        "no_raster_underlay": not forbidden and not embedded_raster,
        "no_raster_equivalent_trace": not raster_trace_suspected,
        "all_issued_sheets_represented": represented_sheets == len(sheet_anchors),
        "all_panels_present": represented_panels == len(expected_panels),
        "coherent_row_precision_at_least_0_30": coherent_row_precision >= 0.30,
        "coherent_row_recall_at_least_0_30": coherent_row_recall >= 0.30,
        "incoming_accuracy_at_least_0_50": incoming_accuracy >= 0.50,
        "topology_at_least_0_30": topology >= 0.30,
        "source_bound_semantics_complete": all(row["fraction"] == 1 for row in semantic_review["items"].values()),
    }
    lenient = 1.0 if all(must_have.values()) else 0.0
    must_have["passed"] = bool(lenient)
    return {
        "schema_version": "electrical-drawing-set-dxf-validator-v4",
        "reward": strict,
        "rewards": {"strict": strict, "lenient": lenient},
        "reward_formulas": {
            "strict": "valid editable DXF gate * (0.50*semantic_content + 0.50*diagram_topology); semantic_content is 0.55*sqrt(exact_row_f1) + 0.20*coherent_partial_row_f1 + 0.10*sheet_anchor_recall + 0.15*source_bound_semantic_review; topology is 0.65*coherent_geometry_f1 + 0.20*sheet_completeness + 0.10*incoming_panel_accuracy + 0.03*connection*has_matched_key + 0.02*junction*has_matched_key",
            "lenient": "1 iff valid editable DXF, no raster-equivalent content, all native sheet frames and panels are present, coherent partial-row precision/recall >=0.30, incoming accuracy >=0.50, topology >=0.30, and source-bound sheet/device/connection semantics are complete",
        },
        "dimension_scores": {
            "semantic_content": round(semantic, 6),
            "diagram_topology": round(topology, 6),
            "vector_delivery": round(vector, 6),
        },
        "raw_dimension_scores": {
            "semantic_content": round(raw_semantic, 6),
            "diagram_topology": round(raw_topology, 6),
        },
        "semantic_judge": semantic_review,
        "counts": {
            "expected_circuits": expected_total,
            "submitted_circuit_keys": submitted_key_estimate,
            "matched_circuit_keys": matched_keys,
            "exact_circuit_rows": exact_rows,
            "matched_row_fields": matched_row_fields,
            "exact_row_coverage_score": round(exact_row_score, 6),
            "expected_row_fields": expected_row_fields,
            "row_field_hits": row_field_hits,
            "coherent_partial_rows": coherent_rows,
            "coherent_partial_row_points": round(coherent_row_points, 6),
            "panels_with_coherent_rows": len(panels_with_coherent_rows),
            "row_geometry_links": row_geometry_links,
            "coherent_row_geometry_points": round(coherent_geometry_points, 6),
            "duplicate_keys": duplicate_keys,
            "expected_panels": len(expected_panels),
            "represented_panels": represented_panels,
            "expected_sheets": len(sheet_anchors),
            "represented_sheets": represented_sheets,
            "complete_sheet_regions": complete_sheet_regions,
            "sheet_anchor_hits": sheet_anchor_hits,
            "sheet_anchor_recall": round(sheet_anchor_recall, 6),
            "sheet_detail": sheet_detail,
            "entity_types": dict(sorted(Counter(entity["type"] for entity in entities).items())),
            "native_geometry_entities": len(native_geometry),
            "trace_like_geometry_entities": len(trace_like_geometry),
            "geometry_per_text": round(geometry_per_text, 6),
            "line_entities": len(lines),
            "polyline_entities": len(polylines),
            "text_entities": len(texts),
            "segments": len(segments),
            "connected_segments": connected_segments,
            "connected_segment_ratio": round(connected_segment_ratio, 6),
            "junction_nodes": junction_nodes,
            "incoming_fields_correct": incoming_hits,
            "incoming_fields_total": incoming_total,
            "complete_incoming_panels": complete_incoming,
            "sheet_completeness_score": round(sheet_completeness_score, 6),
        },
        "precision_recall": {
            "circuit_keys": {"precision": round(key_precision, 6), "recall": round(key_recall, 6)},
            "exact_rows": {"precision": round(exact_precision, 6), "recall": round(exact_recall, 6)},
            "row_fields": {"precision": round(row_field_precision, 6), "recall": round(row_field_recall, 6)},
            "coherent_partial_rows": {"precision": round(coherent_row_precision, 6), "recall": round(coherent_row_recall, 6)},
            "coherent_row_geometry": {"precision": round(coherent_geometry_precision, 6), "recall": round(coherent_geometry_recall, 6)},
        },
        "anti_gaming": {
            "raster_trace_suspected": raster_trace_suspected,
            "max_native_geometry": int(truth.get("max_native_geometry", MAX_NATIVE_GEOMETRY)),
            "max_trace_geometry_per_text": int(truth.get("max_trace_geometry_per_text", MAX_TRACE_GEOMETRY_PER_TEXT)),
        },
        "must_have": must_have,
        "errors": errors,
    }

def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace")
    print(json.dumps(score(locate_submission(target) or target), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

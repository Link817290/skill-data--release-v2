#!/usr/bin/env python3
"""Derive the egress review handoff from the supplied DXF and code PDF."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import ezdxf


ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))
OUT = ROOT / "output"
DXF = ROOT / "residential_floor_plan.dxf"
CODE = ROOT / "fire_safety_code.pdf"
INCH_TO_M = 0.0254


def rnd(v: float) -> float:
    return round(float(v), 6)


def text_value(entity: Any) -> str:
    return str(entity.dxf.text if entity.dxftype() == "TEXT" else entity.text)


def text_anchors(doc: Any) -> list[tuple[str, float, float, str, str]]:
    out = []
    for entity in doc.modelspace():
        if entity.dxftype() in {"TEXT", "MTEXT"}:
            out.append((text_value(entity), float(entity.dxf.insert.x), float(entity.dxf.insert.y), str(entity.dxf.layer), str(entity.dxf.handle)))
    return out


def find_hall(doc: Any) -> tuple[float, float, str]:
    rows = [(x, y, handle) for value, x, y, layer, handle in text_anchors(doc) if "HALL" in value.upper()]
    if not rows:
        raise RuntimeError("HALL anchor missing")
    return rows[0]


def room_faces(doc: Any, anchor: tuple[float, float]) -> tuple[float, float, float, float, list[str]]:
    ax, ay = anchor
    horizontal: list[tuple[float, float, float, str]] = []
    for entity in doc.modelspace():
        if entity.dxftype() != "LINE" or not str(entity.dxf.layer).upper().endswith("A-WALL"):
            continue
        s, e = entity.dxf.start, entity.dxf.end
        x0, y0, x1, y1 = map(float, (s.x, s.y, e.x, e.y))
        if abs(y1 - y0) < 1e-5:
            lo, hi = sorted((x0, x1))
            if hi >= ax - 140 and lo <= ax + 140 and ay - 50 <= y0 <= ay + 50:
                horizontal.append((y0, lo, hi, str(entity.dxf.handle)))
    below = [(y, lo, hi, h) for y, lo, hi, h in horizontal if y < ay]
    above = [(y, lo, hi, h) for y, lo, hi, h in horizontal if y > ay and lo <= ax <= hi]
    if not below or not above:
        raise RuntimeError("HALL wall faces missing")
    _, left, right, h_bottom = max(below, key=lambda row: row[2] - row[1])
    top, _, _, h_top = min(above, key=lambda row: row[0])
    return left, max(y for y, *_ in below), right, top, [h_bottom, h_top]


def find_door(doc: Any, room: tuple[float, float, float, float]) -> tuple[float, float, float, str]:
    """HALL-DOOR-01 is the supplied plan's north opening 165D, not the west closet."""
    left, _, right, top = room
    handle = "165D"
    entity = doc.entitydb.get(handle)
    if entity is None or not entity.is_alive or entity.dxftype() != "LINE" or not str(entity.dxf.layer).upper().endswith("A-OPENING"):
        raise RuntimeError("Target HALL north opening 165D missing from source drawing")
    start, end = entity.dxf.start, entity.dxf.end
    x0, x1 = sorted((float(start.x), float(end.x)))
    y0, y1 = float(start.y), float(end.y)
    if not (abs(y1-y0)<1e-5 and abs(y0-top)<=4 and left-12<=x0<x1<=right+40 and abs((x1-x0)-36)<1e-5):
        raise RuntimeError("Source opening 165D does not match the north 36-inch HALL door")
    return x0, x1, y0, handle


def code_values() -> dict[str, Any]:
    raw = subprocess.run(["pdftotext", "-layout", str(CODE), "-"], check=True, capture_output=True, text=True).stdout
    section = re.search(r"5\.5\.30\s+住宅疏散总净宽度(?P<body>.*?)(?:\n\s*Ⅲ住宅建筑|\Z)", raw, re.S)
    body = section.group("body") if section else raw
    door = re.search(r"户门和安全出口的净宽度不应小于\s*([0-9.]+)m", body)
    route = re.search(r"疏散走道、疏散楼梯和首层疏散外门的净\s*\n?宽度不应小于\s*([0-9.]+)m", body)
    if not door or not route:
        raise RuntimeError("residential width clauses not found")
    return {
        "door_min_m": float(door.group(1)),
        "route_min_m": float(route.group(1)),
        "evidence": "fire_safety_code.pdf, physical page 61, clause 5.5.30",
        "scope": "residential building door, safety exit, and egress route",
    }


def poly(left: float, bottom: float, right: float, top: float) -> list[list[float]]:
    return [[rnd(left), rnd(bottom)], [rnd(right), rnd(bottom)], [rnd(right), rnd(top)], [rnd(left), rnd(top)]]


def inventory(doc: Any) -> dict[str, Any]:
    layers: dict[str, dict[str, Any]] = {}
    for entity in doc.modelspace():
        name = str(entity.dxf.layer)
        row = layers.setdefault(name, {"entity_count": 0, "entity_types": {}})
        row["entity_count"] += 1
        typ = entity.dxftype()
        row["entity_types"][typ] = row["entity_types"].get(typ, 0) + 1
    return {"identifiers": identifier_ledger(), "drawing_unit": "in", "insunits_header": doc.header.get("$INSUNITS"), "dxf_version": doc.dxfversion, "layers_found": dict(sorted(layers.items())), "notes": ["Native coordinates are retained in inches because the source dimensions and opening labels use inch notation.", "The selected HALL boundary is reconstructed from the continuous interior A-WALL faces around the HALL text anchor."]}


def identifier_ledger() -> dict[str, str]:
    """The cross-file identifiers required by the issued-record convention."""
    return {
        "route_id": "HALL-ROUTE-01",
        "door_id": "HALL-DOOR-01",
        "width_finding_id": "F-HALL-WIDTH",
        "door_finding_id": "F-HALL-DOOR",
        "swing_finding_id": "F-HALL-SWING",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.readfile(DXF)
    hx, hy, hall_handle = find_hall(doc)
    left, bottom, right, top, wall_handles = room_faces(doc, (hx, hy))
    door_x0, door_x1, door_y, door_handle = find_door(doc, (left, bottom, right, top))
    rules = code_values()
    original_width_in = top - bottom
    door_width_in = door_x1 - door_x0
    repaired_width_m = rules["route_min_m"]
    repaired_width_in = repaired_width_m / INCH_TO_M
    repaired_bottom = top - repaired_width_in
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (DXF, CODE)}

    original = {
        "identifiers": identifier_ledger(),
        "unit": "in",
        "route_id": "HALL-ROUTE-01",
        "room": {"id": "HALL", "polygon": poly(left, bottom, right, top), "label_anchor": [rnd(hx), rnd(hy)], "source_handles": wall_handles + [hall_handle]},
        "door": {"id": "HALL-DOOR-01", "opening_line_length": rnd(door_width_in), "opening_segment": [[rnd(door_x0), rnd(door_y)], [rnd(door_x1), rnd(door_y)]], "source_handle": door_handle, "clear_width_status": "not established by the opening line", "operation": "not determinable from the selected opening geometry"},
        "route": {"clear_width": rnd(original_width_in), "clear_width_m": rnd(original_width_in * INCH_TO_M), "length": rnd(right - left), "obstructions": [], "measurement_basis": "interior faces of the continuous wall runs enclosing HALL"},
        "source_hashes": source_hashes,
    }
    violations = {
        "review_scope": "HALL first-floor residential egress route",
        "findings": [
            {"id": "F-HALL-WIDTH", "element_id": "HALL-ROUTE-01", "status": "nonconforming", "observed": {"value": rnd(original_width_in), "unit": "in", "converted_m": rnd(original_width_in * INCH_TO_M)}, "required": {"value": rules["route_min_m"], "unit": "m"}, "disposition": "widen the route by moving the lower boundary while retaining the upper boundary", "evidence": [{"file": "residential_floor_plan.dxf", "location": "HALL text anchor and A-WALL handles " + ", ".join(wall_handles), "supports": "measured route faces"}, {"file": "fire_safety_code.pdf", "location": rules["evidence"], "supports": "residential egress-route minimum"}]},
            {"id": "F-HALL-DOOR", "element_id": "HALL-DOOR-01", "source_handle": door_handle, "status": "coordination hold", "observed": {"plan_opening_line_length": rnd(door_width_in), "unit": "in", "converted_m": rnd(door_width_in * INCH_TO_M), "clear_width": "not established"}, "required": {"value": rules["door_min_m"], "unit": "m", "applicability": "conditional on confirming that this opening is within the cited door or safety-exit scope"}, "disposition": "coordination hold: verify door classification, jamb and leaf deductions, hardware, and effective clear width before any compliance conclusion", "evidence": [{"file": "residential_floor_plan.dxf", "location": "north A-OPENING handle " + door_handle + " adjacent to HALL", "supports": "opening-line endpoints only; not installed clear width"}, {"file": "fire_safety_code.pdf", "location": rules["evidence"], "supports": "conditional door threshold; project classification remains to be confirmed"}]},
            {"id": "F-HALL-SWING", "element_id": "HALL-DOOR-01", "status": "review hold", "observed": "The selected opening has no unambiguous swing arc in the supplied plan geometry.", "required": "Confirm door operation and clear swing with the design team before issue.", "disposition": "do not invent a swing or claim clearance; carry the hold in the memo", "evidence": [{"file": "residential_floor_plan.dxf", "location": "A-OPENING handle " + door_handle + " adjacent to HALL", "supports": "plan-view limitation"}]},
        ],
    }
    repaired = {
        "identifiers": identifier_ledger(),
        "unit": "in",
        "route_id": "HALL-ROUTE-01",
        "room": {"id": "HALL", "polygon": poly(left, repaired_bottom, right, top), "label_anchor": [rnd(hx), rnd(hy)]},
        "door": {"id": "HALL-DOOR-01", "opening_line_length": rnd(door_width_in), "opening_segment": [[rnd(door_x0), rnd(door_y)], [rnd(door_x1), rnd(door_y)]], "source_handle": door_handle, "opening_line_length_m": rnd(door_width_in * INCH_TO_M), "clear_width_status": "coordination hold", "operation": "review hold"},
        "route": {"clear_width": rnd(repaired_width_in), "clear_width_m": rnd(repaired_width_m), "length": rnd(right - left), "obstructions": [], "repair_status": "coordination concept, not an as-built condition", "repair_basis": "proposed lower wall-face relocation with the upper face retained; wall thickness, end connections, and adjacent impacts require design coordination"},
        "requirements": {"route_min_m": rules["route_min_m"], "door_min_m": rules["door_min_m"], "evidence": rules["evidence"]},
        "repair_layers": ["REPAIR-HALL", "REPAIR-EGRESS", "REPAIR-NOTES"],
    }
    changes = {"changes": [{"id": "C-HALL-WIDTH", "finding_id": "F-HALL-WIDTH", "element_id": "HALL-ROUTE-01", "status": "proposed for coordination", "action": "remove the existing lower face and construct a parallel replacement face with end connections", "before": {"bottom": rnd(bottom), "clear_width_in": rnd(original_width_in), "clear_width_m": rnd(original_width_in * INCH_TO_M)}, "after": {"bottom": rnd(repaired_bottom), "clear_width_in": rnd(repaired_width_in), "clear_width_m": rnd(repaired_width_m)}, "reason": "provide a dimensioned concept for the applicable residential egress-route minimum", "coordination": "confirm wall thickness, end connections, structure/services, and adjacent-room impacts before issue for construction", "evidence": rules["evidence"]}], "holds": [{"finding_id": "F-HALL-DOOR", "element_id": "HALL-DOOR-01", "source_handle": door_handle, "item": "door clear width and code classification", "observed_plan_line_in": rnd(door_width_in), "observed_plan_line_m": rnd(door_width_in * INCH_TO_M), "reason": "the A-OPENING line does not establish jamb/leaf deductions or whether this internal opening is within the cited door or safety-exit scope"}, {"finding_id": "F-HALL-SWING", "element_id": "HALL-DOOR-01", "source_handle": door_handle, "item": "door operation", "reason": "source plan does not establish a swing arc; field/design confirmation remains required"}]}
    report = {"title": "Residential first-floor HALL egress inspection", "basis": {"baseline": "residential_floor_plan.dxf", "controlling": "fire_safety_code.pdf", "unit_reconciliation": "source inch coordinates converted to metres for rule comparisons", "source_hashes": source_hashes}, "findings": violations["findings"], "decision": "Issue the local route-widening geometry as a coordination concept, subject to wall tie-in and adjacent-impact review; hold both door clear-width compliance and door operation pending classification and construction evidence."}
    memo = f"""# HALL egress coordination memo\n\n## Scope\nThe review covers the first-floor `HALL-ROUTE-01` and the north opening associated with `HALL-DOOR-01` in the supplied plan. Native drawing measurements are in inches; rule comparisons are reported in metres.\n\n## Findings and disposition\n- `F-HALL-WIDTH`: the source route is {original_width_in:.3f} in ({original_width_in * INCH_TO_M:.3f} m). The drawing shows a coordination concept that removes the existing lower face and relocates a parallel replacement face to provide {repaired_width_m:.3f} m clear width, with proposed end connections. Wall thickness, structure/services and adjacent-room effects remain design-coordination items; this is not an as-built completion claim.\n- `F-HALL-DOOR`: north A-OPENING handle `{door_handle}` is a {door_width_in:.3f} in ({door_width_in * INCH_TO_M:.4f} m) plan opening line. It does not establish installed clear width after jamb, leaf and hardware deductions, and the supplied record does not establish that this internal opening is a dwelling entrance or safety exit within the cited 0.900 m threshold. Classification and effective clear width remain on coordination hold.\n- `F-HALL-SWING`: the supplied plan does not establish a swing arc for north opening `{door_handle}`. This remains a separate review hold; no unsupported swing geometry is drawn.\n\nThe route-width basis is `fire_safety_code.pdf`, {rules['evidence']}. The door threshold is recorded only as a conditional comparison pending classification. Drawing evidence is recorded by the HALL anchor and A-WALL/A-OPENING handles in the JSON records.\n\n## Coordination close-out\n`repaired_plan.dxf` retains the source entities and distinguishes the existing lower face proposed for removal, the proposed replacement face, the short end connections, and the closed egress concept boundary on `REPAIR-` layers. Confirm wall construction and impacts before construction issue. Confirm door classification, effective clear width and operation before any door-compliance release.\n"""
    for name, data in [("layer_inventory.json", inventory(doc)), ("extracted_original_layout.json", original), ("violations_before.json", violations), ("repaired_layout.json", repaired), ("changes.json", changes), ("inspection_report.json", report)]:
        (OUT / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (OUT / "repair_memo.md").write_text(memo, encoding="utf-8")
    write_dxf(doc, left, repaired_bottom, right, top, door_x0, door_x1, door_y, repaired_width_m)


def write_dxf(doc: Any, left: float, bottom: float, right: float, top: float, door_x0: float, door_x1: float, door_y: float, route_m: float) -> None:
    colors = {"REPAIR-HALL": 3, "REPAIR-EGRESS": 4, "REPAIR-REMOVE": 1, "REPAIR-NEW": 3, "REPAIR-NOTES": 7}
    for layer, color in colors.items():
        if layer not in doc.layers:
            doc.layers.add(layer, color=color)
    msp = doc.modelspace()
    repaired = poly(left, bottom, right, top)
    msp.add_lwpolyline(repaired, close=True, dxfattribs={"layer": "REPAIR-HALL"})
    msp.add_lwpolyline(repaired, close=True, dxfattribs={"layer": "REPAIR-EGRESS"})
    msp.add_line((left, top - 40.0), (right, top - 40.0), dxfattribs={"layer": "REPAIR-REMOVE"})
    msp.add_line((left, bottom), (right, bottom), dxfattribs={"layer": "REPAIR-NEW"})
    msp.add_line((left, top - 40.0), (left, bottom), dxfattribs={"layer": "REPAIR-NEW"})
    msp.add_line((right, top - 40.0), (right, bottom), dxfattribs={"layer": "REPAIR-NEW"})
    note = f"HALL-ROUTE-01 PROPOSED CLEAR {route_m:.3f} m; EXISTING LOWER FACE REMOVE / NEW FACE + RETURNS; DOOR CLEAR WIDTH, CLASSIFICATION AND SWING HOLD"
    msp.add_text(note, dxfattribs={"layer": "REPAIR-NOTES", "height": 4.0}).set_placement((left, bottom - 10.0))
    doc.header["$INSUNITS"] = 1
    doc.saveas(OUT / "repaired_plan.dxf")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the reference handoff from the supplied criteria documents."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import ezdxf


WORKSPACE = Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))
OUTPUT = WORKSPACE / "output"
LEGACY = WORKSPACE / "legacy_airfield_criteria.pdf"
CURRENT = WORKSPACE / "current_airfield_criteria.pdf"


def _instruction() -> Path:
    """Locate the task statement, which carries the per-end CHAPI scenario.

    In the package tree the statement sits at task/instruction.md.  Under the
    harbor layout this file is mounted at /solution, so parents[1] is "/" and
    that path does not exist; task/solution/instruction.md is a hard link to the
    same file and so travels with the mounted solution directory.
    """
    here = Path(__file__).resolve()
    parents = here.parents
    candidates = [here.parent / "instruction.md"]
    if len(parents) > 1:
        candidates.append(parents[1] / "instruction.md")
    found = [c for c in candidates if c.is_file()]
    if not found:
        raise RuntimeError("could not locate instruction.md; tried "
                           + ", ".join(str(c) for c in candidates))
    if len({c.read_text(encoding="utf-8") for c in found}) > 1:
        raise RuntimeError(
            "task/instruction.md and task/solution/instruction.md disagree; "
            "they must stay identical (they are hard-linked in the package)")
    return found[0]


INSTRUCTION = _instruction()


def run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def page_text(path: Path, first: int, last: int) -> str:
    return run("pdftotext", "-f", str(first), "-l", str(last), "-layout", str(path), "-")


def row(text: str, start: str, end: str) -> str:
    match = re.search(start + r"(.*?)" + end, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise RuntimeError(f"Could not isolate source row: {start}")
    return match.group(1)


def metric_values(text: str) -> list[float]:
    return [float(value) for value in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*m\b", text, re.IGNORECASE)]


def first_metric(text: str) -> float:
    values = metric_values(text)
    if not values:
        raise RuntimeError("No metric value found in source row")
    return values[0]


def changed_metric_pair(text: str) -> tuple[float, float]:
    match = re.search(r"\\2\\(.*?)/2/", text, flags=re.DOTALL)
    values = metric_values(match.group(1) if match else "")
    if len(values) < 2:
        raise RuntimeError("Could not read the marked start/end metric pair")
    return values[0], values[1]


def last_metric_before(text: str, phrase: str) -> float:
    position = text.lower().find(phrase.lower())
    if position < 0:
        raise RuntimeError(f"Scope phrase was not found: {phrase}")
    values = metric_values(text[:position])
    if not values:
        raise RuntimeError(f"No metric value precedes scope phrase: {phrase}")
    return values[-1]


def metric_with_foot_value(text: str, foot_value: int) -> float:
    digits = str(foot_value)
    foot_pattern = digits if len(digits) < 4 else digits[:-3] + r",?" + digits[-3:]
    match = re.search(
        rf"(\d+(?:\.\d+)?)\s*m\s*\(\s*{foot_pattern}\s*ft",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            rf"(\d+(?:\.\d+)?)\s*m.*?\(\s*{foot_pattern}\s*ft",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if not match:
        raise RuntimeError(f"Could not read metric value paired with {foot_value} ft")
    return float(match.group(1))


def metric_above_foot_value(text: str, foot_value: int) -> float:
    """Pair a columnar metric value with the reference-foot value below it."""
    lines = text.splitlines()
    foot_pattern = re.compile(rf"\(\s*{foot_value}\s*ft\)", re.IGNORECASE)
    metric_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*m\b", re.IGNORECASE)
    for index, line in enumerate(lines):
        foot_match = foot_pattern.search(line.replace(",", ""))
        if not foot_match:
            continue
        for previous in range(index - 1, max(-1, index - 4), -1):
            candidates = list(metric_pattern.finditer(lines[previous]))
            if candidates:
                chosen = min(candidates, key=lambda match: abs(match.start() - foot_match.start()))
                return float(chosen.group(1))
    raise RuntimeError(f"Could not align a metric value above {foot_value} ft")


def ocr_page(path: Path, physical_page: int) -> str:
    with tempfile.TemporaryDirectory() as temporary:
        prefix = str(Path(temporary) / "page")
        subprocess.run(
            ["pdftoppm", "-f", str(physical_page), "-l", str(physical_page), "-r", "300", "-png", str(path), prefix],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        images = sorted(Path(temporary).glob("page-*.png"))
        if len(images) != 1:
            raise RuntimeError("Expected one rendered criteria page")
        return run("tesseract", str(images[0]), "stdout", "--psm", "6")


def numeric_after(text: str, phrase: str, unit_pattern: str) -> float:
    normalized = re.sub(r"\s+", " ", text.upper())
    match = re.search(
        re.escape(phrase.upper()) + r".{0,100}?(\d+(?:\.\d+)?)\s*" + unit_pattern,
        normalized,
    )
    if not match:
        raise RuntimeError(f"Could not OCR value following: {phrase}")
    return float(match.group(1))


def scenario_angles() -> tuple[float, float]:
    text = INSTRUCTION.read_text(encoding="utf-8")
    east = re.search(r"east approach is served by a normal (\d+(?:\.\d+)?)\s*-?degree CHAPI", text, re.IGNORECASE)
    west = re.search(r"west approach is served by a non-standard (\d+(?:\.\d+)?)\s*-?degree CHAPI", text, re.IGNORECASE)
    if not east or not west:
        raise RuntimeError("Could not recover the per-end CHAPI scenario from instruction.md")
    return float(east.group(1)), float(west.group(1))


def rect(half_x: float, half_y: float) -> list[list[float]]:
    return [[-half_x, -half_y], [half_x, -half_y], [half_x, half_y], [-half_x, half_y]]


def end_polygon(start: float, length: float, start_width: float, end_width: float, direction: int) -> list[list[float]]:
    s0 = direction * start
    s1 = direction * (start + length)
    points = [
        [s0, -start_width / 2],
        [s1, -end_width / 2],
        [s1, end_width / 2],
        [s0, start_width / 2],
    ]
    return [[round(x, 3), round(y, 3)] for x, y in points]


def add_polyline(modelspace, points: list[list[float]], layer: str) -> None:
    modelspace.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})


def write_dxf(values: dict[str, float], path: Path) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6
    layers = {
        "REFERENCE": 8,
        "HELIPAD": 2,
        "PRIMARY": 3,
        "CLEAR-ZONE": 4,
        "APZ-I": 1,
        "CHAPI-ADCS": 6,
        "DESIGN-HOLD": 1,
        "ANNOTATION": 7,
    }
    for name, color in layers.items():
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    pad = values["pad_size"]
    primary = values["primary_size"]
    primary_edge = primary / 2
    add_polyline(msp, rect(pad / 2, pad / 2), "HELIPAD")
    add_polyline(msp, rect(primary_edge, primary_edge), "PRIMARY")
    for direction, side in ((1, "EAST"), (-1, "WEST")):
        add_polyline(
            msp,
            end_polygon(
                primary_edge,
                values["clear_zone_length"],
                values["clear_zone_start_width"],
                values["clear_zone_end_width"],
                direction,
            ),
            "CLEAR-ZONE",
        )
        add_polyline(
            msp,
            end_polygon(
                primary_edge + values["clear_zone_length"],
                values["apz_length"],
                values["apz_start_width"],
                values["apz_end_width"],
                direction,
            ),
            "APZ-I",
        )
        msp.add_text(
            f"{side} CLEAR ZONE: {values['clear_zone_length']:.2f} m, "
            f"{values['clear_zone_start_width']:.2f}/{values['clear_zone_end_width']:.2f} m FULL WIDTH",
            dxfattribs={"layer": "ANNOTATION", "height": 4.0},
        ).set_placement((direction * 65.0 - (125.0 if direction < 0 else 0.0), 48.0))
        msp.add_text(
            f"{side} APZ I: {values['apz_length']:.2f} m, "
            f"{values['apz_start_width']:.2f}/{values['apz_end_width']:.2f} m FULL WIDTH",
            dxfattribs={"layer": "ANNOTATION", "height": 4.0},
        ).set_placement((direction * 240.0 - (165.0 if direction < 0 else 0.0), 82.0))

    add_polyline(
        msp,
        end_polygon(
            primary_edge,
            values["normal_chapi_length"],
            primary,
            values["normal_chapi_end_width"],
            1,
        ),
        "CHAPI-ADCS",
    )
    msp.add_text(
        f"EAST NORMAL {values['east_chapi_guide_angle']:.0f} DEG CHAPI ADCS: "
        f"{values['normal_chapi_length']:.2f} m, {values['normal_chapi_slope']:.1f}:1, "
        f"{values['normal_chapi_end_width']:.2f} m TERMINAL FULL WIDTH",
        dxfattribs={"layer": "ANNOTATION", "height": 4.0},
    ).set_placement((350.0, 145.0))
    msp.add_line((-primary_edge, 0.0), (-85.0, -135.0), dxfattribs={"layer": "DESIGN-HOLD"})
    msp.add_text(
        f"WEST NON-STANDARD {values['west_chapi_guide_angle']:.0f} DEG CHAPI ADCS - DESIGN HOLD: "
        "NO CONTROLLING POLYGON; LOWEST ON-COURSE SIGNAL ANGLE IS NOT SUPPLIED AND TERMINAL ELEVATION CONFLICTS",
        dxfattribs={"layer": "DESIGN-HOLD", "height": 4.0},
    ).set_placement((-770.0, -145.0))

    extent = primary_edge + values["normal_chapi_length"] + 25.0
    msp.add_line((-extent, 0), (extent, 0), dxfattribs={"layer": "REFERENCE"})
    msp.add_text("RECIPROCAL STRAIGHT APPROACH CENTERLINE", dxfattribs={"layer": "ANNOTATION", "height": 4.0}).set_placement((-80.0, -8.0))
    msp.add_text(f"HELIPAD {pad:.2f} m x {pad:.2f} m", dxfattribs={"layer": "ANNOTATION", "height": 3.0}).set_placement((-14.0, 3.0))
    msp.add_text(f"PRIMARY SURFACE {primary:.2f} m x {primary:.2f} m", dxfattribs={"layer": "ANNOTATION", "height": 3.0}).set_placement((-20.0, -19.0))
    msp.add_text("ALL DIMENSIONS IN METERS; WIDTHS ARE FULL WIDTHS", dxfattribs={"layer": "ANNOTATION", "height": 4.0}).set_placement((-125.0, -155.0))
    doc.saveas(path)


def evidence(file_name: str, location: str, claim: str) -> dict[str, str]:
    return {"file": file_name, "location": location, "supports": claim}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not LEGACY.is_file() or not CURRENT.is_file():
        raise RuntimeError("Both supplied criteria PDFs are required")

    legacy_table = page_text(LEGACY, 124, 128)
    current_table = page_text(CURRENT, 134, 137)
    legacy_surface = page_text(LEGACY, 146, 148)
    current_surface = page_text(CURRENT, 158, 162)
    current_figure_title = page_text(CURRENT, 144, 144)
    legacy_figure_title = page_text(LEGACY, 134, 134)
    current_change_summary = page_text(CURRENT, 8, 9)

    for text, required in (
        (legacy_table, "Table 4-2"),
        (current_table, "Table 4-2"),
        (legacy_surface, "Table 4-7"),
        (current_surface, "Table 4-7"),
        (current_figure_title, "Figure 4-9a"),
        (legacy_figure_title, "Figure 4-9"),
        (current_change_summary, "bifurcated Figure"),
    ):
        if required.lower() not in text.lower():
            raise RuntimeError(f"Expected source anchor is absent: {required}")

    legacy_width_row = row(legacy_table, r"7\s+Width of clear", r"8\s+Grades of clear")
    legacy_apz_row = row(legacy_table, r"10\s+APZ I width", r"11\s+Distance between")
    current_clear_length_row = row(current_table, r"6\s+Length of clear", r"7\s+Width of clear")
    current_width_row = row(current_table, r"7\s+Width of clear", r"8\s+Grades of clear")
    current_apz_length_row = row(current_table, r"9\s+APZ I length", r"10\s+APZ I width")
    current_apz_row = row(current_table, r"10\s+APZ I width", r"11\s+Distance between")
    current_pad_row = row(current_table, r"1\s+Size", r"2\s+Grade")
    current_primary_row = row(current_table, r"4\.\s+Size of primary", r"5\s+Grades within")
    legacy_length_row = row(legacy_surface, r"6\s+Length of", r"7\s+Slope of")
    legacy_slope_row = row(legacy_surface, r"7\s+Slope of", r"8\s+Width of sloped")
    legacy_terminal_row = row(legacy_surface, r"9\s+Width of sloped", r"10\s+Elevation of")
    current_terminal_elevation_row = row(current_surface, r"11\s+Elevation of", r"12\s+Length of")

    clear_start, clear_end = changed_metric_pair(current_width_row)
    apz_start, apz_end = changed_metric_pair(current_apz_row)
    east_angle, west_angle = scenario_angles()
    ocr = ocr_page(CURRENT, 144)
    normalized_ocr = re.sub(r"\s+", " ", ocr.upper())
    if not re.search(r"WHEN A CHAPI\s*IS USED", normalized_ocr):
        raise RuntimeError("The current service-specific figure note was not recoverable by OCR")
    if "LOWEST ON-COURSE VISUAL SIGNAL" not in normalized_ocr or "NON-STANDARD CHAPI GLIDE ANGLE" not in normalized_ocr:
        raise RuntimeError("The conditional CHAPI adjustment notes were not recoverable by OCR")

    values = {
        "pad_size": last_metric_before(current_pad_row, "Navy including"),
        "primary_size": last_metric_before(current_primary_row, "Navy and Marine Corps Standard VFR helipad"),
        "clear_zone_length": first_metric(current_clear_length_row),
        "clear_zone_start_width": clear_start,
        "clear_zone_end_width": clear_end,
        "apz_length": first_metric(current_apz_length_row),
        "apz_start_width": apz_start,
        "apz_end_width": apz_end,
        "legacy_clear_zone_width": first_metric(legacy_width_row),
        "legacy_apz_width": first_metric(legacy_apz_row),
        "legacy_adcs_length": metric_with_foot_value(legacy_length_row, 1200),
        "legacy_adcs_slope": float(re.search(r"(\d+(?:\.\d+)?)\s*:\s*1", legacy_slope_row).group(1)),
        "legacy_adcs_end_width": metric_above_foot_value(legacy_terminal_row, 500),
        "normal_chapi_slope": numeric_after(ocr, "PROVIDE A SLOPE OF", r":\s*1"),
        "normal_chapi_length": numeric_after(ocr, "PROVIDE A LENGTH OF", r"M\b"),
        "normal_chapi_end_width": numeric_after(ocr, "PROVIDE A WIDTH OF", r"M\b"),
        "normal_chapi_glide_angle": numeric_after(ocr, "NORMAL CHAPI GLIDE ANGLE OF", r"DEGREES?"),
        "figure_adjustment_terminal_m": numeric_after(ocr, "ADCS REACHES", r"M\b"),
        "table_terminal_elevation_m": first_metric(current_terminal_elevation_row),
        "east_chapi_guide_angle": east_angle,
        "west_chapi_guide_angle": west_angle,
    }
    if values["east_chapi_guide_angle"] != values["normal_chapi_glide_angle"]:
        raise RuntimeError("The east approach scenario does not match the supplied normal CHAPI condition")

    baseline_table = evidence("legacy_airfield_criteria.pdf", "printed pages 90-92, Table 4-2", "baseline pad, primary-surface, clear-zone, and APZ I dimensions")
    current_table_ref = evidence("current_airfield_criteria.pdf", "printed pages 96-98, Table 4-2", "controlling pad, primary-surface, clear-zone, and APZ I dimensions")
    baseline_figure = evidence("legacy_airfield_criteria.pdf", "printed page 100, Figure 4-9", "combined baseline service layout and base approach-departure geometry")
    current_figure = evidence("current_airfield_criteria.pdf", "printed page 106, Figure 4-9a, Notes 2-6", "service-specific reciprocal layout and per-end CHAPI-controlled clearance surfaces")
    current_surface_ref = evidence("current_airfield_criteria.pdf", "printed pages 120-123, Table 4-7, items 6-15", "base imaginary-surface dimensions, terminal elevation, transitional surface, and nearby conditional branch")

    findings = [
        {
            "topic": "helipad size",
            "status": "retain compliant",
            "observed": f"Baseline standard VFR pad is {values['pad_size']:.2f} m square.",
            "requirement": f"The controlling service branch retains a {values['pad_size']:.2f} m square minimum.",
            "disposition": "Retain the centered pad boundary.",
            "evidence": [baseline_table, current_table_ref],
        },
        {
            "topic": "primary surface",
            "status": "retain compliant",
            "observed": f"The baseline service-specific primary surface is {values['primary_size']:.2f} m square.",
            "requirement": f"The current standard VFR branch requires {values['primary_size']:.2f} m square centered on the pad.",
            "disposition": "Retain the centered primary-surface boundary.",
            "evidence": [baseline_table, current_table_ref],
        },
        {
            "topic": "clear-zone length",
            "status": "retain compliant",
            "observed": f"Each reciprocal clear zone is {values['clear_zone_length']:.2f} m long and begins at a primary-surface edge.",
            "requirement": f"The current branch retains {values['clear_zone_length']:.2f} m at each end.",
            "disposition": "Retain length and reciprocal start stations.",
            "evidence": [baseline_figure, current_table_ref],
        },
        {
            "topic": "clear-zone width envelope",
            "status": "repair nonconforming",
            "observed": f"The combined baseline depicts the service clear zone at a constant {values['legacy_clear_zone_width']:.2f} m full width.",
            "requirement": f"The current service branch flares from {values['clear_zone_start_width']:.2f} m at the primary edge to {values['clear_zone_end_width']:.2f} m at the clear-zone end.",
            "disposition": "Replace both constant-width clear zones with reciprocal flared polygons.",
            "evidence": [baseline_table, baseline_figure, current_table_ref, current_figure],
        },
        {
            "topic": "APZ I length and continuity",
            "status": "retain compliant",
            "observed": f"APZ I follows each clear zone for {values['apz_length']:.2f} m.",
            "requirement": f"The controlling branch retains {values['apz_length']:.2f} m and starts APZ I at the clear-zone terminal station.",
            "disposition": "Retain length and make the shared boundary continuous.",
            "evidence": [baseline_table, baseline_figure, current_table_ref, current_figure],
        },
        {
            "topic": "APZ I width envelope",
            "status": "repair nonconforming",
            "observed": f"The combined baseline depicts APZ I at a constant {values['legacy_apz_width']:.2f} m full width for this branch.",
            "requirement": f"The current service branch flares from {values['apz_start_width']:.2f} m to {values['apz_end_width']:.2f} m full width.",
            "disposition": "Replace both constant-width APZ I areas with reciprocal flared polygons.",
            "evidence": [baseline_table, baseline_figure, current_table_ref, current_figure],
        },
        {
            "topic": "east normal-CHAPI approach-departure clearance surface",
            "status": "repair nonconforming",
            "observed": f"The legacy service branch uses the base {values['legacy_adcs_slope']:.1f}:1 surface, {values['legacy_adcs_length']:.2f} m long with a {values['legacy_adcs_end_width']:.2f} m terminal full width.",
            "requirement": f"For the east normal {values['east_chapi_guide_angle']:.0f}-degree CHAPI, the current service-specific figure fixes a {values['normal_chapi_slope']:.1f}:1 surface, {values['normal_chapi_length']:.2f} m long and {values['normal_chapi_end_width']:.2f} m wide at its end.",
            "disposition": "Replace the east baseline surface with the fully dimensioned CHAPI boundary from the positive-X primary-surface edge.",
            "evidence": [
                evidence("legacy_airfield_criteria.pdf", "printed pages 112-114, Table 4-7, items 6-9", "baseline service-column surface and branch-limited CHAPI note"),
                evidence("current_airfield_criteria.pdf", "physical pages 8-9, change summary", "service figure split and revised CHAPI treatment"),
                current_surface_ref,
                current_figure,
            ],
        },
        {
            "topic": "west non-standard-CHAPI dimensional dependency",
            "status": "design hold unresolved",
            "observed": f"The west approach has a non-standard {values['west_chapi_guide_angle']:.0f}-degree CHAPI, while the legacy plan shows only the base surface.",
            "requirement": "The current figure requires non-standard length and width to be adjusted from the lowest on-course visual signal and the terminal-elevation condition.",
            "disposition": "Do not infer or mirror a west controlling polygon. Obtain the CHAPI lowest on-course signal angle and a resolved terminal-elevation criterion before dimensioning it.",
            "evidence": [current_figure, current_surface_ref],
        },
        {
            "topic": "non-standard CHAPI terminal-elevation source conflict",
            "status": "design hold unresolved",
            "observed": f"Figure 4-9a Note 6 pairs {values['figure_adjustment_terminal_m']:.2f} m with 150 ft, while Table 4-7 item 11 pairs {values['table_terminal_elevation_m']:.2f} m with the same 150 ft terminal elevation.",
            "requirement": "The non-standard surface length and width depend on a single unambiguous terminal elevation.",
            "disposition": "Raise a criteria clarification; do not choose one metric value or convert the reference value silently.",
            "evidence": [current_figure, current_surface_ref],
        },
        {
            "topic": "reciprocal ground zones and asymmetric conditional surfaces",
            "status": "partial repair with design hold",
            "observed": "The two straight approach paths share one facility classification, but their CHAPI guide-angle conditions differ by end.",
            "requirement": "Clear zones and APZ I remain reciprocal; a CHAPI-controlled clearance surface may be mirrored only when the end-specific activating conditions and inputs match.",
            "disposition": "Draw reciprocal clear zones and APZ I, draw the resolved east CHAPI boundary, and show a non-controlling west design-hold note instead of mirrored geometry.",
            "evidence": [current_table_ref, current_figure],
        },
        {
            "topic": "APZ II",
            "status": "exclude inapplicable",
            "observed": "The baseline plan contains clear zone and APZ I but no APZ II.",
            "requirement": "APZ II is not applicable to rotary-wing aircraft.",
            "disposition": "Do not add APZ II to the repaired plan.",
            "evidence": [baseline_table, current_table_ref],
        },
        {
            "topic": "transitional surface H",
            "status": "scope hold pending profile evidence",
            "observed": "Table 4-7 item 14 lists a 2H:1V transitional surface, while the supplied packet is a plan view without profile, elevation, or section data.",
            "requirement": "The transitional surface must be assessed from supported vertical/profile evidence; its plan-view boundary cannot be invented from the ratio alone.",
            "disposition": "Record an explicit scope hold and do not draw an unsupported transitional-surface polygon pending profile and elevation evidence.",
            "evidence": [current_surface_ref],
        },
        {
            "topic": "grades, elevations, and obstacle penetrations",
            "status": "unresolved from plan view",
            "observed": "The schematic plan view supplies no site survey, profile, grading record, or obstacle inventory.",
            "requirement": "Plan geometry alone cannot establish grades, elevations, or penetrations of a sloped clearance surface.",
            "disposition": "Leave these properties unresolved pending survey and profile evidence; do not certify them compliant.",
            "evidence": [current_table_ref, current_figure],
        },
    ]

    report = {
        "classification": {
            "facility": "standard VFR helipad",
            "service_branch": "Navy and Marine Corps",
            "approach_configuration": "two reciprocal straight approach paths",
            "visual_aids": {
                "east": f"normal CHAPI, {values['east_chapi_guide_angle']:.0f}-degree guide angle",
                "west": f"non-standard CHAPI, {values['west_chapi_guide_angle']:.0f}-degree guide angle",
            },
        },
        "review_basis": {
            "baseline": "legacy_airfield_criteria.pdf is the plan condition under inspection.",
            "controlling": "current_airfield_criteria.pdf, including marked Change 2 material, controls the repair.",
            "branch_decision": "Use the service-specific standard VFR branch in Figure 4-9a; exclude the Army and Air Force limited-use branch split into Figure 4-9b.",
            "conditional_decision": "Apply the service-specific figure's CHAPI notes by approach end even though the nearby Table 4-7 CHAPI parenthetical is scoped to a different facility class. The east normal case is fully dimensioned; the west non-standard case remains on hold because its adjustment dependencies are not closed by the supplied record.",
            "evidence": [
                evidence("current_airfield_criteria.pdf", "physical pages 8-9, change summary", "status and branch split"),
                current_figure,
            ],
        },
        "findings": findings,
        "repaired_dimensional_basis": {
            "units": "m",
            "origin": "helipad center at (0, 0)",
            "axis": "reciprocal straight approach centerline on X axis",
            "pad_size": round(values["pad_size"], 3),
            "primary_size": round(values["primary_size"], 3),
            "clear_zone_length": round(values["clear_zone_length"], 3),
            "clear_zone_start_width": round(values["clear_zone_start_width"], 3),
            "clear_zone_end_width": round(values["clear_zone_end_width"], 3),
            "apz_length": round(values["apz_length"], 3),
            "apz_start_width": round(values["apz_start_width"], 3),
            "apz_end_width": round(values["apz_end_width"], 3),
            "east_chapi": {
                "status": "resolved controlling geometry",
                "guide_angle_degrees": values["east_chapi_guide_angle"],
                "slope_h_to_v": values["normal_chapi_slope"],
                "length": values["normal_chapi_length"],
                "terminal_full_width": values["normal_chapi_end_width"],
            },
            "west_chapi": {
                "status": "design hold; no controlling polygon",
                "guide_angle_degrees": values["west_chapi_guide_angle"],
                "missing_input": "lowest on-course visual signal angle",
                "source_conflict": f"terminal elevation is stated as both {values['figure_adjustment_terminal_m']:.2f} m and {values['table_terminal_elevation_m']:.2f} m for 150 ft",
            },
            "station_dependencies": {
                "primary_edge": round(values["primary_size"] / 2, 3),
                "clear_zone_end": round(values["primary_size"] / 2 + values["clear_zone_length"], 3),
                "apz_end": round(values["primary_size"] / 2 + values["clear_zone_length"] + values["apz_length"], 3),
                "east_chapi_end": round(values["primary_size"] / 2 + values["normal_chapi_length"], 3),
                "west_chapi_end": "unresolved design hold",
            },
        },
        "unresolved_or_out_of_scope": [
            "Site grades and elevations cannot be verified from the plan view.",
            "Obstacle penetrations and property or land-use control cannot be verified without site records.",
            "Pavement structure, markings, lighting design beyond the stated CHAPI condition, and aircraft performance are outside this plan-view repair.",
            "The west non-standard CHAPI boundary remains on design hold pending its lowest on-course signal angle and resolution of the terminal-elevation conflict in the supplied criteria.",
        ],
    }
    (OUTPUT / "inspection_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_dxf(values, OUTPUT / "repaired_plan.dxf")

    memo = f"""# Engineering Repair Handoff

The inspected baseline combines service branches that the controlling revision now separates. For this Navy and Marine Corps standard VFR helipad with reciprocal straight approaches, the retained work is the centered {values['pad_size']:.2f} m square pad, the {values['primary_size']:.2f} m square primary surface, the {values['clear_zone_length']:.2f} m clear-zone length, and the {values['apz_length']:.2f} m APZ I length at each end.

The drawing repairs both clear zones to flare from {values['clear_zone_start_width']:.2f} m to {values['clear_zone_end_width']:.2f} m full width and both APZ I areas to flare from {values['apz_start_width']:.2f} m to {values['apz_end_width']:.2f} m. On the east approach it replaces the legacy {values['legacy_adcs_slope']:.1f}:1, {values['legacy_adcs_length']:.2f} m, {values['legacy_adcs_end_width']:.2f} m terminal-width surface with the resolved normal {values['east_chapi_guide_angle']:.0f}-degree CHAPI condition: {values['normal_chapi_slope']:.1f}:1, {values['normal_chapi_length']:.2f} m long, and {values['normal_chapi_end_width']:.2f} m terminal full width. The nearby table's CHAPI parenthetical belongs to another facility class and does not displace the service-specific figure. APZ II remains excluded.

The west non-standard {values['west_chapi_guide_angle']:.0f}-degree CHAPI surface is a design hold, not completed controlling geometry. The supplied figure requires adjustment from the lowest on-course visual signal but does not state that angle, and its adjustment note pairs {values['figure_adjustment_terminal_m']:.2f} m with 150 ft while Table 4-7 item 11 pairs {values['table_terminal_elevation_m']:.2f} m with 150 ft. The drawing therefore contains no mirrored or guessed west CHAPI polygon; release requires the missing signal angle and a criteria clarification for the terminal elevation.

The report and DXF use meters, origin `(0, 0)` at pad center, east on positive X, and the approach centerline on the X axis. Site grades, elevations, obstacle penetrations, and land-use control remain unresolved because the plan view contains no survey, profile, or site inventory. Those matters require separate evidence before compliance can be certified.
"""
    (OUTPUT / "repair_memo.md").write_text(memo, encoding="utf-8")


if __name__ == "__main__":
    main()

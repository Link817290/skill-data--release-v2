#!/usr/bin/env python3
"""Derive verifier values and input locks directly from the supplied criteria PDFs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve()
PACKAGE = Path(os.environ["PACKAGE_ROOT"]) if "PACKAGE_ROOT" in os.environ else SCRIPT.parents[2]
WORKSPACE = Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))
TARGET = Path(os.environ.get("GROUND_TRUTH_TARGET", str(PACKAGE / "task/tests/ground_truth.json")))
INSTRUCTION = PACKAGE / "task/instruction.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def page_text(path: Path, first: int, last: int) -> str:
    return run("pdftotext", "-f", str(first), "-l", str(last), "-layout", str(path), "-")


def row(text: str, start: str, end: str) -> str:
    match = re.search(start + r"(.*?)" + end, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise RuntimeError(f"Could not isolate criteria row: {start}")
    return match.group(1)


def metric_values(text: str) -> list[float]:
    return [float(value) for value in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*m\b", text, re.IGNORECASE)]


def first_metric(text: str) -> float:
    values = metric_values(text)
    if not values:
        raise RuntimeError("No metric value found in criteria row")
    return values[0]


def changed_metric_pair(text: str) -> tuple[float, float]:
    changed = re.search(r"\\2\\(.*?)/2/", text, flags=re.DOTALL)
    values = metric_values(changed.group(1) if changed else "")
    if len(values) < 2:
        raise RuntimeError("Could not isolate marked start/end values")
    return values[0], values[1]


def last_metric_before(text: str, phrase: str) -> float:
    position = text.lower().find(phrase.lower())
    if position < 0:
        raise RuntimeError(f"Scope phrase was not found: {phrase}")
    values = metric_values(text[:position])
    if not values:
        raise RuntimeError(f"No metric value precedes: {phrase}")
    return values[-1]


def metric_with_foot_value(text: str, foot_value: int) -> float:
    digits = str(foot_value)
    foot_pattern = digits if len(digits) < 4 else digits[:-3] + r",?" + digits[-3:]
    match = re.search(
        rf"(\d+(?:\.\d+)?)\s*m.*?\(\s*{foot_pattern}\s*ft",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"Could not pair metric value with {foot_value} ft")
    return float(match.group(1))


def metric_above_foot_value(text: str, foot_value: int) -> float:
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


def ocr_page(path: Path, page: int) -> str:
    with tempfile.TemporaryDirectory() as temporary:
        prefix = str(Path(temporary) / "criteria")
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "300", "-png", str(path), prefix],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        images = sorted(Path(temporary).glob("criteria-*.png"))
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


def main() -> None:
    legacy = WORKSPACE / "legacy_airfield_criteria.pdf"
    current = WORKSPACE / "current_airfield_criteria.pdf"
    legacy_table = page_text(legacy, 124, 128)
    current_table = page_text(current, 134, 137)
    legacy_surface = page_text(legacy, 146, 148)
    current_figure = page_text(current, 144, 144)
    current_surface = page_text(current, 158, 162)
    if "Table 4-2" not in legacy_table or "Table 4-2" not in current_table:
        raise RuntimeError("Required Table 4-2 anchors were not found")
    if "Table 4-7" not in legacy_surface or "Figure 4-9a" not in current_figure or "Table 4-7" not in current_surface:
        raise RuntimeError("Required clearance-surface anchors were not found")

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
    ocr = ocr_page(current, 144)
    normalized_ocr = re.sub(r"\s+", " ", ocr.upper())
    if "LOWEST ON-COURSE VISUAL SIGNAL" not in normalized_ocr or "NON-STANDARD CHAPI GLIDE ANGLE" not in normalized_ocr:
        raise RuntimeError("The conditional CHAPI adjustment notes were not recoverable by OCR")

    expected = {
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
        "legacy_adcs_slope": float(re.search(r"(\d+(?:\.\d+)?)\s*:\s*1", legacy_slope_row).group(1)),
        "legacy_adcs_length": metric_with_foot_value(legacy_length_row, 1200),
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
    if expected["east_chapi_guide_angle"] != expected["normal_chapi_glide_angle"]:
        raise RuntimeError("The east scenario does not match the normal CHAPI guide angle in the figure")
    payload = {
        "locked_inputs": {
            "legacy_airfield_criteria.pdf": sha256(legacy),
            "current_airfield_criteria.pdf": sha256(current),
        },
        "expected_values": expected,
        "expert_judgments": {
            "west_chapi_numeric_boundary": "unresolved design hold",
            "basis": "The supplied figure requires adjustment from the lowest on-course visual signal but does not state that signal angle, and its metric terminal elevation conflicts with Table 4-7 item 11 for the same reference-unit value.",
            "evidence": [
                "current_airfield_criteria.pdf, printed page 106, Figure 4-9a, Notes 3 and 6",
                "current_airfield_criteria.pdf, printed page 123, Table 4-7, item 11",
            ],
        },
        "derivation": "Values, per-end task conditions, source conflict, and input hashes were derived from the supplied instruction and criteria PDFs by scoped table extraction and figure OCR.",
    }
    TARGET.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

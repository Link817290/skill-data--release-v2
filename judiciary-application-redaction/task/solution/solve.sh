#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -d /workspace/materials ]]; then
  MATERIAL_DIR="/workspace/materials"
  OUT_DIR="/workspace/output"
else
  MATERIAL_DIR="$BASE_DIR/environment/workspace/materials"
  OUT_DIR="$BASE_DIR/environment/workspace/output"
fi
mkdir -p "$OUT_DIR"

python3 - "$MATERIAL_DIR" "$OUT_DIR/sanitized_onboarding_packet.pdf" "$BASE_DIR/solution/disposition-ledger.json" <<'PY'
from __future__ import annotations

import sys
import json
import hashlib
import tempfile
from collections import Counter
from pathlib import Path

import pymupdf as fitz


materials = Path(sys.argv[1])
output_path = Path(sys.argv[2])
counts: Counter[str] = Counter()
ledger: dict[str, list[tuple[str, float, float, str, str]]] = {
    "Application": [],
    "Withholding record": [],
    "Employment eligibility record": [],
}


def clear_xml(document: fitz.Document) -> None:
    try:
        document.del_xml_metadata()
    except Exception:
        pass


def response_rect(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> fitz.Rect:
    return fitz.Rect(
        x0 * page.rect.width / 612.0,
        y0 * page.rect.height / 792.0,
        x1 * page.rect.width / 612.0,
        y1 * page.rect.height / 792.0,
    )


def record_action(section: str, page_label: str, rectangle: fitz.Rect, code: str) -> None:
    outcome = "REPLACED" if code == "ALIAS" else "REMOVED"
    ledger[section].append((page_label, rectangle.y0, rectangle.x0, code, outcome))
    counts[code] += 1


def fitted_size(text: str, rectangle: fitz.Rect, maximum: float) -> float:
    size = min(maximum, max(3.8, rectangle.height * 0.56))
    while size > 3.8 and fitz.get_text_length(text, fontname="helv", fontsize=size) > rectangle.width - 3:
        size -= 0.25
    return size


def centered_text(page: fitz.Page, rectangle: fitz.Rect, text: str, color: tuple[float, float, float], maximum: float = 8.0) -> None:
    rectangle = rectangle & page.rect
    if rectangle.is_empty:
        return
    size = fitted_size(text, rectangle, maximum)
    width = fitz.get_text_length(text, fontname="helv", fontsize=size)
    x = rectangle.x0 + max(1.0, (rectangle.width - width) / 2)
    y = rectangle.y0 + (rectangle.height + size * 0.72) / 2
    page.insert_text((x, y), text, fontname="helv", fontsize=size, color=color, overlay=True)


def draw_bar(page: fitz.Page, rectangle: fitz.Rect, code: str, label: bool = True) -> None:
    rectangle = rectangle & page.rect
    page.draw_rect(rectangle, color=(0, 0, 0), fill=(0, 0, 0), width=0, overlay=True)
    if label and rectangle.width >= 28 and rectangle.height >= 7:
        centered_text(page, rectangle, code, (1, 1, 1), maximum=5.2)


def apply_destructive_actions(page: fitz.Page, actions: list[tuple[fitz.Rect, str, str]]) -> None:
    for rectangle, kind, _text in actions:
        fill = (1, 1, 1) if kind == "alias" else (0, 0, 0)
        page.add_redact_annot(rectangle & page.rect, fill=fill, cross_out=False)
    if actions:
        page.apply_redactions(images=2, graphics=2, text=0)
    for rectangle, kind, text in actions:
        clipped = rectangle & page.rect
        if kind == "alias":
            centered_text(page, clipped, text, (0, 0, 0), maximum=8.0)
        elif clipped.width >= 28 and clipped.height >= 7:
            centered_text(page, clipped, text, (1, 1, 1), maximum=5.2)


def is_professional_application_value(page_index: int, rectangle: fitz.Rect) -> bool:
    if page_index != 0:
        return False
    role_or_location = 250 <= rectangle.y0 < 290 and rectangle.x0 < 460
    education = 325 <= rectangle.y0 < 431
    return role_or_location or education


def application_disposition(page_index: int, rectangle: fitz.Rect) -> tuple[str, str]:
    if page_index == 0 and 180 <= rectangle.y0 < 210:
        if rectangle.x0 < 170:
            return "alias", "SUBJECT"
        if rectangle.x0 < 220:
            return "alias", "S"
        if rectangle.x0 < 410:
            return "alias", "07"
    if page_index == 0 and rectangle.y0 < 260:
        return "redact", "CONTACT"
    return "redact", "OTHER"


def sanitize_application(source: Path, target: Path) -> None:
    document = fitz.open(source)
    page_actions: dict[int, list[tuple[fitz.Rect, str, str]]] = {}
    for page_index, page in enumerate(document):
        for widget in list(page.widgets() or []):
            current = str(widget.field_value or "").strip()
            if not current or is_professional_application_value(page_index, widget.rect):
                continue
            kind, token = application_disposition(page_index, widget.rect)
            if kind == "alias":
                rectangles = [widget.rect]
                code = "ALIAS"
            else:
                hits = [hit for hit in page.search_for(current) if hit.intersects(widget.rect)]
                if hits:
                    rectangles = [hit + (-2, -1, 2, 1) for hit in hits]
                else:
                    height = min(widget.rect.height, 18.0)
                    rectangles = [fitz.Rect(widget.rect.x0, widget.rect.y0, widget.rect.x1, widget.rect.y0 + height)]
                code = token
            page_actions.setdefault(page_index, []).extend((rectangle, kind, token) for rectangle in rectangles)
            record_action("Application", f"APP-{page_index + 1}", widget.rect, code)
            widget.field_value = False if widget.field_type != fitz.PDF_WIDGET_TYPE_TEXT else ""
            widget.update()

    document.bake(annots=False, widgets=True)
    for page_index, actions in page_actions.items():
        apply_destructive_actions(document[page_index], actions)
    document.set_metadata({})
    clear_xml(document)
    document.save(target, garbage=4, deflate=True, clean=True)
    document.close()


def remove_regions(page: fitz.Page, rectangles: list[fitz.Rect]) -> None:
    for rectangle in rectangles:
        page.add_redact_annot(rectangle & page.rect, fill=(1, 1, 1), cross_out=False)
    if rectangles:
        page.apply_redactions(images=2, graphics=1, text=0)


def sanitize_withholding(source: Path, target: Path) -> None:
    document = fitz.open(source)
    page = document[0]
    identity_removals = [
        response_rect(page, 176, 163, 272, 179), response_rect(page, 323, 163, 443, 179),
        response_rect(page, 35, 187, 300, 202), response_rect(page, 323, 187, 580, 202),
        response_rect(page, 35, 211, 170, 227), response_rect(page, 175, 211, 270, 227),
        response_rect(page, 275, 211, 440, 227), response_rect(page, 444, 211, 580, 227),
    ]
    display_regions = [
        response_rect(page, 176, 170, 272, 179), response_rect(page, 323, 169, 443, 179),
        response_rect(page, 35, 194, 300, 202), response_rect(page, 323, 194, 580, 202),
        response_rect(page, 35, 219, 170, 227), response_rect(page, 175, 219, 270, 227),
        response_rect(page, 275, 219, 440, 227), response_rect(page, 444, 219, 580, 227),
    ]
    remove_regions(page, identity_removals)

    labels = [
        (178.9, 166.5, "Social Security Number"),
        (325.0, 166.5, "Employee Name"),
        (35.4, 190.0, "Home Address (number and street or rural route)"),
        (324.0, 188.5, "Address Continued (apartment number, if any)"),
        (36.7, 214.5, "City"), (175.1, 214.0, "State"),
        (275.8, 214.0, "Zip Code"), (444.9, 214.0, "County of Residence (required)"),
    ]
    for x, y, label in labels:
        page.insert_text((x, y), label, fontname="Times-Roman", fontsize=7.0, color=(0, 0, 0), overlay=True)

    draw_bar(page, display_regions[0], "GOV-ID")
    centered_text(page, display_regions[1], "SUBJECT 07", (0, 0, 0), maximum=7.0)
    for rectangle in display_regions[2:]:
        draw_bar(page, rectangle, "CONTACT")
    identity_codes = ("GOV-ID", "ALIAS", "CONTACT", "CONTACT", "CONTACT", "CONTACT", "CONTACT", "CONTACT")
    for rectangle, code in zip(identity_removals, identity_codes):
        record_action("Withholding record", "TAX-1", rectangle, code)

    declaration_rectangles = [
        response_rect(page, 66, 247, 81, 262), response_rect(page, 489, 267, 508, 282),
        response_rect(page, 493, 279, 585, 297), response_rect(page, 124, 369, 139, 384),
        response_rect(page, 425, 386, 443, 403), response_rect(page, 425, 405, 526, 424),
    ]
    apply_destructive_actions(page, [(rectangle, "redact", "TAX") for rectangle in declaration_rectangles])
    for rectangle in declaration_rectangles:
        record_action("Withholding record", "TAX-1", rectangle, "TAX")
    document.set_metadata({})
    clear_xml(document)
    document.save(target, garbage=4, deflate=True, clean=True)
    document.close()


def sanitize_eligibility(source: Path, target: Path) -> None:
    document = fitz.open(source)
    page = document[0]
    rectangles = [
        response_rect(page, 42, 214, 222, 230), response_rect(page, 224, 214, 365, 230),
        response_rect(page, 379, 214, 411, 230), response_rect(page, 42, 241, 350, 257),
        response_rect(page, 416, 241, 555, 257), response_rect(page, 42, 269, 210, 285),
        response_rect(page, 211, 269, 348, 285), response_rect(page, 350, 269, 412, 285),
        response_rect(page, 416, 269, 555, 285), response_rect(page, 296, 295, 311, 312),
        response_rect(page, 112, 351, 235, 381), response_rect(page, 376, 351, 500, 381),
    ]
    actions = [
        (rectangles[0], "alias", "07"), (rectangles[1], "alias", "SUBJECT"),
        (rectangles[2], "alias", "S"), (rectangles[3], "redact", "CONTACT"),
        (rectangles[4], "redact", "DOB"), (rectangles[5], "redact", "CONTACT"),
        (rectangles[6], "redact", "CONTACT"), (rectangles[7], "redact", "CONTACT"),
        (rectangles[8], "redact", "GOV-ID"), (rectangles[9], "redact", "AUTH"),
        (rectangles[10], "redact", "SIGN"), (rectangles[11], "redact", "DATE"),
    ]
    apply_destructive_actions(page, actions)
    action_codes = ("ALIAS", "ALIAS", "ALIAS", "CONTACT", "DOB", "CONTACT", "CONTACT", "CONTACT", "GOV-ID", "AUTH", "SIGN", "DATE")
    for rectangle, code in zip(rectangles, action_codes):
        record_action("Employment eligibility record", "ELIG-1", rectangle, code)
    document.set_metadata({})
    clear_xml(document)
    document.save(target, garbage=4, deflate=True, clean=True)
    document.close()


def merge_semantic_phone():
    entries = ledger["Application"]
    fragments = [e for e in entries if e[0] == "APP-1" and e[3] == "CONTACT" and e[2] >= 430 and 180 <= e[1] < 210]
    if len(fragments) > 1:
        ledger["Application"] = [e for e in entries if e not in fragments] + [("APP-1", min(e[1] for e in fragments), min(e[2] for e in fragments), "CONTACT", "REMOVED")]
        counts["CONTACT"] -= len(fragments) - 1


def add_control_sheet(document: fitz.Document) -> None:
    page = document.new_page(width=612, height=792)
    page.draw_rect(fitz.Rect(36, 36, 576, 756), color=(0.15, 0.15, 0.15), width=1)
    page.insert_text((54, 82), "PRIVACY REVIEW CONTROL SHEET", fontname="hebo", fontsize=20, color=(0, 0, 0))
    page.insert_text((54, 111), "ARCHIVAL HUMAN RESOURCES REVIEW", fontname="helv", fontsize=9, color=(0.25, 0.25, 0.25))
    page.draw_line(fitz.Point(54, 128), fitz.Point(558, 128), color=(0, 0, 0), width=0.8)
    page.insert_text((54, 164), "Review alias", fontname="hebo", fontsize=10)
    page.insert_text((190, 164), "SUBJECT 07", fontname="helv", fontsize=10)

    page.insert_text((54, 214), "SOURCE SECTIONS", fontname="hebo", fontsize=11)
    rows = [
        ("Application", "APP-1 to APP-6"),
        ("Withholding record", "TAX-1"),
        ("Employment eligibility record", "ELIG-1"),
        ("Disposition register", "AUD-1 to AUD-3"),
    ]
    y = 240
    for label, page_range in rows:
        page.insert_text((66, y), label, fontname="helv", fontsize=9)
        page.insert_text((360, y), page_range, fontname="helv", fontsize=9)
        y += 24

    page.insert_text((54, 346), "FIELD ACTION SUMMARY", fontname="hebo", fontsize=11)
    page.insert_text((66, 372), "ACTION CODE", fontname="hebo", fontsize=8)
    page.insert_text((360, 372), "AFFECTED RESPONSE FIELDS", fontname="hebo", fontsize=8)
    page.draw_line(fitz.Point(66, 380), fitz.Point(546, 380), color=(0.3, 0.3, 0.3), width=0.6)
    y = 400
    for code in ("ALIAS", "CONTACT", "GOV-ID", "DOB", "SIGN", "DATE", "TAX", "AUTH", "OTHER"):
        page.insert_text((66, y), code, fontname="helv", fontsize=9)
        page.insert_text((360, y), str(counts[code]), fontname="helv", fontsize=9)
        y += 24
    page.draw_line(fitz.Point(54, 632), fitz.Point(558, 632), color=(0, 0, 0), width=0.8)
    page.insert_text((54, 655), "All counts reconcile to source response fields; source pages follow unchanged in size and order.", fontname="helv", fontsize=8)
    page.insert_text((54, 684), "Classification: RESTRICTED / REDACTED REVIEW COPY", fontname="hebo", fontsize=8)


def add_register_page(document: fitz.Document, section: str) -> None:
    page = document.new_page(width=612, height=792)
    page.draw_rect(fitz.Rect(36, 36, 576, 756), color=(0.15, 0.15, 0.15), width=1)
    page.insert_text((54, 78), "FIELD DISPOSITION REGISTER", fontname="hebo", fontsize=18)
    page.insert_text((54, 108), f"Source section: {section}", fontname="helv", fontsize=10)
    page.draw_line(fitz.Point(54, 126), fitz.Point(558, 126), color=(0, 0, 0), width=0.8)
    page.insert_text((58, 154), "SOURCE PAGE", fontname="hebo", fontsize=8)
    page.insert_text((180, 154), "ROW", fontname="hebo", fontsize=8)
    page.insert_text((270, 154), "ACTION", fontname="hebo", fontsize=8)
    page.insert_text((420, 154), "OUTCOME", fontname="hebo", fontsize=8)
    page.draw_line(fitz.Point(54, 163), fitz.Point(558, 163), color=(0.3, 0.3, 0.3), width=0.6)
    entries = sorted(ledger[section], key=lambda item: (int(item[0].split("-")[-1]), item[1], item[2]))
    y = 187
    for sequence, (page_label, _top, _left, code, outcome) in enumerate(entries, start=1):
        page.insert_text((58, y), page_label, fontname="helv", fontsize=8.5)
        page.insert_text((180, y), f"{sequence:02d}", fontname="helv", fontsize=8.5)
        page.insert_text((270, y), code, fontname="helv", fontsize=8.5)
        page.insert_text((420, y), outcome, fontname="helv", fontsize=8.5)
        page.draw_line(fitz.Point(54, y + 7), fitz.Point(558, y + 7), color=(0.82, 0.82, 0.82), width=0.35)
        y += 27
    page.draw_line(fitz.Point(54, 704), fitz.Point(558, 704), color=(0, 0, 0), width=0.8)
    page.insert_text((54, 727), "Original response values are intentionally excluded from this register.", fontname="helv", fontsize=8)


with tempfile.TemporaryDirectory() as temporary:
    temporary_path = Path(temporary)
    application = temporary_path / "application.pdf"
    withholding = temporary_path / "withholding.pdf"
    eligibility = temporary_path / "eligibility.pdf"
    sanitize_application(materials / "employment_application_record.pdf", application)
    sanitize_withholding(materials / "withholding_record.pdf", withholding)
    sanitize_eligibility(materials / "employment_eligibility_record.pdf", eligibility)

    merge_semantic_phone()
    compiled = json.loads(Path(sys.argv[3]).read_text())
    assert compiled["valid"]
    assert all(hashlib.sha256((materials / name).read_bytes()).hexdigest() == sha for name,sha in compiled["source_sha256"].items())
    assert dict(counts) == compiled["counts"], "Mutation actions must match the preflight-closed semantic ledger"
    ledger = {section: [] for section in ledger}
    for row in compiled["register_rows"]:
        rectangle = row["sort_rect"]
        ledger[row["record"]].append((row["logical_page"], rectangle[1], rectangle[0], row["action"], row["outcome"]))
    counts = Counter(compiled["counts"])
    packet = fitz.open()
    add_control_sheet(packet)
    for path in (application, withholding, eligibility):
        with fitz.open(path) as part:
            packet.insert_pdf(part)
    for section in ("Application", "Withholding record", "Employment eligibility record"):
        add_register_page(packet, section)
    packet.set_toc([
        [1, "Control Sheet", 1],
        [1, "Application", 2],
        [1, "Withholding Record", 8],
        [1, "Employment Eligibility Record", 9],
        [1, "Disposition Register", 10],
        [2, "Application Actions", 10],
        [2, "Withholding Actions", 11],
        [2, "Employment Eligibility Actions", 12],
    ])
    packet.set_page_labels([
        {"startpage": 0, "prefix": "CTRL-", "style": "D", "firstpagenum": 1},
        {"startpage": 1, "prefix": "APP-", "style": "D", "firstpagenum": 1},
        {"startpage": 7, "prefix": "TAX-", "style": "D", "firstpagenum": 1},
        {"startpage": 8, "prefix": "ELIG-", "style": "D", "firstpagenum": 1},
        {"startpage": 9, "prefix": "AUD-", "style": "D", "firstpagenum": 1},
    ])
    clear_xml(packet)
    packet.set_metadata({
        "title": "Privacy-Safe Onboarding Review Packet",
        "author": "",
        "subject": "HR archival review",
        "keywords": "restricted; redacted",
        "creator": "",
        "producer": "",
        "creationDate": "",
        "modDate": "",
    })
    packet.save(output_path, garbage=4, deflate=True, clean=True)
    packet.close()
PY

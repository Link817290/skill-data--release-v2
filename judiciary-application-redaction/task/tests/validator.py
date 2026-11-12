#!/usr/bin/env python3
"""Condition-blind validator for the sanitized onboarding packet.

Two independent lenses are computed for every submission.

`reward_strict` is the continuous professional capability score. It asks whether
the right responses were withheld, retained, aliased, reason-coded and
reconciled, and it derives every expected value from the supplied source PDFs
and the hidden ground truth.

`reward_lenient` is a separate binary delivery-completeness score. It asks only
whether a complete, parseable, correctly partitioned packet was handed over. It
opens the delivered file and nothing else: it never reads the source materials
or the ground truth, never derives an expected response value, and never reuses
a strict observation, so a submission can be structurally complete and still
score near zero under the strict lens, or professionally sound in the parts it
delivered and still fail the delivery contract for shipping an incomplete
packet.

`reward` aliases `reward_strict`.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pymupdf as fitz


ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = Path("/workspace") if Path("/workspace/materials").is_dir() else ROOT / "environment" / "workspace"
MATERIALS = WORKSPACE / "materials"
SOURCES = [
    MATERIALS / "employment_application_record.pdf",
    MATERIALS / "withholding_record.pdf",
    MATERIALS / "employment_eligibility_record.pdf",
]
WEIGHTS = {
    "selective_privacy": 0.15,
    "required_retention": 0.10,
    "pseudonym_consistency": 0.05,
    "purpose_based_disposition": 0.50,
    "control_and_navigation": 0.05,
    "register_structure": 0.05,
    "document_fidelity": 0.07,
    "delivery_hygiene": 0.03,
}
CONTROL_TITLE = "PRIVACY REVIEW CONTROL SHEET"
REGISTER_TITLE = "DISPOSITION REGISTER"
REVIEW_ALIAS = "SUBJECT 07"
REGISTER_RANGE = ("AUD-1", "AUD-3")
ROW_OUTCOMES = ("REPLACED", "REMOVED")
# Requested packet composition: one control sheet, the source pages, three
# register pages. The delivery lens counts parts, it does not judge them.
PACKET_PARTS = (1, 8, 3)
DELIVERY_CHECKS = (
    "deliverable_present",
    "pdf_opens_unencrypted",
    "packet_has_every_part",
    "control_sheet_leads_packet",
    "control_sheet_field_slots_filled",
    "source_block_carries_text",
    "register_block_present",
    "register_rows_populated",
    "navigation_objects_present",
)
ORDERED_ANCHORS = [
    (0, "EMPLOYMENT APPLICATION"), (1, "SECTION THREE: EMPLOYMENT HISTORY"),
    (4, "VOLUNTARY PERSONAL INFORMATION FORM"), (5, "Place Stamp or Franking Here"),
    (6, "Employee Withholding Allowance Certificate"), (7, "Form 1-9, Employment"),
]
ACTION_CODES = ("ALIAS", "CONTACT", "GOV-ID", "DOB", "SIGN", "DATE", "TAX", "AUTH", "OTHER")


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def contains_phrase(text: str, phrase: str) -> bool:
    token = re.escape(norm(phrase)).replace(r"\ ", r"\s+")
    return bool(re.search(r"(?<![a-z0-9])" + token + r"(?![a-z0-9])", norm(text)))


def page_range_present(text: str, label: str, prefix: str, start: int, end: int) -> bool:
    """Accept equivalent range notation without prescribing one connector."""
    value = norm(text).replace("\u2013", "-").replace("\u2014", "-")
    pattern = (
        rf"{re.escape(norm(label))}.{{0,40}}"
        rf"{prefix}\s*-?\s*0*{start}\s*(?:to|through|thru|-)\s*"
        rf"(?:{prefix}\s*-?\s*)?0*{end}"
    )
    return bool(re.search(pattern, value, re.I))


def fraction(items: list[bool]) -> float:
    return sum(items) / len(items) if items else 0.0


def nominal(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> fitz.Rect:
    return fitz.Rect(
        x0 * page.rect.width / 612.0,
        y0 * page.rect.height / 792.0,
        x1 * page.rect.width / 612.0,
        y1 * page.rect.height / 792.0,
    )


def black_fraction(page: fitz.Page, rectangle: fitz.Rect) -> float:
    rectangle = rectangle & page.rect
    if rectangle.is_empty:
        return 0.0
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rectangle, colorspace=fitz.csGRAY, alpha=False)
    return sum(value < 35 for value in pixmap.samples) / max(1, len(pixmap.samples))


def external_text(path: Path) -> str:
    try:
        process = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        return process.stdout.decode("utf-8", errors="ignore")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def is_professional_application_value(page_index: int, rectangle: fitz.Rect) -> bool:
    return page_index == 0 and (
        (250 <= rectangle.y0 < 290 and rectangle.x0 < 460)
        or 325 <= rectangle.y0 < 431
    )


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


def application_inventory(source: fitz.Document) -> dict:
    inventory = {
        "retained": [], "excluded": [], "excluded_regions": [],
        "visible": [], "coded": [], "aliases": [], "counts": Counter(), "ledger": [],
    }
    for page_index, page in enumerate(source):
        for widget in page.widgets() or []:
            value = str(widget.field_value or "").strip()
            if not value:
                continue
            rectangle = widget.rect
            if is_professional_application_value(page_index, rectangle):
                inventory["retained"].append(value)
                continue
            kind, token = application_disposition(page_index, rectangle)
            if widget.field_type == fitz.PDF_WIDGET_TYPE_TEXT:
                inventory["excluded"].append(value)
                inventory["excluded_regions"].append((page_index, value, rectangle))
            if kind == "alias":
                inventory["aliases"].append((page_index, token, rectangle))
                inventory["counts"]["ALIAS"] += 1
                inventory["ledger"].append((f"APP-{page_index + 1}", rectangle, "ALIAS"))
                continue
            hits = [hit for hit in page.search_for(value) if hit.intersects(rectangle)]
            if hits:
                regions = [hit + (-2, -1, 2, 1) for hit in hits]
            else:
                height = min(rectangle.height, 18.0)
                regions = [fitz.Rect(rectangle.x0, rectangle.y0, rectangle.x1, rectangle.y0 + height)]
            inventory["visible"].extend((page_index, region) for region in regions)
            inventory["coded"].extend((page_index, token, region) for region in regions if region.width >= 28 and region.height >= 7)
            inventory["counts"][token] += 1
            inventory["ledger"].append((f"APP-{page_index + 1}", rectangle, token))
    fragments = [entry for entry in inventory["ledger"] if entry[0] == "APP-1" and entry[2] == "CONTACT" and entry[1].x0 >= 430 and 180 <= entry[1].y0 < 210]
    if len(fragments) > 1:
        merged = fitz.Rect(fragments[0][1])
        for entry in fragments[1:]:
            merged.include_rect(entry[1])
        inventory["ledger"] = [entry for entry in inventory["ledger"] if entry not in fragments] + [("APP-1", merged, "CONTACT")]
        inventory["counts"]["CONTACT"] -= len(fragments) - 1
    return inventory


def withholding_regions(page: fitz.Page) -> tuple[list[fitz.Rect], list[fitz.Rect]]:
    identity = [
        nominal(page, 176, 163, 272, 179), nominal(page, 323, 163, 443, 179),
        nominal(page, 35, 187, 300, 202), nominal(page, 323, 187, 580, 202),
        nominal(page, 35, 211, 170, 227), nominal(page, 175, 211, 270, 227),
        nominal(page, 275, 211, 440, 227), nominal(page, 444, 211, 580, 227),
    ]
    declaration = [
        nominal(page, 66, 247, 81, 262), nominal(page, 489, 267, 508, 282),
        nominal(page, 493, 279, 585, 297), nominal(page, 124, 369, 139, 384),
        nominal(page, 425, 386, 443, 403), nominal(page, 425, 405, 526, 424),
    ]
    return identity, declaration


def withholding_reason_regions(page: fitz.Page, declarations: list[fitz.Rect]) -> list[tuple[str, fitz.Rect]]:
    display = [
        nominal(page, 176, 170, 272, 179),
        nominal(page, 35, 194, 300, 202), nominal(page, 323, 194, 580, 202),
        nominal(page, 35, 219, 170, 227), nominal(page, 175, 219, 270, 227),
        nominal(page, 275, 219, 440, 227), nominal(page, 444, 219, 580, 227),
    ]
    return [("GOV-ID", display[0])] + [("CONTACT", region) for region in display[1:]] + [
        ("TAX", region) for region in declarations
    ]


def eligibility_regions(page: fitz.Page) -> list[fitz.Rect]:
    return [
        nominal(page, 42, 214, 222, 230), nominal(page, 224, 214, 365, 230),
        nominal(page, 379, 214, 411, 230), nominal(page, 42, 241, 350, 257),
        nominal(page, 416, 241, 555, 257), nominal(page, 42, 269, 210, 285),
        nominal(page, 211, 269, 348, 285), nominal(page, 350, 269, 412, 285),
        nominal(page, 416, 269, 555, 285), nominal(page, 296, 295, 311, 312),
        nominal(page, 112, 351, 235, 381), nominal(page, 376, 351, 500, 381),
    ]


def clipped_values(page: fitz.Page, regions: list[fitz.Rect]) -> list[str]:
    values = []
    for rectangle in regions:
        value = norm(page.get_text("text", clip=rectangle))
        if value:
            values.append(value)
    return values


def centered_words(page: fitz.Page, rectangle: fitz.Rect) -> str:
    words = []
    for x0, y0, x1, y1, value, *_rest in page.get_text("words", sort=True):
        center = fitz.Point((x0 + x1) / 2, (y0 + y1) / 2)
        if center in rectangle:
            words.append(value)
    return norm(" ".join(words))


def large_image_digests(document: fitz.Document, page: fitz.Page) -> set[str]:
    digests = set()
    page_area = page.rect.width * page.rect.height
    for item in page.get_images(full=True):
        xref = item[0]
        if not any(rect.width * rect.height >= page_area * 0.60 for rect in page.get_image_rects(xref)):
            continue
        image = document.extract_image(xref).get("image", b"")
        if image:
            digests.add(hashlib.sha256(image).hexdigest())
    return digests


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate_source_pages(output: fitz.Document) -> tuple[int, bool]:
    """Find where the preserved source block begins.

    The block is located by testing whether the whole ordered anchor set lands at
    a candidate start, not by taking the first page that happens to mention the
    application. The control sheet is required to list the source sections and
    their page ranges, so it legitimately names the application section on the
    leading page; treating that mention as the start of the source block would
    shift every anchor by one page and reject an otherwise correct packet over a
    choice of section wording that neither the assignment nor the source material
    fixes. Both admissible starts are tested and the first fully aligned one wins.
    The requirement itself is unchanged: all six anchors must sit at their exact
    relative offsets and the packet must carry between start + 8 and start + 11
    pages.
    """
    for start in (0, 1):
        if not start + 8 <= output.page_count <= start + 11:
            continue
        if all(
            contains_phrase(output[start + relative].get_text(), anchor)
            for relative, anchor in ORDERED_ANCHORS
        ):
            return start, True
    mentions = [
        index for index, page in enumerate(output)
        if contains_phrase(page.get_text(), "EMPLOYMENT APPLICATION")
    ]
    return (mentions[0] if mentions else 0), False


def row_has_count(page: fitz.Page, code: str, count: int) -> bool:
    code_hits = page.search_for(code)
    count_hits = page.search_for(str(count))
    return any(
        number.x0 > label.x1 and abs((number.y0 + number.y1) - (label.y0 + label.y1)) <= 8
        for label in code_hits for number in count_hits
    )


def legacy_row_has_fields(page: fitz.Page, values: tuple[str, str, str, str]) -> bool:
    hits = [page.search_for(value) for value in values]
    if any(not group for group in hits):
        return False
    for first in hits[0]:
        for second in hits[1]:
            for third in hits[2]:
                for fourth in hits[3]:
                    rectangles = (first, second, third, fourth)
                    centers = [(rectangle.y0 + rectangle.y1) / 2 for rectangle in rectangles]
                    if max(centers) - min(centers) <= 8 and first.x0 < second.x0 < third.x0 < fourth.x0:
                        return True
    return False


def control_heading(text):
    # Equivalent professional control-sheet titles; no prescribed exact title.
    return bool(re.search(r"\bprivacy\b.{0,40}\breview\b.{0,40}\bcontrol\b|\bprivacy\b.{0,40}\bcontrol\b.{0,40}\breview\b", norm(text)))


def row_has_fields(page, values):
    words = page.get_text("words", sort=True)
    # Header x positions define roles, allowing any column order.
    lines = {}
    for word in words:
        lines.setdefault(round((word[1] + word[3]) / 2), []).append(word)
    header = next((ws for ws in lines.values() if {"row", "action", "outcome"} <= {w[4].lower() for w in ws}), [])
    if not header:
        return False
    columns = {}
    for w in header:
        token = w[4].lower()
        if token in ("source", "row", "action", "outcome"):
            columns[{"source": "source", "row": "row", "action": "action", "outcome": "outcome"}[token]] = w[0]
    if set(columns) != {"source", "row", "action", "outcome"}:
        return False
    order = sorted(columns, key=columns.get)
    edges = [columns[k] - 8 for k in order] + [page.rect.width]
    for ws in lines.values():
        found = {k: " ".join(w[4] for w in sorted(ws, key=lambda w:w[0]) if edges[i] <= w[0] < edges[i+1]) for i,k in enumerate(order)}
        if all(norm(found[k]) == norm(v) for k,v in zip(("source", "row", "action", "outcome"), values)):
            return True
    return False


def vector_signature(shape):
    def canonical(value):
        if isinstance(value, (fitz.Point, fitz.Rect, fitz.Quad)):
            return tuple(round(float(v), 3) for v in value)
        if isinstance(value, (tuple, list)):
            return tuple(canonical(v) for v in value)
        if isinstance(value, float):
            return round(value, 3)
        return value
    return repr(canonical((shape.get("type"), shape.get("items"), shape.get("color"), shape.get("fill"))))


def recoverable_payload(output, sources, source_start, source_packet, direct_values):
    # An attached source or other unrequested payload bypasses page extraction.
    attachments = output.embfile_count()
    blob = norm(" ".join(str(v) for v in (output.metadata or {}).values()))
    if output.xref_xml_metadata():
        blob += " " + norm(output.get_xml_metadata())
    metadata_leak = any(contains_phrase(blob, v) for v in direct_values)
    residual = []
    residual_regions = set()
    declarations = []
    if source_packet:
        _, declarations = withholding_regions(sources[1][0])
        # Only dark stroked response marks carry the source choice. The source
        # also contains empty-box fills and white layout strokes in these
        # regions; retaining those is not recoverable private content.
        expected = {}
        for shape in sources[1][0].get_drawings():
            color = shape.get("color")
            region_indexes = [index for index, region in enumerate(declarations)
                              if shape["rect"] in region]
            if (region_indexes and shape.get("type") == "s" and color
                    and max(color) < 0.5
                    and any(item[0] == "l" for item in shape["items"])):
                expected[vector_signature(shape)] = region_indexes[0]
        for shape in output[source_start + 6].get_drawings():
            signature = vector_signature(shape)
            if signature in expected:
                residual.append(tuple(shape["rect"]))
                residual_regions.add(expected[signature])
    global_unsafe = bool(attachments or metadata_leak)
    vector_integrity = (1.0 - len(residual_regions) / len(declarations)) if declarations else 1.0
    return {"attachments": attachments, "metadata_identifier_leak": metadata_leak,
            "residual_private_vector_objects": residual,
            "residual_private_vector_regions": sorted(residual_regions),
            "private_choice_vector_integrity": vector_integrity,
            "global_unsafe": global_unsafe,
            "unsafe": bool(global_unsafe or residual_regions)}


def toc_has(toc: list[list], level: int, page: int, keywords: tuple[str, ...]) -> bool:
    return any(
        int(item[0]) == level and int(item[2]) == page
        and all(keyword in norm(str(item[1])) for keyword in keywords)
        for item in toc
    )


FORMULAS = {
    "strict": (
        "weighted continuous score over source-derived privacy, retention, "
        "pseudonym, disposition, control, register, fidelity and hygiene "
        "fractions, zeroed by the readability, input-integrity, source-packet "
        "and direct-identifier/global-payload gates; residual private-choice "
        "vectors proportionally reduce the privacy and disposition dimensions"
    ),
    "lenient": (
        "1 iff the delivered PDF alone satisfies the whole delivery contract: "
        "present, opens unencrypted, carries every requested packet part, the "
        "control sheet leads and names its alias and every field slot, every "
        "source page carries text, every register page announces itself and "
        "holds at least one disposed row, and the navigation objects exist; "
        "otherwise 0"
    ),
}


def failure(strict: float, lenient: float, delivery: dict, gates: dict, error: str) -> dict:
    return {
        "reward": strict,
        "rewards": {"strict": strict, "lenient": lenient},
        "reward_formulas": dict(FORMULAS),
        "reward_strict": strict,
        "reward_lenient": lenient,
        "gates": gates,
        "delivery_contract": delivery,
        "error": error,
    }


def delivery_contract(path: Path) -> dict:
    """The lenient lens: was a complete, parseable, partitioned packet handed over?

    Everything here is read out of the delivered file itself. No source PDF, no
    ground-truth record and no strict intermediate is consulted, and no expected
    response value, region, count or code assignment is checked. The questions
    are only: does the artifact exist, does it open, does it carry every
    requested part, does each part announce itself, is each part filled in
    rather than left as an empty shell, and are the navigation objects there.
    """
    checks = dict.fromkeys(DELIVERY_CHECKS, False)
    if not path.is_file():
        return checks
    checks["deliverable_present"] = True
    try:
        document = fitz.open(path)
    except Exception:
        return checks
    try:
        if document.needs_pass or document.page_count < 1:
            return checks
        checks["pdf_opens_unencrypted"] = True
        pages = [page.get_text() for page in document]
        control_count, source_count, register_count = PACKET_PARTS
        checks["packet_has_every_part"] = (
            len(pages) == control_count + source_count + register_count
        )
        # The remaining clauses stay individually diagnostic even when the part
        # count is wrong: the control sheet is whatever leads, the register block
        # is whatever trails, and the source block is what sits between them.
        if len(pages) < control_count + register_count + 1:
            return checks

        control = pages[0]
        checks["control_sheet_leads_packet"] = (
            control_heading(control)
            and contains_phrase(control, REVIEW_ALIAS)
        )
        checks["control_sheet_field_slots_filled"] = (
            all(contains_phrase(control, label) for label in REGISTER_RANGE)
            and all(contains_phrase(control, code) for code in ACTION_CODES)
        )

        source_block = pages[control_count:len(pages) - register_count]
        checks["source_block_carries_text"] = all(norm(text) for text in source_block)

        register_block = pages[len(pages) - register_count:]
        checks["register_block_present"] = all(
            contains_phrase(text, REGISTER_TITLE) for text in register_block
        )
        checks["register_rows_populated"] = all(
            any(contains_phrase(text, outcome) for outcome in ROW_OUTCOMES)
            for text in register_block
        )

        checks["navigation_objects_present"] = (
            bool(document.get_toc(simple=True)) and bool(document.get_page_labels())
        )
    finally:
        document.close()
    return checks


def score(path: Path) -> dict:
    delivery = delivery_contract(path)
    lenient = 1.0 if all(delivery.values()) else 0.0
    gates = {
        "readable_pdf": False,
        "input_integrity": False,
        "complete_source_packet": False,
        "direct_identifier_leak": False,
    }
    if not path.is_file():
        return failure(0.0, lenient, delivery, gates, "missing deliverable")

    try:
        ground_truth = json.loads((ROOT / "tests" / "ground_truth.json").read_text(encoding="utf-8"))
        locked_inputs = ground_truth["locked_inputs"]
        gates["input_integrity"] = all(sha256(source) == locked_inputs[source.name] for source in SOURCES)
        output = fitz.open(path)
        sources = [fitz.open(source) for source in SOURCES]
    except Exception as exc:
        return failure(0.0, lenient, delivery, gates, f"unreadable PDF: {exc}")

    source_pages = [page for document in sources for page in document]
    gates["readable_pdf"] = output.page_count > 0 and not output.needs_pass
    source_start, gates["complete_source_packet"] = locate_source_pages(output)
    output_text = "\n".join(page.get_text() for page in output)
    searchable_blob = norm(output_text + "\n" + external_text(path))

    application = application_inventory(sources[0])
    withhold_identity, withhold_declaration = withholding_regions(sources[1][0])
    eligibility = eligibility_regions(sources[2][0])
    flattened_excluded = clipped_values(sources[1][0], withhold_identity + withhold_declaration)
    flattened_excluded += clipped_values(sources[2][0], eligibility)
    excluded_values = [value for value in application["excluded"] + flattened_excluded if len(norm(value)) >= 3]
    privacy_atoms = [not contains_phrase(searchable_blob, value) for value in excluded_values]

    no_widgets = all(not list(page.widgets() or []) for page in output)
    no_annotations = all(not list(page.annots() or []) for page in output)
    privacy_atoms.extend([no_widgets, no_annotations])
    if gates["complete_source_packet"]:
        privacy_atoms.extend(
            not contains_phrase(output[source_start + page_index].get_text("text", clip=rectangle), value)
            for page_index, value, rectangle in application["excluded_regions"]
        )
        source_scan_digests = large_image_digests(sources[2], sources[2][0])
        output_scan_digests = large_image_digests(output, output[source_start + 7])
        privacy_atoms.append(not bool(source_scan_digests & output_scan_digests))

    direct_gate_values = []
    for page, regions in ((sources[1][0], withhold_identity), (sources[2][0], eligibility[:9])):
        direct_gate_values.extend(value for value in clipped_values(page, regions) if len(norm(value)) >= 3)
    direct_gate_values.extend(
        value for page_index, value, rectangle in application["excluded_regions"]
        if page_index == 0 and rectangle.y0 < 260 and len(norm(value)) >= 3
    )
    gates["direct_identifier_leak"] = any(contains_phrase(searchable_blob, value) for value in direct_gate_values)
    payload_audit = recoverable_payload(output, sources, source_start, gates["complete_source_packet"], direct_gate_values)
    gates["recoverable_private_payload"] = payload_audit["unsafe"]
    # A packet with recoverable source/private payload is not a usable redacted
    # handoff, even when its page/control/register shell is complete.
    if payload_audit["unsafe"]:
        lenient = 0.0

    required_values = application["retained"] + [
        centered_words(sources[1][0], nominal(sources[1][0], 35, 140, 55, 154)),
        norm(sources[1][0].get_text("text", clip=nominal(sources[1][0], 35, 170, 105, 180))),
        norm(sources[1][0].get_text("text", clip=nominal(sources[1][0], 178, 145, 310, 154))),
        "this will be completed", "hr or your judge's chambers", "address of person certifying the i-9",
    ]
    required_values = [value for value in required_values if len(norm(value)) >= 2]
    retention_atoms = [contains_phrase(searchable_blob, value) for value in required_values]

    pseudonym_atoms: list[bool] = []
    reason_atoms: list[bool] = []
    expected_counts = Counter(application["counts"])
    expected_counts.update({
        "ALIAS": 4, "CONTACT": 10, "GOV-ID": 2, "DOB": 1,
        "SIGN": 1, "DATE": 1, "TAX": len(withhold_declaration), "AUTH": 1,
    })
    withholding_ledger = [
        ("TAX-1", rectangle, code)
        for rectangle, code in zip(
            withhold_identity,
            ("GOV-ID", "ALIAS", "CONTACT", "CONTACT", "CONTACT", "CONTACT", "CONTACT", "CONTACT"),
        )
    ] + [("TAX-1", rectangle, "TAX") for rectangle in withhold_declaration]
    eligibility_ledger = [
        ("ELIG-1", rectangle, code)
        for rectangle, code in zip(
            eligibility,
            ("ALIAS", "ALIAS", "ALIAS", "CONTACT", "DOB", "CONTACT", "CONTACT", "CONTACT", "GOV-ID", "AUTH", "SIGN", "DATE"),
        )
    ]
    if gates["complete_source_packet"]:
        for page_index, token, rectangle in application["aliases"]:
            local = centered_words(output[source_start + page_index], rectangle)
            pseudonym_atoms.append(
                contains_phrase(local, token)
                and black_fraction(output[source_start + page_index], rectangle) < 0.45
            )
        w_page = output[source_start + 6]
        w_alias = nominal(w_page, 323, 163, 443, 181)
        pseudonym_atoms.append(
            contains_phrase(centered_words(w_page, w_alias), "SUBJECT 07")
            and black_fraction(w_page, w_alias) < 0.45
        )
        e_page = output[source_start + 7]
        for token, rectangle in zip(("07", "SUBJECT", "S"), eligibility[:3]):
            pseudonym_atoms.append(
                contains_phrase(centered_words(e_page, rectangle), token)
                and black_fraction(e_page, rectangle) < 0.45
            )

        for page_index, rectangle in application["visible"]:
            reason_atoms.append(black_fraction(output[source_start + page_index], rectangle) >= 0.58)
        for page_index, code, rectangle in application["coded"]:
            reason_atoms.append(contains_phrase(centered_words(output[source_start + page_index], rectangle), code))

        for code, rectangle in withholding_reason_regions(w_page, withhold_declaration):
            reason_atoms.append(black_fraction(w_page, rectangle) >= 0.16)
            if rectangle.width >= 28 and rectangle.height >= 7:
                reason_atoms.append(contains_phrase(centered_words(w_page, rectangle), code))
        eligibility_codes = ("CONTACT", "DOB", "CONTACT", "CONTACT", "CONTACT", "GOV-ID", "AUTH", "SIGN", "DATE")
        for code, rectangle in zip(eligibility_codes, eligibility[3:]):
            reason_atoms.append(black_fraction(e_page, rectangle) >= 0.16)
            if rectangle.width >= 28 and rectangle.height >= 7:
                reason_atoms.append(contains_phrase(centered_words(e_page, rectangle), code))

    control_atoms: list[bool] = []
    has_control = source_start == 1 and output.page_count >= 9
    if has_control:
        control = output[0]
        control_text = control.get_text()
        control_atoms.extend([
            control.rect == fitz.Rect(0, 0, 612, 792),
            control_heading(control_text),
            contains_phrase(control_text, "SUBJECT 07"),
            page_range_present(control_text, "Application", "APP", 1, 6),
            contains_phrase(control_text, "Withholding record TAX-1"),
            contains_phrase(control_text, "Employment eligibility record ELIG-1"),
            page_range_present(control_text, "Disposition register", "AUD", 1, 3),
        ])
        control_atoms.extend(row_has_count(control, code, expected_counts[code]) for code in ACTION_CODES)
    else:
        control_atoms.extend([False] * (7 + len(ACTION_CODES)))

    toc = output.get_toc(simple=True)
    toc_contract = [
        (1, 1, ("control",)), (1, 2, ("application",)),
        (1, 8, ("withholding",)), (1, 9, ("eligibility",)),
        (1, 10, ("disposition", "register")),
        (2, 10, ("application",)), (2, 11, ("withholding",)), (2, 12, ("eligibility",)),
    ]
    expected_labels = [
        {"startpage": 0, "prefix": "CTRL-", "firstpagenum": 1, "style": "D"},
        {"startpage": 1, "prefix": "APP-", "firstpagenum": 1, "style": "D"},
        {"startpage": 7, "prefix": "TAX-", "firstpagenum": 1, "style": "D"},
        {"startpage": 8, "prefix": "ELIG-", "firstpagenum": 1, "style": "D"},
        {"startpage": 9, "prefix": "AUD-", "firstpagenum": 1, "style": "D"},
    ]
    metadata = output.metadata or {}
    controlled_metadata = (
        metadata.get("title") == "Privacy-Safe Onboarding Review Packet"
        and metadata.get("subject") == "HR archival review"
        and metadata.get("keywords") == "restricted; redacted"
        and not any(metadata.get(key) for key in ("author", "creator", "producer", "creationDate", "modDate"))
    )
    control_atoms.extend([
        all(toc_has(toc, level, page, keywords) for level, page, keywords in toc_contract),
        output.get_page_labels() == expected_labels,
        controlled_metadata,
    ])

    register_format_atoms: list[bool] = []
    register_row_atoms: list[bool] = []
    register_specs = [
        (9, "Application", application["ledger"]),
        (10, "Withholding record", withholding_ledger),
        (11, "Employment eligibility record", eligibility_ledger),
    ]
    has_register = source_start == 1 and output.page_count == 12
    register_row_counts: list[bool] = []
    for page_index, section, raw_entries in register_specs:
        entries = sorted(raw_entries, key=lambda item: (int(item[0].split("-")[-1]), item[1].y0, item[1].x0))
        page_present = source_start == 1 and output.page_count > page_index
        if page_present:
            register_page = output[page_index]
            page_text = register_page.get_text()
            register_format_atoms.extend([
                register_page.rect == fitz.Rect(0, 0, 612, 792),
                contains_phrase(page_text, "FIELD DISPOSITION REGISTER"),
                contains_phrase(page_text, section),
                contains_phrase(page_text, "REPLACED") or contains_phrase(page_text, "REMOVED"),
            ])
            for sequence, (page_label, _rectangle, code) in enumerate(entries, start=1):
                outcome = "REPLACED" if code == "ALIAS" else "REMOVED"
                register_row_atoms.append(row_has_fields(register_page, (page_label, f"{sequence:02d}", code, outcome)))
            observed_rows = len(register_page.search_for("REPLACED")) + len(register_page.search_for("REMOVED"))
            register_row_counts.append(observed_rows == len(entries))
            register_format_atoms.append(observed_rows == len(entries))
        else:
            register_format_atoms.extend([False] * 5)
            register_row_atoms.extend([False] * len(entries))
            register_row_counts.append(False)
    register_reconciled = has_register and all(register_row_atoms) and all(register_row_counts)
    purpose_disposition_fraction = (
        fraction(reason_atoms) + fraction(register_row_atoms)
    ) / 2

    geometry_atoms: list[bool] = []
    if gates["complete_source_packet"]:
        for index, source_page in enumerate(source_pages):
            output_page = output[source_start + index]
            geometry_atoms.append(output_page.rect == source_page.rect and output_page.rotation == source_page.rotation)
            geometry_atoms.append(len(output_page.get_text()) >= int(len(source_page.get_text()) * 0.80))
        geometry_atoms.extend(
            contains_phrase(output[source_start + page_index].get_text(), anchor)
            for page_index, anchor in ORDERED_ANCHORS
        )

    xml_cleared = output.xref_xml_metadata() == 0
    delivery_atoms = [path.suffix.casefold() == ".pdf", xml_cleared, no_widgets, no_annotations]

    retention_fraction = fraction(retention_atoms)
    vector_integrity = payload_audit["private_choice_vector_integrity"]
    dimension_scores = {
        "selective_privacy": WEIGHTS["selective_privacy"] * fraction(privacy_atoms) * retention_fraction * vector_integrity,
        "required_retention": WEIGHTS["required_retention"] * retention_fraction,
        "pseudonym_consistency": WEIGHTS["pseudonym_consistency"] * fraction(pseudonym_atoms) * retention_fraction,
        "purpose_based_disposition": WEIGHTS["purpose_based_disposition"] * purpose_disposition_fraction * retention_fraction * vector_integrity,
        "control_and_navigation": WEIGHTS["control_and_navigation"] * fraction(control_atoms) * retention_fraction,
        "register_structure": WEIGHTS["register_structure"] * fraction(register_format_atoms) * retention_fraction,
        "document_fidelity": WEIGHTS["document_fidelity"] * fraction(geometry_atoms),
        "delivery_hygiene": WEIGHTS["delivery_hygiene"] * fraction(delivery_atoms) * retention_fraction,
    }
    reward = sum(dimension_scores.values())
    if (
        not gates["readable_pdf"] or not gates["input_integrity"]
        or not gates["complete_source_packet"] or gates["direct_identifier_leak"]
        or payload_audit["global_unsafe"]
    ):
        reward = 0.0
    reward = round(reward, 6)
    privacy_ready = (
        gates["readable_pdf"] and gates["input_integrity"]
        and gates["complete_source_packet"] and not gates["direct_identifier_leak"]
        and not gates["recoverable_private_payload"]
        and all(privacy_atoms) and all(retention_atoms) and all(pseudonym_atoms)
        and all(reason_atoms) and register_reconciled
        and all(control_atoms) and all(register_format_atoms)
    )
    lenient = float(bool(lenient) and privacy_ready)
    result = {
        "reward": reward,
        "rewards": {"strict": reward, "lenient": lenient},
        "reward_formulas": dict(FORMULAS),
        "dimension_scores": {key: round(value, 6) for key, value in dimension_scores.items()},
        "reward_strict": reward,
        "reward_lenient": lenient,
        "gates": gates,
        "delivery_contract": delivery,
        "atoms": {
            "privacy": privacy_atoms, "retention": retention_atoms,
            "pseudonym": pseudonym_atoms, "reason_coding": reason_atoms,
            "control_navigation": control_atoms, "register_rows": register_row_atoms,
            "register_structure": register_format_atoms, "fidelity": geometry_atoms,
            "delivery": delivery_atoms,
        },
        "derived_action_counts": dict(expected_counts),
        "recoverable_payload_audit": payload_audit,
        "private_choice_vector_integrity": vector_integrity,
        "register_reconciled": register_reconciled,
    }
    output.close()
    for document in sources:
        document.close()
    return result


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/output/sanitized_onboarding_packet.pdf")
    print(json.dumps(score(target), ensure_ascii=True, separators=(",", ":")))

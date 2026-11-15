#!/usr/bin/env python3
"""Deterministic, relation-aware scorer for the HDR test-case workbook task."""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


HERE = Path(__file__).resolve().parent
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}

WELL_FORMED_STEP_QUALITY = 0.6
WELL_FORMED_EXPECTED_QUALITY = 2 / 3

REWARD_FORMULAS = {
    "strict": "max(0, min(1, (sum(six published independent dimension points)-unique source-bound deductions)/100)); no score caps or coverage multipliers",
    "lenient": "1 iff the XLSX has all six fields, all nine required objectives, all five correct acceptance relationships, defensible separated equipment roles, and executable/checkable content; otherwise 0",
}


HEADER_ALIASES = {
    "test_id": ["testid", "id", "caseid"],
    "module": ["testmodule", "module", "hdrmodule"],
    "title": ["testcasename", "testcase", "casename", "testitem", "testobjective", "testitemandobjective"],
    "preconditions": ["preconditions", "precondition", "prerequisites", "testconditions"],
    "steps": ["teststeps", "steps", "procedure", "testprocedure", "stimulusandprocedure"],
    "expected": ["expectedresult", "expectedresults", "acceptancecriteria", "expectedoutcome", "expectedresultevidence"],
}


RELATION_COMPONENTS = {
    "HDR-001": [
        [["dolby vision", "dv"]], [["dynamic metadata"]],
        [["tone mapping", "tone map", "frame-to-frame rendering", "metadata changes"]],
    ],
    "HDR-002": [
        [["dolby vision", "dv"]], [["p3d65", "p3 d65", "color gamut", "colour gamut"]],
        [["10 bit", "10-bit", "color depth", "colour depth"]],
        [["skin tone", "skin-tone", "delta e", "deltae"]],
    ],
    "HDR-003": [
        [["dolby vision", "dv"]], [["sdr"]],
        [["fallback", "down-conversion", "backward compatibility", "sdr layer"]],
    ],
    "HDR-004": [
        [["hlg", "hybrid log gamma"]],
        [["oetf", "eotf", "transfer function", "tone curve", "tone-curve", "transfer curve", "brightness curve", "grayscale", "grey scale", "ramp"]],
    ],
    "HDR-005": [
        [["hlg"]], [["sdr"]],
        [["fallback", "backward compatibility", "down-conversion", "mapped image"]],
    ],
    "HDR-006": [
        [["hlg"]], [["brightness", "luminance", "dynamic range"]],
        [["10%", "10 percent", "white window"]],
    ],
    "HDR-007": [
        [["hdr10 pro", "hdr 10 pro"]],
        [["dynamic tone mapping", "tone mapping", "tone-mapping"]],
        [["compare", "comparison", "enabled", "disabled", "baseline"]],
    ],
    "HDR-008": [
        [["hdr10 pro", "hdr 10 pro"]],
        [["color gamut", "colour gamut", "p3d65", "dci-p3", "dci p3"]],
        [["color accuracy", "colour accuracy", "delta e", "deltae", "skin tone"]],
    ],
    "HDR-009": [
        [["hdr10 pro", "hdr 10 pro"]], [["dolby vision", "dv"]], [["hlg"]],
        [["switch", "switching", "transition"]],
    ],
}


TITLE_TOPICS = {
    "HDR-001": ["dynamic metadata", "tone mapping", "tone-mapping"],
    "HDR-002": ["p3d65", "p3-d65", "p3 d65", "dci-p3", "dci p3", "color gamut", "colour gamut", "color depth", "colour depth", "color accuracy", "colour accuracy", "skin tone", "skin-tone"],
    "HDR-003": ["fallback", "sdr", "backward compatibility", "down-conversion"],
    "HDR-004": ["oetf", "eotf", "transfer function", "tone curve", "tone-curve", "transfer curve", "curve accuracy", "grayscale", "grey scale", "ramp"],
    "HDR-005": ["fallback", "sdr", "backward compatibility", "down-conversion"],
    "HDR-006": ["brightness", "luminance", "dynamic range"],
    "HDR-007": ["tone mapping", "tone-mapping"],
    "HDR-008": ["color gamut", "colour gamut", "color accuracy", "colour accuracy"],
    "HDR-009": ["switch", "switching", "transition"],
}


def norm(value: object) -> str:
    value = unicodedata.normalize("NFKC", str(value)).lower()
    value = value.replace("≥", ">=").replace("≤", "<=").replace("–", "-").replace("—", "-")
    value = value.replace("≥", ">=").replace("≤", "<=").replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9%+<>=.]+", "", value)


def column_index(headers: list[str], field: str) -> int | None:
    normalized = [norm(value) for value in headers]
    for alias in HEADER_ALIASES[field]:
        if norm(alias) in normalized:
            return normalized.index(norm(alias))
    return None


def canonical_rows(matrix: list[list[str]]) -> tuple[list[dict[str, str]], list[str]]:
    if not matrix:
        return [], []
    headers = [str(value).strip() for value in matrix[0]]
    indices = {field: column_index(headers, field) for field in HEADER_ALIASES}
    rows: list[dict[str, str]] = []
    for values in matrix[1:]:
        record = {}
        for field, index in indices.items():
            record[field] = str(values[index]).strip() if index is not None and index < len(values) and values[index] is not None else ""
        if any(record.values()):
            rows.append(record)
    found = [field for field, index in indices.items() if index is not None]
    return rows, found


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//a:t", NS))
    value = cell.find("a:v", NS)
    if value is None or value.text is None:
        return ""
    if kind == "s":
        return shared[int(value.text)]
    return value.text


def read_xlsx(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//a:t", NS)) for item in root.findall("a:si", NS)]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {item.attrib["Id"]: item.attrib["Target"] for item in relations.findall("r:Relationship", REL_NS)}
        matrices: list[list[list[str]]] = []
        for sheet in workbook.findall("a:sheets/a:sheet", NS):
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_map[rel_id].replace("\\", "/").lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            root = ET.fromstring(archive.read(target))
            matrix: list[list[str]] = []
            for row in root.findall(".//a:sheetData/a:row", NS):
                values: list[str] = []
                for cell in row.findall("a:c", NS):
                    ref = cell.attrib.get("r", "A1")
                    letters = re.match(r"[A-Z]+", ref)
                    column = 0
                    for letter in letters.group(0) if letters else "A":
                        column = column * 26 + ord(letter) - 64
                    while len(values) < column - 1:
                        values.append("")
                    values.append(_cell_text(cell, shared))
                matrix.append(values)
            matrices.append(matrix)

    # A valid deliverable may place cover notes before the test-case worksheet.
    # Select the worksheet whose first row best matches the required columns;
    # never assume that the first worksheet contains the answer table.
    def sheet_rank(matrix: list[list[str]]) -> tuple[int, int]:
        if not matrix:
            return (0, 0)
        headers = [str(value).strip() for value in matrix[0]]
        recognized = sum(column_index(headers, field) is not None for field in HEADER_ALIASES)
        return (recognized, len(matrix))

    return max(matrices, key=sheet_rank, default=[])


def read_csv(path: Path) -> list[list[str]]:
    text = path.read_text(encoding="utf-8-sig", errors="strict")
    return [list(row) for row in csv.reader(text.splitlines())]


def read_markdown(path: Path) -> list[list[str]]:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in lines:
        if line.strip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    compatible = [
        table for table in tables
        if table and sum(column_index(table[0], field) is not None for field in HEADER_ALIASES) >= 4
    ]
    if not compatible:
        return []
    merged = list(compatible[0])
    first_header = [norm(value) for value in compatible[0][0]]
    for table in compatible[1:]:
        if [norm(value) for value in table[0]] == first_header:
            merged.extend(table[1:])
    return merged


def load_submission(path: Path) -> tuple[list[dict[str, str]], list[str], str | None, str]:
    try:
        suffix = path.suffix.lower()
        if suffix == ".xlsx":
            matrix = read_xlsx(path)
            kind = "xlsx"
        elif suffix == ".csv":
            matrix = read_csv(path)
            kind = "csv"
        elif suffix in {".md", ".markdown"}:
            matrix = read_markdown(path)
            kind = "markdown"
        else:
            return [], [], "unsupported deliverable format", suffix.lstrip(".") or "unknown"
        rows, found = canonical_rows(matrix)
        return rows, found, None, kind
    except Exception as exc:
        return [], [], str(exc), path.suffix.lower().lstrip(".") or "unknown"


def atom_match(text: str, atom: list[list[str]]) -> bool:
    return all(any(phrase_present(text, option) for option in slot) for slot in atom)


def phrase_present(text: str, option: str) -> bool:
    """Match semantic aliases without treating short acronyms as substrings.

    In particular, the Dolby Vision alias ``DV`` must not match incidental
    character pairs inside words such as ``advanced`` or ``device``.
    """
    def normalize_phrase(value: str) -> str:
        value = unicodedata.normalize("NFKC", value).lower()
        value = re.sub(r"[\-‐‑‒–—]+", " ", value)
        value = re.sub(r"\s*%", "%", value)
        value = re.sub(r"\b(?:degrees?|deg)\b|°", " degree ", value)
        return re.sub(r"\s+", " ", value).strip()

    normalized_option = normalize_phrase(option)
    normalized_text = normalize_phrase(text)
    pattern = (rf"(?<![a-z0-9]){re.escape(normalized_option)}(?![a-z0-9])"
               if re.fullmatch(r"[a-z0-9]{1,3}", normalized_option)
               else re.escape(normalized_option))
    negative_outcomes = {"black screen", "flicker", "corruption", "corrupted", "banding", "clipping", "color cast", "colour cast"}
    for match in re.finditer(pattern, normalized_text):
        prefix = normalized_text[max(0, match.start() - 18):match.start()]
        directly_negated = re.search(r"(?:\bnot|\bnever|\bincorrect|\bfails?\s+to|\bdoes\s+not|\bdo\s+not)\s+$", prefix)
        if directly_negated and normalized_option not in negative_outcomes:
            continue
        return True
    return False


def concept_coverage(text: str, concepts: list[list[list[str]]]) -> float:
    if not concepts:
        return 1.0
    return sum(atom_match(text, atom) for atom in concepts) / len(concepts)


def module_match(text: str, key: str) -> bool:
    return any(phrase_present(text, alias) for alias in GROUND["module_aliases"][key])


def pair_score(row: dict[str, str], item: dict) -> float:
    row_semantics = " ".join((row["title"], row["steps"], row["expected"]))
    title_score = max(
        concept_coverage(row["title"], item["title"]),
        concept_coverage(row_semantics, item["title"]),
    )
    module_evidence = " ".join((row["module"], row["test_id"], row["title"]))
    module_score = 1.0 if module_match(module_evidence, item["module"]) else 0.0
    identifier_bonus = 1.0 if norm(row["test_id"]) == norm(item["id"]) else 0.0
    return 0.55 * title_score + 0.35 * module_score + 0.10 * identifier_bonus


def related_rows(rows: list[dict[str, str]], item: dict) -> list[int]:
    """Return rows that may jointly express one Gold relationship.

    A case may be split into measurement-specific rows or consolidated with a
    related check.  Requiring a one-row/one-Gold assignment creates false
    negatives, so relation coverage is evaluated over a small item-specific
    row set instead.
    """
    selected: list[int] = []
    components = RELATION_COMPONENTS[item["id"]]
    for index, row in enumerate(rows):
        # Use the declared objective and performed actions for relationship
        # assignment.  Incidental words in an expected-result warning must not
        # turn a different case into a false-positive match.
        semantics = " ".join((row["module"], row["title"], row["steps"]))
        title_signal = concept_coverage(semantics, components)
        module_signal = module_match(" ".join((row["module"], row["title"], row["steps"])), item["module"])
        title_compact = norm(row["title"])
        declared_topic = any(norm(term) in title_compact for term in TITLE_TOPICS[item["id"]])
        explicit_format_title = module_match(row["title"], item["module"])
        if (declared_topic or (explicit_format_title and title_signal >= 0.75)) and title_signal >= 0.5 and module_signal:
            selected.append(index)
    return selected


def combined_field(rows: list[dict[str, str]], indices: list[int], field: str) -> str:
    return " ".join(rows[index][field] for index in indices)


def contains_all(text: str, atoms: list[list[list[str]]]) -> bool:
    return all(atom_match(text, atom) for atom in atoms)


def operational_precondition_quality(text: str) -> float:
    groups = [
        ["connect", "hdmi", "probe", "meter", "generator", "hdr-01"],
        ["warm", "calibrat", "dark room", "ambient", "ready", "stable"],
        ["signal", "pattern", "picture mode", "hdr10", "dolby vision", "hlg", "sdr"],
    ]
    compact = text.lower()
    return sum(any(term in compact for term in group) for group in groups) / len(groups)


def operational_step_quality(text: str) -> float:
    groups = [
        ["configure", "select", "set ", "load", "enable", "disable"],
        ["send", "apply", "display", "play", "switch", "transmit"],
        ["measure", "observe", "inspect", "verify", "calculate", "confirm"],
        ["record", "compare", "capture", "log", "save", "retain"],
        ["1.", "2.", "first", "then", "repeat", "sequential"],
    ]
    compact = text.lower()
    return sum(any(term in compact for term in group) for group in groups) / len(groups)


def operational_expected_quality(text: str) -> float:
    groups = [
        ["recognize", "identify", "detect", "display", "render", "mapping", "curve", "coverage", "brightness", "gamma", "delta e", "response time"],
        ["<", ">", "close to", "no ", "without", "retained", "smooth", "stable", "correct"],
        ["record", "invalid", "condition", "mode", "signal", "pattern", "measurement", "transition"],
    ]
    compact = text.lower()
    return sum(any(term in compact for term in group) for group in groups) / len(groups)


def evidence_bound_quality(specific: float, operational: float, relationship: float) -> float:
    """Blend item-specific evidence with generic procedural quality.

    Generic verbs such as "configure", "measure", and "record" are useful
    quality signals, but they cannot substitute for the case-specific signal,
    measurement, and decision relationship.  Keeping them as a minority
    component prevents fluent boilerplate from receiving near-complete credit.
    """
    if specific >= 1.0:
        return 1.0
    return min(1.0, 0.90 * specific + 0.10 * operational * relationship)


def acceptance_checks(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    checks = [
        ("dolby_vision_p3d65", [
            [["dolby vision", "dv"]], [["p3d65", "p3 d65"]],
            [["close to 100", "near 100", "approximately 100"]],
        ]),
        ("dolby_vision_skin_tone", [
            [["dolby vision", "dv"]], [["skin tone"]], [["delta e", "deltae"]],
            [["<3", "< 3", "less than 3", "below 3"]], [["cie 1931"]], [["2 degree", "2°"]],
        ]),
        ("sdr_fallback_gamma", [
            [["dolby vision", "dv", "hlg"]],
            [["sdr"]], [["fallback", "recovery", "compatibility"]], [["bt.709", "bt709"]],
            [["gamma"]], [["2.2"]],
        ]),
        ("hlg_peak_brightness", [
            [["hlg"]], [["10%", "10 percent"]], [["brightness booster"]],
            [["800 nit", ">=800", "at least 800"]],
        ]),
        ("three_format_switching", [
            [["hdr10 pro", "hdr 10 pro"]], [["dolby vision", "dv"]], [["hlg"]],
            [["switch"]], [["<2 second", "< 2 second", "<2.0 second", "< 2.0 second", "<2.0 s", "<2.00 s", "<2.000 s", "less than 2 second", "below 2 second", "within two second"]],
            [["black screen"]], [["flicker"]], [["corruption", "corrupted"]],
        ]),
    ]
    row_texts = [" ".join(row.values()) for row in rows]
    numeric_patterns={
        "dolby_vision_p3d65":r"(?:close to|near|approximately)\s*100(?:\.0+)?\s*(?:%|percent)",
        "dolby_vision_skin_tone":r"(?:<|less than|below)\s*3(?:\.0+)?(?!\d)(?=\s|[.,;:)]|$)",
        "sdr_fallback_gamma":r"gamma[^\n.;]{0,30}2\.2(?!\d)",
        "hlg_peak_brightness":r"(?:>=|≥|at least)\s*800(?!\d)|800\s*nits?\s*(?:or above|or higher|minimum)",
        "three_format_switching":r"(?:<|less than|below)\s*2(?:\.0+)?\s*(?:s\b|second)|within two seconds?",
    }
    anchors={"dolby_vision_p3d65":r"p3\s*d65", "dolby_vision_skin_tone":r"skin\s*tone|delta\s*e", "sdr_fallback_gamma":r"gamma", "hlg_peak_brightness":r"hlg.*?(?:brightness|luminance)|(?:brightness|luminance).*?hlg", "three_format_switching":r"switch.*?(?:time|second|response)|response.*?switch"}
    asserted_patterns={
        "dolby_vision_p3d65":r"(?:coverage|gamut)[^\n]{0,45}\d+(?:\.\d+)?\s*(?:%|percent)",
        "dolby_vision_skin_tone":r"delta\s*e\s*(?:[<>≤≥=]|less than|greater than|below|above|under|over)\s*\d",
        "sdr_fallback_gamma":r"gamma[^\n]{0,35}\d+\.\d+",
        "hlg_peak_brightness":r"(?:brightness|luminance)[^\n]{0,45}\d+(?:\.\d+)?\s*nits?",
        "three_format_switching":r"(?:response time|switching time)[^\n]{0,35}\d+(?:\.\d+)?\s*(?:s\b|second)",
    }
    out=[]
    for name,atoms in checks:
        relevant=[r for r in rows if re.search(anchors[name]," ".join(r.values()).lower(),re.S)]
        valid=any(contains_all(" ".join(r.values()),atoms) and re.search(numeric_patterns[name],r["expected"].lower()) for r in relevant)
        # Wrong threshold requires an actually stated criterion, not merely omission.
        wrong=[]
        for r in relevant:
            ex=r["expected"].lower()
            if re.search(asserted_patterns[name],ex,re.S) and not re.search(numeric_patterns[name],ex):wrong.append(r["test_id"])
        out.append({"name":name,"hit":bool(valid) and not wrong,"wrong_threshold_rows":wrong})
    return out


def task_deductions(rows: list[dict[str, str]]) -> tuple[float, list[dict[str, object]]]:
    findings: list[dict[str, object]] = []

    def add(row_index: int, category: str, points: float, evidence: str) -> None:
        findings.append({
            "row": row_index + 1,
            "category": category,
            "points": points,
            "evidence": evidence,
        })

    peripheral = {
        "edid_inventory": ["edid hdr capability", "edid/hdr capability", "edid inventory", "edid advertisement"],
        "protected_content": ["hdcp", "protected-content", "protected content", "protected hdr playback"],
        "link_endurance": ["timing and link stability", "link endurance", "playback stability", "switching endurance"],
        "4k120_stress": ["4k/120", "4k 120", "120 hz hdr"],
        "static_logo_retention": ["logo luminance limiting", "static-image protection", "static image protection"],
        "menu_overlay": ["osd/menu overlay", "menu overlay", "osd overlay", "menus, subtitles", "menus, subtitles, and overlays"],
        "cec": ["cec", "simplink"],
        "motion_latency": ["processing latency", "end-to-end delay", "motion test", "motion and low-latency", "game optimizer"],
        "power_endurance": ["long-duration", "long duration", "power consumption", "energy consumption", "power/energy", "energy-control interaction"],
        "chroma_text": ["chroma subsampling", "chroma-format", "timing/chroma", "text/ui legibility", "1-pixel colored text"],
        "hotplug_recovery": ["hot-plug", "hot plug", "source reconnect"],
        "internal_app_playback": ["internal-app", "internal app", "netflix"],
        "audio_earc": ["earc", "dolby atmos", "audio return"],
        "standby_restart": ["standby/wake", "standby and resume", "power-cycle", "ac restart"],
        "nonclaimed_format_boundary": ["hdr10+ non-claimed", "hdr10+ graceful fallback", "hdr vivid non-claimed", "hdr vivid graceful"],
        "input_inventory": ["four-input smoke test", "all four hdmi", "four hdmi inputs"],
    }
    for index, row in enumerate(rows):
        text = " ".join(row.values()).lower()
        title_module = f"{row['module']} {row['title']}".lower()
        for category, terms in peripheral.items():
            if any(term in title_module for term in terms):
                add(index, f"peripheral_{category}", 2.0, row["title"])
                break
        if any(term in row["module"].lower() for term in (
            "pre-test", "post-test", "preparation & configuration", "preparation & instrument control"
        )):
            add(index, "standalone_setup_or_record", 0.5, row["title"])
        if any(term in text for term in ("≥10 min", ">=10 min", "≥2 h", ">=2 h", "2 h of")):
            add(index, "invented_project_duration", 1.25, row["title"])

        for unsupported in ("hdr10+", "hdr vivid"):
            if unsupported in text and any(term in text for term in ("supports", "natively supports", "accepts and identifies")):
                if not any(term in text for term in ("not listed", "unsupported", "do not infer", "without evidence")):
                    add(index, "unsupported_native_format", 5.0, unsupported)

    return sum(float(item["points"]) for item in findings), findings


def grade(path: Path) -> dict:
    rows, headers, parse_error, kind = load_submission(path)
    dimensions = {
        "required_hdr_objective_coverage": 0.0,
        "project_acceptance_relationships": 0.0,
        "evidence_and_equipment_role_correctness": 0.0,
        "executable_test_procedure": 0.0,
        "expected_result_and_decision_closure": 0.0,
        "english_spreadsheet_deliverable": 0.0,
    }
    if parse_error or not rows:
        return {
            "reward": 0.0,
            "rewards": {"strict": 0.0, "lenient": 0.0},
            "reward_formulas": REWARD_FORMULAS,
            "dimension_points": dimensions,
            "detail": {"parse_error": parse_error, "row_count": len(rows), "caps": ["missing_or_unreadable:0"]},
        }

    objective_weights = [2.5, 2.5, 2.0, 2.0, 2.0, 2.0, 2.5, 2.0, 2.5]
    objective_details = []
    from semantic_judge import adjudicate
    hdr_item = next(item for item in GROUND["items"] if item["id"] == "HDR-007")
    hdr_indices = related_rows(rows, hdr_item)
    semantic_result = adjudicate(json.dumps({
        "hdr10_pro_comparison": {
            field: combined_field(rows, hdr_indices, field) if hdr_indices else ""
            for field in ("preconditions", "steps", "expected")
        },
        "complete_candidate": rows,
    }, ensure_ascii=False), (HERE / "semantic_source.json").read_text())
    pre_weighted = 0.0
    step_weighted = 0.0
    expected_weighted = 0.0
    present_weight = 0.0
    coherent_weight = 0.0
    matched_row_indices: set[int] = set()
    for item, weight in zip(GROUND["items"], objective_weights):
        indices = related_rows(rows, item)
        matched_row_indices.update(indices)
        title_text = " ".join(combined_field(rows, indices, field) for field in ("title", "steps", "expected"))
        title_ratio = concept_coverage(title_text, RELATION_COMPONENTS[item["id"]]) if indices else 0.0
        pre_text = combined_field(rows, indices, "preconditions") if indices else ""
        step_text = combined_field(rows, indices, "steps") if indices else ""
        expected_text = combined_field(rows, indices, "expected") if indices else ""
        specific_pre = concept_coverage(pre_text, item["preconditions"]) if indices else 0.0
        specific_steps = concept_coverage(step_text, item["steps"]) if indices else 0.0
        specific_expected = concept_coverage(expected_text, item["expected"]) if indices else 0.0
        if item["id"]=="HDR-007" and indices:
            specific_pre=semantic_result["items"]["preconditions"]["fraction"]
            specific_steps=semantic_result["items"]["steps"]["fraction"]
            specific_expected=semantic_result["items"]["expected"]["fraction"]
        pre_ratio = evidence_bound_quality(
            specific_pre, operational_precondition_quality(pre_text), title_ratio
        )
        step_ratio = evidence_bound_quality(
            specific_steps, operational_step_quality(step_text), title_ratio
        )
        expected_ratio = evidence_bound_quality(
            specific_expected, operational_expected_quality(expected_text), title_ratio
        )
        dimensions["required_hdr_objective_coverage"] += weight * title_ratio
        pre_weighted += weight * pre_ratio
        step_weighted += weight * step_ratio
        expected_weighted += weight * expected_ratio
        if indices:
            present_weight += weight
            coherent_weight += weight * min(step_ratio, expected_ratio)
        objective_details.append({
            "gold_id": item["id"],
            "submitted_rows": [index + 1 for index in indices],
            "objective": round(title_ratio, 4),
            "preconditions": round(pre_ratio, 4),
            "steps": round(step_ratio, 4),
            "expected": round(expected_ratio, 4),
        })

    acceptance = acceptance_checks(rows)
    acceptance_hits = sum(bool(item["hit"]) for item in acceptance)
    dimensions["project_acceptance_relationships"] = 4.0 * acceptance_hits

    all_text = " ".join(" ".join(row.values()) for row in rows).lower()
    device_modes = all(term in all_text for term in ("dolby vision", "hlg", "hdr10 pro"))
    _, deduction_preview = task_deductions(rows)
    role_fraction = (semantic_result["items"]["equipment_roles"]["fraction"]
                     if semantic_result else 0.0)
    unsupported_native = any(item["category"] == "unsupported_native_format" for item in deduction_preview)
    evidence_points = 0.0
    evidence_points += 1.25 if device_modes and not unsupported_native else (0.625 if device_modes else 0.0)
    evidence_points += 1.25 if not unsupported_native else 0.0
    evidence_points += 1.5 * role_fraction
    evidence_points += 1.0 * role_fraction if not unsupported_native else 0.0
    dimensions["evidence_and_equipment_role_correctness"] = 3.0 * evidence_points

    total_weight = sum(objective_weights)
    dimensions["executable_test_procedure"] = 35.0 * (
        0.20 * pre_weighted / total_weight
        + 0.50 * step_weighted / total_weight
        + 0.15 * min(1.0, present_weight / total_weight)
        + 0.15 * coherent_weight / total_weight
    )
    dimensions["expected_result_and_decision_closure"] = 8.0 * expected_weighted / total_weight

    required_found = sum(field in headers for field in ("test_id", "module", "title", "preconditions", "steps", "expected"))
    english_cells = " ".join(value for row in rows for value in row.values())
    ascii_letters = len(re.findall(r"[A-Za-z]", english_cells))
    cjk = len(re.findall(r"[\u3400-\u9fff]", english_cells))
    dimensions["english_spreadsheet_deliverable"] = (
        (0.8 if kind == "xlsx" else 0.2)
        + 0.8 * required_found / 6
        + (0.4 if ascii_letters > 0 and ascii_letters >= 4 * cjk else 0.0)
    )

    coverage_ratio = dimensions["required_hdr_objective_coverage"] / 10.0
    supporting_points = sum(dimensions[key] for key in (
        "project_acceptance_relationships",
        "evidence_and_equipment_role_correctness",
        "executable_test_procedure",
        "expected_result_and_decision_closure",
    ))
    matched_rows = len(matched_row_indices)
    positive_points = sum(dimensions.values())
    deduction_points, deductions = task_deductions(rows)
    wrong_thresholds=[check for check in acceptance if check["wrong_threshold_rows"]]
    threshold_penalty=min(30.,10.*len(wrong_thresholds))
    if threshold_penalty:
        deductions.append({"category":"incorrect_numeric_acceptance","points":threshold_penalty,"evidence":[{"name":x["name"],"rows":x["wrong_threshold_rows"]} for x in wrong_thresholds]})
        deduction_points+=threshold_penalty
    raw_points = positive_points - deduction_points
    score = max(0.0, min(1.0, raw_points / 100))
    caps = []
    overall_step_ratio = step_weighted / total_weight
    overall_expected_ratio = expected_weighted / total_weight
    score = round(score, 6)
    matched_objectives = sum(bool(item["submitted_rows"]) for item in objective_details)
    # The two overall ratios above are weighted by gold objective, so they rise with
    # coverage and fall when an objective is missed entirely. Asking them again here
    # would make this lens a second reading of the strict coverage score. What a
    # delivered list has to answer instead is whether its own entries stand up: a
    # row is well formed when its steps carry the operational verbs and its expected
    # result states something a reader can check. Padding a list with vague entries
    # lowers this share; leaving an objective uncovered does not.
    well_formed_rows = sum(
        1 for row in rows
        if operational_step_quality(row["steps"]) >= WELL_FORMED_STEP_QUALITY
        and operational_expected_quality(row["expected"]) >= WELL_FORMED_EXPECTED_QUALITY
    )
    well_formed_share = well_formed_rows / len(rows) if rows else 0.0
    lenient = 1.0 if (
        kind == "xlsx"
        and required_found == 6
        and matched_objectives == len(GROUND["items"])
        and acceptance_hits == 5
        and not wrong_thresholds
        and role_fraction >= 1.0
        and not unsupported_native
        and overall_step_ratio >= 0.75
        and overall_expected_ratio >= 0.75
        and well_formed_share >= 0.75
    ) else 0.0
    return {
        "reward": score,
        "rewards": {"strict": score, "lenient": lenient},
        "reward_formulas": REWARD_FORMULAS,
        "dimension_points": {key: round(value, 4) for key, value in dimensions.items()},
        "detail": {
            "format": kind,
            "headers_found": headers,
            "row_count": len(rows),
            "matched_gold_items": matched_objectives,
            "unmatched_rows": len(rows) - len(matched_row_indices),
            "precondition_ratio": round(pre_weighted / total_weight, 6),
            "step_ratio": round(overall_step_ratio, 6),
            "expected_ratio": round(overall_expected_ratio, 6),
            "objectives": objective_details,
            "acceptance_checks": acceptance,
            "semantic_HDR007": semantic_result,
            "positive_points": round(positive_points, 4),
            "supporting_coverage_factor": 1.0,
            "deduction_points": round(deduction_points, 4),
            "deductions": deductions,
            "caps": caps,
            "raw_points": round(raw_points, 4),
            "parse_error": parse_error,
        },
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validator.py <submission.xlsx|submission.csv|submission.md>", file=sys.stderr)
        return 2
    try:result=grade(Path(sys.argv[1]))
    except Exception as exc:
        sys.stderr.write("evaluator failed: "+type(exc).__name__+"\n");return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

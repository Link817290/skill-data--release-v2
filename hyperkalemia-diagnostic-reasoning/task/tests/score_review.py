#!/usr/bin/env python3
"""Score Golden-derived factual accuracy and aggregate a paired reasoning review."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

HERE = Path(__file__).resolve().parent
NAMES = {
    "template": "hyperkalemia_reasoning_template.docx",
    "case_001": "CASE-001_reasoning.docx",
    "case_002": "CASE-002_reasoning.docx",
    "case_003": "CASE-003_reasoning.docx",
}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
RUBRIC_PATH = HERE / "review_rubric.json"
CONTRACT_PATH = HERE / "golden_contract.json"
SOURCE_FACTS_PATH = HERE / "source_fact_table.json"
REASONING_PREREQUISITES = {
    "B1": ("M03", "M06"),
    "B2": ("M04", "M05", "M06"),
    "B3": ("M09", "M10", "M11", "M12"),
    "B4": ("M09", "M10", "M11", "M12"),
    "B5": ("M08", "M13", "M14", "M15", "M16"),
    "B6": ("M08", "M13", "M14", "M15", "M16"),
    "B7": ("M08", "M13", "M14", "M15", "M16"),
    "B8": ("M08", "M17", "M18", "M19", "M20"),
    "B9": ("M08", "M17", "M18", "M19", "M20"),
    "B10": ("M01", "M02", "M07", "M08"),
}
LENIENT_REQUIRED_CHECKS = (
    "M01", "M02", "M06", "M07", "M08",
)
LENIENT_CASE_FACT_CHECKS = ("M10", "M14", "M18")
LENIENT_MIN_CASE_FACTS = 2
LENIENT_SEMANTIC_CHECKS = (
    "B3.1", "B3.2", "B3.3",
    "B5.1", "B5.2", "B5.4",
    "B8.1", "B8.2", "B8.3",
)


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = value.translate(str.maketrans({"−": "-", "–": "-", "—": "-", "／": "/"}))
    return re.sub(r"\s+", " ", value).strip()


def inspect_docx(path: Path) -> dict:
    with ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError("CRC failure: " + bad)
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(W + "body")
    blocks: list[str] = []
    rows: list[list[str]] = []
    if body is not None:
        for child in body:
            if child.tag == W + "p":
                text = "".join(node.text or "" for node in child.iter(W + "t")).strip()
                if text:
                    blocks.append(text)
            elif child.tag == W + "tbl":
                for row in child.findall(W + "tr"):
                    cells = [
                        "".join(node.text or "" for node in cell.iter(W + "t")).strip()
                        for cell in row.findall(W + "tc")
                    ]
                    rows.append(cells)
                    blocks.append(" | ".join(cells))
    text = "\n".join(blocks)
    return {
        "sha256": digest(path),
        "status": "READABLE",
        "text_length": len(text),
        "table_count": len(list(root.iter(W + "tbl"))),
        "blocks": blocks,
        "rows": rows,
        "text": text,
    }


def artifact_documents(output: Path) -> dict[str, dict]:
    documents = {}
    for role, name in NAMES.items():
        path = Path(output) / name
        if not path.is_file():
            documents[role] = {
                "sha256": None,
                "status": "MISSING",
                "text_length": 0,
                "table_count": 0,
                "blocks": [],
                "rows": [],
                "text": "",
            }
            continue
        try:
            documents[role] = inspect_docx(path)
        except (BadZipFile, KeyError, ValueError, ET.ParseError) as exc:
            documents[role] = {
                "sha256": digest(path),
                "status": "UNREADABLE",
                "text_length": 0,
                "table_count": 0,
                "blocks": [],
                "rows": [],
                "text": "",
                "issue": str(exc),
            }
    return documents


def public_states(documents: dict[str, dict]) -> dict[str, dict]:
    return {
        role: {key: value for key, value in record.items() if key not in {"blocks", "rows", "text"}}
        for role, record in documents.items()
    }


def artifact_state(output: Path) -> dict[str, dict]:
    return public_states(artifact_documents(output))


def alias_present(text: str, alias: str) -> bool:
    haystack = normalize(text)
    needle = normalize(alias)
    if re.fullmatch(r"[a-z0-9]+", needle):
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    return needle in haystack


def groups_present(text: str, groups: list[list[str]]) -> tuple[bool, list[str]]:
    missing = ["/".join(group) for group in groups if not any(alias_present(text, alias) for alias in group)]
    return not missing, missing


def numeric_values(text: str) -> set[Decimal]:
    values = set()
    normalized = normalize(text)
    normalized = re.sub(r"(?<=\d)\s*-+\s*(?=\d)", " ", normalized)
    for token in re.findall(r"(?<![a-z0-9])[-+]?\d+(?:\.\d+)?", normalized):
        try:
            values.add(Decimal(token))
        except InvalidOperation:
            pass
    return values


def numbers_present(text: str, expected: list[str]) -> tuple[bool, list[str]]:
    observed = numeric_values(text)
    missing = [value for value in expected if Decimal(value) not in observed]
    return not missing, missing


def digit_sequence_present(text: str, sequence: str) -> bool:
    return re.sub(r"\D", "", sequence) in re.sub(r"\D", "", normalize(text))


def cooccurs(blocks: list[str], left: list[str], right: list[str]) -> bool:
    return any(
        any(alias_present(block, alias) for alias in left)
        and any(alias_present(block, alias) for alias in right)
        for block in blocks
    )


def multi_cell_row_count(rows: list[list[str]]) -> int:
    return sum(sum(bool(cell.strip()) for cell in row) >= 2 for row in rows)


def linked_anchor_row_count(rows: list[list[str]], anchors: list[dict]) -> int:
    matched_rows = set()
    for index, row in enumerate(rows):
        if sum(bool(cell.strip()) for cell in row) < 3:
            continue
        text = " | ".join(row)
        values = numeric_values(text)
        if any(
            Decimal(anchor["value"]) in values
            and any(alias_present(text, alias) for alias in anchor["aliases"])
            for anchor in anchors
        ):
            matched_rows.add(index)
    return len(matched_rows)


def associated_values(rows: list[list[str]], aliases: list[list[str]], expected: list[str]) -> tuple[bool, list[str]]:
    """Bind every expected number to its analyte row instead of the whole file."""
    missing = []
    for index, value in enumerate(expected):
        group = aliases[index] if index < len(aliases) else []
        wanted = Decimal(value)
        if not any(wanted in numeric_values(" | ".join(row))
                   and any(alias_present(" | ".join(row), alias) for alias in group)
                   for row in rows):
            missing.append(value)
    return not missing, missing


def associated_observations(
    rows: list[list[str]],
    aliases: list[list[str]],
    observations: list[dict],
    *,
    bind_range: bool = False,
    bind_time: bool = False,
) -> tuple[bool, list[str]]:
    """Bind source facts to one row instead of accepting a document-wide token set."""
    missing = []
    for observation in observations:
        group = aliases[observation["analyte"]]
        result = Decimal(observation["result"])
        ranges = {Decimal(value) for value in observation["range"]}
        expected_time = observation["time"]
        unit = observation.get("unit")
        found = False
        for row in rows:
            row_text = " | ".join(row)
            if not any(alias_present(row_text, alias) for alias in group):
                continue
            values = numeric_values(row_text)
            if result not in values:
                continue
            if bind_range and not ranges.issubset(values):
                continue
            if bind_range and unit and not alias_present(row_text, unit):
                continue
            if bind_time:
                observed_digits = re.sub(r"\D", "", normalize(row_text))
                expected_digits = re.sub(r"\D", "", expected_time)
                variants = {expected_digits}
                if len(expected_digits) >= 12:
                    variants.add(expected_digits[:8] + str(int(expected_digits[8:10])) + expected_digits[10:12])
                if not any(value in observed_digits for value in variants):
                    continue
            found = True
            break
        if not found:
            label = "/".join(group) + "=" + observation["result"]
            if bind_time:
                label += "@" + expected_time
            if bind_range:
                label += " range=" + "..".join(observation["range"])
            missing.append(label)
    return not missing, missing


def evaluate_factual_accuracy(output: Path, contract_path: Path = CONTRACT_PATH) -> dict:
    contract = load_json(contract_path)
    source_facts = load_json(SOURCE_FACTS_PATH)
    documents = artifact_documents(output)
    states = public_states(documents)
    text = {role: record["text"] for role, record in documents.items()}
    blocks = {role: record["blocks"] for role, record in documents.items()}
    groups = contract["term_groups"]
    expected_numbers = contract["numeric_results"]
    anti_gaming = contract["anti_gaming"]
    check_specs = {check["id"]: check for check in contract["checks"]}
    decisions: dict[str, tuple[bool, str]] = {}

    readable = [role for role, state in states.items() if state["status"] == "READABLE"]
    decisions["M01"] = (len(readable) == 4, "Readable roles: " + ", ".join(readable))
    multi_cell_rows = {
        role: multi_cell_row_count(record["rows"])
        for role, record in documents.items()
    }
    editable = [
        role for role, state in states.items()
        if (
            state["status"] == "READABLE"
            and state["text_length"] >= 100
            # The brief requires editable, linked tables and named sections,
            # but does not prescribe a minimum of three separate tables.
            and multi_cell_rows[role] >= anti_gaming["minimum_multi_cell_rows"][role]
        )
    ]
    decisions["M02"] = (
        len(editable) == 4,
        "Roles with readable, substantive multi-cell Word table structure: "
        + ", ".join(editable)
        + "; row counts="
        + repr(multi_cell_rows),
    )

    for check_id, group_name in (("M03", "evidence_fields"), ("M04", "assessment_fields"), ("M05", "reasoning_fields")):
        met, missing = groups_present(text["template"], groups[group_name])
        decisions[check_id] = (met, "Missing Golden-derived field groups: " + (", ".join(missing) if missing else "none"))

    neutral_markers = ["case-001", "case-002", "case-003", "2025-11-15", "2023-02-16", "2023-02-25", "6.69", "6.84", "6.71"]
    found_markers = [marker for marker in neutral_markers if alias_present(text["template"], marker)]
    decisions["M06"] = (not found_markers, "Case-specific markers in blank template: " + (", ".join(found_markers) if found_markers else "none"))

    template_tables = states["template"]["table_count"]
    structured_roles = []
    anchor_rows = {}
    for role in ("case_001", "case_002", "case_003"):
        sections_ok, _ = groups_present(text[role], groups["case_sections"])
        anchor_rows[role] = linked_anchor_row_count(
            documents[role]["rows"],
            anti_gaming["row_association_anchors"][role],
        )
        if (
            sections_ok
            and anchor_rows[role] >= anti_gaming["minimum_distinct_anchor_rows"][role]
        ):
            structured_roles.append(role)
    decisions["M07"] = (
        len(structured_roles) == 3,
        "Case roles preserving template structure with row-linked analyte/value evidence: "
        + ", ".join(structured_roles)
        + "; anchor rows="
        + repr(anchor_rows),
    )

    ownership = (
        not any(Decimal(value) in numeric_values(text["case_001"]) for value in ("6.69", "6.84", "6.71"))
        and Decimal("6.69") in numeric_values(text["case_002"])
        and not any(Decimal(value) in numeric_values(text["case_002"]) for value in ("6.84", "6.71", "2.90"))
        and all(Decimal(value) in numeric_values(text["case_003"]) for value in ("2.90", "6.84", "6.71"))
        and Decimal("6.69") not in numeric_values(text["case_003"])
    )
    decisions["M08"] = (ownership, "Checked distinctive Golden numeric anchors for cross-case placement")

    met, missing = groups_present(text["case_001"], groups["case_001_analytes"])
    decisions["M09"] = (met, "Missing CASE-001 Golden analyte labels: " + (", ".join(missing) if missing else "none"))
    met, missing = associated_observations(documents["case_001"]["rows"], groups["case_001_analytes"], source_facts["case_001"])
    decisions["M10"] = (met, "Missing CASE-001 analyte-associated result values: " + (", ".join(missing) if missing else "none"))
    units_ok, units_missing = groups_present(text["case_001"], groups["units"])
    reference_ok, _ = groups_present(text["case_001"], groups["reference"])
    c1_range_ok, c1_range_missing = associated_observations(documents["case_001"]["rows"], groups["case_001_analytes"], source_facts["case_001"], bind_range=True)
    decisions["M11"] = (units_ok and reference_ok and c1_range_ok, "Missing analyte-bound units/ranges: " + ", ".join(units_missing + c1_range_missing))
    c1_time, c1_time_missing = associated_observations(documents["case_001"]["rows"], groups["case_001_analytes"], source_facts["case_001"], bind_time=True)
    c1_missing_k = cooccurs(blocks["case_001"], ["potassium", "blood potassium", "血钾", "钾"], ["not provided", "not reported", "missing", "unavailable", "未提供", "未报告", "缺失"])
    decisions["M12"] = (c1_time and c1_missing_k, f"Observation-bound date/time present={c1_time}; missing={c1_time_missing}; potassium-not-provided co-occurrence={c1_missing_k}")

    met, missing = groups_present(text["case_002"], groups["case_002_analytes"])
    decisions["M13"] = (met, "Missing CASE-002 Golden labels: " + (", ".join(missing) if missing else "none"))
    met, missing = associated_observations(documents["case_002"]["rows"], groups["case_002_analytes"][:-1], source_facts["case_002"])
    decisions["M14"] = (met, "Missing CASE-002 analyte-associated result values: " + (", ".join(missing) if missing else "none"))
    c2_units = alias_present(text["case_002"], "mmol/l")
    c2_reference, _ = groups_present(text["case_002"], groups["reference"])
    c2_range_ok, c2_range_missing = associated_observations(documents["case_002"]["rows"], groups["case_002_analytes"][:-1], source_facts["case_002"], bind_range=True)
    decisions["M15"] = (c2_units and c2_reference and c2_range_ok, "Missing analyte-bound CASE-002 ranges: " + (", ".join(c2_range_missing) if c2_range_missing else "none"))
    c2_time, c2_time_missing = associated_observations(documents["case_002"]["rows"], groups["case_002_analytes"][:-1], source_facts["case_002"], bind_time=True)
    c2_diagnosis = cooccurs(blocks["case_002"], ["bradycardia", "心动过缓"], ["diagnosis", "recorded", "report", "诊断", "记录", "报告"])
    conflicting_diagnosis = alias_present(text["case_002"], "tachycardia") or alias_present(text["case_002"], "心动过速")
    decisions["M16"] = (c2_time and c2_diagnosis and not conflicting_diagnosis, f"Observation-bound report time={c2_time}; missing={c2_time_missing}; bradycardia recorded={c2_diagnosis}; conflicting diagnosis={conflicting_diagnosis}")

    labels_ok, labels_missing = groups_present(text["case_003"], groups["case_003_analytes"])
    occurrence_ok = all(sum(normalize(alias) in normalize(text["case_003"]) for alias in group) >= 1 for group in groups["case_003_analytes"])
    decisions["M17"] = (labels_ok and occurrence_ok, "Missing CASE-003 Golden analyte labels: " + (", ".join(labels_missing) if labels_missing else "none"))
    met, missing = associated_observations(documents["case_003"]["rows"], groups["case_003_analytes"], source_facts["case_003"], bind_time=True)
    decisions["M18"] = (met, "Missing CASE-003 timepoint-associated result values: " + (", ".join(missing) if missing else "none"))
    c3_units = alias_present(text["case_003"], "mmol/l")
    c3_reference, _ = groups_present(text["case_003"], groups["reference"])
    c3_range_ok, c3_range_missing = associated_observations(documents["case_003"]["rows"], groups["case_003_analytes"], source_facts["case_003"], bind_range=True, bind_time=True)
    decisions["M19"] = (c3_units and c3_reference and c3_range_ok, "Missing timepoint/analyte-bound CASE-003 ranges: " + (", ".join(c3_range_missing) if c3_range_missing else "none"))
    c3_times, c3_time_missing = associated_observations(documents["case_003"]["rows"], groups["case_003_analytes"], source_facts["case_003"], bind_time=True)
    decisions["M20"] = (c3_times, "Missing timepoint-bound observations: " + (", ".join(c3_time_missing) if c3_time_missing else "none"))

    unknown = set(decisions) ^ set(check_specs)
    if unknown:
        raise ValueError("Factual-accuracy check implementation differs from contract: " + repr(sorted(unknown)))
    checks = []
    for spec in contract["checks"]:
        met, evidence = decisions[spec["id"]]
        checks.append({
            "id": spec["id"],
            "weight": spec["weight"],
            "met": int(met),
            "criterion": spec["criterion"],
            "evidence": evidence,
        })
    score = round(sum(check["weight"] * check["met"] for check in checks) / 100, 6)
    return {
        "golden_contract_sha256": digest(contract_path),
        "source_fact_table_sha256": digest(SOURCE_FACTS_PATH),
        "score": score,
        "score_100": score * 100,
        "checks": checks,
    }


def scaffold(output: Path, rubric_path: Path = RUBRIC_PATH) -> dict:
    rubric = load_json(rubric_path)
    states = artifact_state(output)
    return {
        "rubric_sha256": digest(rubric_path),
        "golden_contract_sha256": digest(CONTRACT_PATH),
        "source_fact_table_sha256": digest(SOURCE_FACTS_PATH),
        "reviewer": {"kind": "model", "identity": "", "independence": "", "limitations": []},
        "artifacts": {key: value["sha256"] for key, value in states.items()},
        "items": [
            {
                "id": item["id"],
                "checks": [
                    {"id": check["id"], "met": None, "evidence": [], "reason": ""}
                    for check in item["checks"]
                ],
            }
            for item in rubric["items"]
        ],
        "unscored_observations": [],
    }


def aggregate(output: Path, review: dict | None = None, rubric_path: Path = RUBRIC_PATH) -> dict:
    output = Path(output)
    rubric = load_json(rubric_path)
    states = artifact_state(output)
    factual = evaluate_factual_accuracy(output)
    factual_status = {check["id"]: bool(check["met"]) for check in factual["checks"]}
    case_fact_coverage = sum(factual_status[check_id] for check_id in LENIENT_CASE_FACT_CHECKS)
    must_haves_met = (
        all(factual_status[check_id] for check_id in LENIENT_REQUIRED_CHECKS)
        and case_fact_coverage >= LENIENT_MIN_CASE_FACTS
    )
    lenient = float(must_haves_met)
    result = {
        "status": "PENDING_REASONING_REVIEW",
        "reward": None,
        "rewards": {"strict": None, "lenient": lenient, "factual_accuracy": factual["score"], "reasoning_quality": None},
        "score_100": None,
        "scores_100": {"strict": None, "lenient": lenient * 100, "factual_accuracy": factual["score_100"], "reasoning_quality": None},
        "semantics": "Golden-derived factual accuracy multiplied by a Golden-paired reasoning-quality comparison",
        "reward_formulas": {
            "strict": "factual_accuracy * reasoning_quality",
            "lenient": "binary delivery structure plus analyte/result association in at least two of the three cases",
            "factual_accuracy": "sum(weight * binary_check) / 100",
            "reasoning_quality": "sum(item_weight * passed_checks / item_checks) / 100",
            "reward_alias": "strict",
        },
        "rubric_sha256": digest(rubric_path),
        "golden_contract_sha256": digest(CONTRACT_PATH),
        "source_fact_table_sha256": digest(SOURCE_FACTS_PATH),
        "artifacts": states,
        "factual_accuracy": factual,
        "lenient_required_checks": list(LENIENT_REQUIRED_CHECKS),
        "lenient_case_fact_checks": list(LENIENT_CASE_FACT_CHECKS),
        "lenient_min_case_facts": LENIENT_MIN_CASE_FACTS,
        "lenient_case_fact_coverage": case_fact_coverage,
        "lenient_semantic_checks": list(LENIENT_SEMANTIC_CHECKS),
        "issues": [],
    }
    if review is None:
        return result
    try:
        if review["rubric_sha256"] != result["rubric_sha256"]:
            raise ValueError("Review/rubric hash mismatch")
        if review.get("golden_contract_sha256") != result["golden_contract_sha256"]:
            raise ValueError("Review/Golden-contract hash mismatch")
        if review.get("source_fact_table_sha256") != result["source_fact_table_sha256"]:
            raise ValueError("Review/source-fact-table hash mismatch")
        hashes = {key: value["sha256"] for key, value in states.items()}
        if review["artifacts"] != hashes:
            raise ValueError("Review artifact hashes mismatch")
        who = review["reviewer"]
        if who["kind"] not in {"model", "human", "author_self_check", "synthetic_test"} or not who["identity"].strip():
            raise ValueError("Explicit reviewer kind and identity required")
        expected = {item["id"]: item for item in rubric["items"]}
        supplied = review["items"]
        if len(supplied) != len(expected) or {item["id"] for item in supplied} != set(expected):
            raise ValueError("Missing, unexpected or duplicate reasoning-quality item IDs")
        pending, detail, semantic_status = [], [], {}
        for record in supplied:
            item = expected[record["id"]]
            expected_checks = {check["id"] for check in item["checks"]}
            checks = record["checks"]
            if len(checks) != 4 or {check["id"] for check in checks} != expected_checks:
                raise ValueError("Missing, unexpected or duplicate checks: " + item["id"])
            fulfilled = 0
            for check in checks:
                met = check["met"]
                if met is not None and type(met) is not bool:
                    raise ValueError("Reasoning-quality met must be boolean or null: " + check["id"])
                if met is None:
                    pending.append(check["id"])
                    continue
                if not isinstance(check["evidence"], list) or not check["evidence"] or not all(isinstance(value, str) and value.strip() for value in check["evidence"]):
                    raise ValueError("Reasoning-quality evidence required: " + check["id"])
                if not isinstance(check["reason"], str) or not check["reason"].strip():
                    raise ValueError("Reasoning-quality rationale required: " + check["id"])
                fulfilled += int(met)
                semantic_status[check["id"]] = bool(met)
            missing = [role for role in item["artifacts"] if states[role]["status"] != "READABLE"]
            if missing and fulfilled:
                raise ValueError("Review awards credit despite missing artifact: " + item["id"])
            prerequisites = REASONING_PREREQUISITES[item["id"]]
            prerequisite_misses = [check_id for check_id in prerequisites if not factual_status[check_id]]
            atomic_coverage = fulfilled / len(checks)
            detail.append({
                "id": item["id"],
                "weight": item["weight"],
                "fulfilled": fulfilled,
                "atomic_coverage": atomic_coverage,
                "points": round(item["weight"] * atomic_coverage, 6),
                "artifact_dependencies": item["artifacts"],
                "factual_prerequisites": list(prerequisites),
                "blocked_by": prerequisite_misses,
                "prerequisites_scoring_effect": "diagnostic_only",
            })
        result.update(reviewer=who, reasoning_quality_items=detail, pending_checks=pending, unscored_observations=review.get("unscored_observations", []))
        if pending:
            return result
        reasoning = round(sum(item["points"] for item in detail) / 100, 6)
        strict = round(factual["score"] * reasoning, 6)
        semantic_lenient = all(
            semantic_status.get(check_id, False)
            for check_id in LENIENT_SEMANTIC_CHECKS
        )
        lenient = float(must_haves_met and semantic_lenient)
        result.update(
            status="REVIEWED",
            reward=strict,
            rewards={"strict": strict, "lenient": lenient, "factual_accuracy": factual["score"], "reasoning_quality": reasoning},
            score_100=strict * 100,
            scores_100={"strict": strict * 100, "lenient": lenient * 100, "factual_accuracy": factual["score_100"], "reasoning_quality": reasoning * 100},
            lenient_semantic_evaluation={
                "required_checks": list(LENIENT_SEMANTIC_CHECKS),
                "failed_ids": [
                    check_id for check_id in LENIENT_SEMANTIC_CHECKS
                    if not semantic_status.get(check_id, False)
                ],
            },
        )
    except (KeyError, TypeError, ValueError) as exc:
        result.update(status="REVIEW_RECORD_INVALID", issues=[str(exc)])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--scaffold", action="store_true")
    args = parser.parse_args()
    if args.review and args.review.resolve().is_relative_to(args.output.resolve()):
        result = {"status": "REVIEW_RECORD_INVALID", "reward": None, "issues": ["Review must be evaluator-side"]}
    else:
        try:
            review = load_json(args.review) if args.review else None
            result = scaffold(args.output) if args.scaffold else aggregate(args.output, review)
        except (OSError, ValueError) as exc:
            result = {"status": "EVALUATION_ERROR", "reward": None, "issues": [str(exc)]}
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result.get(key) for key in ["status", "scores_100", "rewards", "reward"]}, ensure_ascii=False))

#!/usr/bin/env python3
"""Condition-blind semantic scorer for the HACCP authorization audit JSON."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any
from semantic_judge import adjudicate


HERE = Path(__file__).resolve().parent
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
EXPECTED_DIGESTS = json.loads((HERE / "source_integrity.json").read_text(encoding="utf-8"))

WEIGHTS = {
    "decision_boundary": 0.08,
    "applicability_hazard_scope": 0.14,
    "botulinum_control_chain": 0.17,
    "process_validation": 0.09,
    "cooling_control": 0.11,
    "monitoring_limit_alignment": 0.08,
    "corrective_action_closure": 0.08,
    "verification_calibration": 0.07,
    "distribution_and_storage": 0.06,
    "postprocess_boundary": 0.04,
    "evidence_binding": 0.08,
}
MIN_RECOGNIZED_ANCHORS = 8
MIN_EVIDENCE_BOUND_ANCHORS = 7



# Retained only as a diagnostic reference for the original audit. These patterns
# are deliberately not used for scoring; all substantive anchor decisions go
# through the source-bound Responses judge below.
PATTERNS = {
    "release_boundary": (
        (r"\bhold\b.{0,40}\bauthor", r"not ready.{0,40}author", r"withhold.{0,30}approv", r"do not author", r"authorization is not recommended", r"not.{0,30}(controlled|adequate).{0,30}author"),
        (r"illustrative.{0,20}example", r"blank.{0,30}(signature|revision)", r"controlled.{0,20}plan"),
        (r"does not prove.{0,90}(operat|implement|plan exists|signed|controlled)", r"not establish.{0,70}(operat|implement)", r"actual.{0,30}(operat|implement).{0,50}not determin", r"not.determinable.{0,60}(version|outside|implementation)"),
    ),
    "scope_hazard_analysis": (
        (r"species",),
        (r"hazard analysis", r"hazard-analysis"),
        (r"(missing|absent|not supplied|unresolved|not determin).{0,100}(species|source|scope)", r"(species|source|scope).{0,100}(missing|absent|not supplied|unresolved|not determin)"),
        (r"(supply|provide|document|obtain|add|identify).{0,100}(product.group|species|hazard analysis)",),
    ),
    "scombrotoxin_applicability": (
        (r"scombrotoxin", r"histamine"),
        (r"species", r"histamine-forming"),
        (r"pre.receipt", r"pre.freez", r"before freezing", r"harvest.{0,30}history", r"receiv.{0,50}time.temperature"),
        (r"(conditional|unresolved|not determin|cannot).{0,100}(applic|hazard|conclusion)", r"(applic|hazard).{0,100}(conditional|unresolved|not determin|cannot)"),
    ),
    "botulinum_hazard_identity": (
        (r"clostridium.{0,12}botulinum", r"c\.?\s*botulinum", r"botulinal toxin"),
        (r"vacuum", r"reduced.oxygen"),
        (r"type e", r"nonproteolytic", r"shelf life.{0,80}normal.{0,30}moderate abuse", r"normal.{0,30}moderate abuse.{0,80}shelf life"),
        (r"(salt|brin).{0,100}(dry|refrigerat|heat)", r"(dry|refrigerat|heat).{0,100}(salt|brin)"),
        (r"generic.{0,30}pathogen", r"does not connect", r"not map"),
    ),
    "brining_drying_endpoint": (
        (r"brin",),
        (r"process schedule", r"scientific.{0,25}(study|process)", r"process.establish"),
        (r"water.phase.salt", r"\bwps\b", r"finished.product.{0,40}(salt|inhibitory)", r"inhibitory endpoint"),
        (r"missing", r"absent", r"not supplied", r"does not supply", r"no demonstrated", r"does not show", r"do not demonstrate"),
        (r"species|thickness|load|drying condition|critical factor",),
    ),
    "process_schedule_support": (
        (r"critical limit", r"brining.{0,50}(smoking|cooking)"),
        (r"process schedule", r"scheduled process"),
        (r"absent", r"missing", r"not supplied"),
        (r"scientific.{0,25}(study|support)", r"validat", r"process.establish"),
    ),
    "periodic_product_verification": (
        (r"annual",),
        (r"water.phase.salt", r"\bwps\b", r"finished.product.{0,30}(check|test|analy)"),
        (r"cannot.{0,30}substitute", r"does not.{0,30}(establish|replace)", r"do not.{0,40}demonstrate", r"not a substitute"),
        (r"three months", r"3 months", r"quarter", r"direct.{0,20}monitor", r"lot.level monitoring"),
        (r"sampling|frequency|analytical method|failing.result|deviation response",),
    ),
    "cooling_measurement": (
        (r"cool",),
        (r"ambient", r"room temperature", r"cooler temperature"),
        (r"internal.{0,30}product", r"warmest.{0,30}product", r"product.{0,30}cooling (curve|profile)"),
        (r"cooling.rate study", r"validat.{0,30}(surrogate|process factor|cool)", r"study.{0,50}(process factor|cooler)"),
        (r"not.{0,60}(show|demonstrate|measure|specify|state)", r"does not.{0,60}(show|demonstrate|measure|specify|state)", r"neither.{0,50}(monitor|study)", r"measurement.{0,25}mismatch"),
    ),
    "cooking_monitoring": (
        (r"cook", r"heating"),
        (r"center temperature", r"internal temperature"),
        (r"chart recorder", r"recording device"),
        (r"sensor.{0,30}(place|location)", r"coldest.{0,30}(unit|location)", r"worst.case.{0,30}(unit|product)", r"how.{0,30}(both|parameter).{0,30}measure"),
        (r"not show", r"does not show", r"does not state", r"lacks", r"absent.{0,30}(schedule|support)", r"unclear", r"not specified", r"unresolved"),
    ),
    "corrective_action_closure": (
        (r"corrective", r"hold.{0,30}evaluat", r"reprocess|relabel"),
        (r"affected.{0,20}(lot|product)", r"product.{0,40}disposition", r"safe.{0,20}dispos"),
        (r"cause.{0,40}(correct|control)", r"restore.{0,30}(process|control)", r"regain.{0,30}control"),
        (r"evaluation.{0,20}basis", r"qualified.{0,20}evaluat", r"lookback"),
    ),
    "instrument_verification": (
        (r"(daily|record).{0,30}review", r"review.{0,30}(record|monitor)"),
        (r"useful", r"retain", r"credit", r"positive", r"contemplated", r"lists.{0,50}(daily|record review|recorder check)"),
        (r"accuracy", r"calibrat"),
        (r"reference.{0,20}(standard|device)", r"known accurate"),
        (r"lookback", r"last known accurate", r"affected.{0,30}(lot|record)"),
    ),
    "storage_distribution": (
        (r"storage",),
        (r"continuous.{0,30}(chart|record)", r"chart.{0,30}continuous"),
        (r"conservative", r"credit", r"retain"),
        (r"label.{0,50}(not|is not|does not|cannot)", r"label.{0,50}not evidence", r"label check.{0,70}(transport|distribution)"),
        (r"transport", r"distribution", r"shipping"),
    ),
    "postprocess_boundary": (
        (r"post.process", r"post-cook", r"recontamin"),
        (r"sanitation",),
        (r"(not|cannot).{0,60}(declar|requir).{0,35}ccp", r"ccp.{0,50}(not automatic|not determin)", r"additional ccp.{0,35}(not required|not established)", r"absence.{0,50}does not.{0,50}(prove|establish).{0,40}(inadequate|violation)"),
        (r"hazard analysis", r"environmental monitoring", r"implementation record"),
        (r"not determin", r"absent", r"outside.{0,20}(packet|record)"),
    ),
}


# Alternative experts often cite the controlling regulation, a chapter overview,
# or a worked control-strategy page instead of the particular page used by the
# canonical audit. These are all valid source locations for the same relations.
EVIDENCE_PAGES = {
    "release_boundary": {17, 18, 19, 28, 536},
    "scope_hazard_analysis": {18, 19, 22, 23, 24, 25, 81, 82, 83, 84, 85, 86, 311, 535, 536, 541},
    "scombrotoxin_applicability": set(range(132, 141)) | {18, 19},
    "botulinum_hazard_identity": set(range(296, 323)) | {18, 19, 86, 541},
    "brining_drying_endpoint": set(range(302, 315)) | {18, 19},
    "process_schedule_support": set(range(311, 324)) | {18, 19, 29, 536},
    "periodic_product_verification": {18, 19, 313, 314, 315, 316, 317, 338},
    "cooling_measurement": {18, 19, 281, 282, 283},
    "cooking_monitoring": set(range(307, 323)) | {18, 19, 29},
    "corrective_action_closure": set(range(281, 284)) | set(range(312, 319)) | {18, 19, 30},
    "instrument_verification": set(range(281, 284)) | set(range(313, 318)) | {18, 19, 28},
    "storage_distribution": set(range(296, 323)) | {18, 19, 266, 541},
    "postprocess_boundary": set(range(396, 405)) | {18, 19, 371},
}


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip().lower()


def flatten(value: Any) -> str:
    parts: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                parts.append(str(key))
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif item is not None:
            parts.append(str(item))

    visit(value)
    return normalized(" ".join(parts))


def is_aggregate(record: dict) -> bool:
    # A finding owns its evidence/action lists. Only collections of independent
    # findings are aggregate containers, irrespective of evidence text length.
    own = {str(k).lower() for k in record}
    if own & {"finding_id", "conclusion", "finding", "haccp_element", "corrective_recommendation"}: return False
    return any(isinstance(v,list) and any(isinstance(c,dict) and set(c) & {"finding_id", "conclusion", "finding", "haccp_element"} for c in v) for v in record.values())


def candidate_records(value: Any) -> list[dict]:
    found: list[dict] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            text = flatten(item)
            # Finding length is not a contract requirement.  Keep only the
            # structural ownership check here so a detailed, long finding is
            # still eligible for semantic and evidence scoring.
            if len(text) >= 1 and not is_aggregate(item):
                found.append(item)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return found


def evidence_match(anchor: str, record: dict | None) -> float:
    if record is None:
        return 0.0
    expected = GROUND["accepted_evidence"][anchor]
    accepted_pages = set(expected["pdf_pages"]) | EVIDENCE_PAGES.get(anchor, set())

    # Bind the document and locator from the same citation object.  Looking at
    # a flattened finding lets an unrelated page number (or a page from a
    # different document) satisfy the evidence check.
    citations = []
    def visit(node):
        if isinstance(node, dict):
            keys = {str(k).lower(): v for k, v in node.items()}
            doc = next((str(keys[k]) for k in ("document", "file", "source", "document_name") if k in keys and keys[k]), None)
            page = next((keys[k] for k in ("pdf_page", "page", "page_number", "locator") if k in keys and keys[k] is not None), None)
            if doc is not None and page is not None:
                citations.append((doc, page))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
        elif isinstance(node, str):
            # A citation may be a compact string; the task does not require a
            # JSON citation object. Keep document and page bound to this same
            # scalar so an unrelated number elsewhere cannot satisfy it.
            for name in expected["documents"]:
                if normalized(name) in normalized(node) or normalized(name).replace("_", " ").replace(".pdf", "") in normalized(node):
                    pages = re.findall(r"(?:pdf[ _-]*page|page|p\.?)[^0-9]{0,8}(\d{1,3})", node, re.I)
                    for page in pages:
                        citations.append((name, page))
    visit(record)
    for document, page_value in citations:
        doc_norm = normalized(document)
        if not any(normalized(name) in doc_norm or normalized(name).replace("_", " ").replace(".pdf", "") in doc_norm for name in expected["documents"]):
            continue
        pages = [int(x) for x in re.findall(r"\d+", str(page_value))]
        if any(page in accepted_pages for page in pages):
            if "review_dossier.pdf" in doc_norm and any(page > 36 for page in pages):
                continue
            return 1.0
    return 0.0


def source_roots(target: Path) -> list[Path]:
    roots = [target if target.is_dir() else target.parent]
    roots.append(HERE.parent / "environment" / "workspace")
    unique = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def source_integrity(target: Path) -> tuple[bool, dict]:
    details = {}
    for filename, expected in EXPECTED_DIGESTS.items():
        source = next((root / filename for root in source_roots(target) if (root / filename).is_file()), None)
        actual = hashlib.sha256(source.read_bytes()).hexdigest() if source else None
        details[filename] = {"present": source is not None, "digest_matches": actual == expected}
    return all(item["digest_matches"] for item in details.values()), details


def load_artifact(target: Path) -> tuple[Any | None, str | None]:
    try:
        if target.is_dir():
            preferred = target / "haccp_audit.json"
            choices = [preferred] if preferred.is_file() else sorted(target.glob("*.json"))
            if not choices:
                return None, "no JSON deliverable found"
            target = choices[0]
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, (dict, list)):
            return None, "JSON root is not an object or array"
        return data, None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"unreadable JSON: {exc}"


def list_records(value: Any) -> list[list[dict]]:
    lists: list[list[dict]] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            records = [child for child in item if isinstance(child, dict)]
            if records:
                lists.append(records)
            for child in item:
                visit(child)

    visit(value)
    return lists


def has_locator(text: str) -> bool:
    has_document = bool(re.search(r"\b(pdf|dossier|control.reference)\b", text))
    has_page = bool(re.search(r"(?:pdf[ _-]*page|page|p\.?)[^0-9]{0,8}[0-9]{1,3}", text))
    return has_document and has_page


def score_lenient(
    artifact: Any | None,
    anchor_scores: dict[str, float],
    evidence_scores: dict[str, float],
    authorization_decision_correct: bool = False,
) -> tuple[float, dict]:
    if artifact is None:
        gates = {
            "json_readable": False,
            "decision_present": False,
            "findings_present": False,
            "actions_present": False,
            "evidence_boundary_present": False,
        }
        return 0.0, {
            **gates,
            "professional_anchor_coverage": False,
            "evidence_binding_coverage": False,
            "recognized_anchors": 0,
            "evidence_bound_anchors": 0,
            "recognized_anchor_floor": MIN_RECOGNIZED_ANCHORS,
            "evidence_bound_anchor_floor": MIN_EVIDENCE_BOUND_ANCHORS,
        }

    usable_lists = []
    for records in list_records(artifact):
        usable = []
        for record in records:
            text = flatten(record)
            # Shape is checked mechanically; substantive topic, action and
            # evidence-boundary meaning are judged by the source-bound LLM.
            # There is no arbitrary finding-length contract.
            if text and has_locator(text):
                usable.append(text)
        if len(usable) >= 2:
            usable_lists.append(usable)

    findings = max(usable_lists, key=len) if usable_lists else []
    gates = {
        "json_readable": True,
        # The adopted disposition is semantic, so synonyms such as defer,
        # suspend, or return for controlled revision are handled by the judge.
        "decision_present": authorization_decision_correct,
        "findings_present": len(findings) >= 2,
        # Each positive anchor requires an adopted conclusion, an evidence
        # boundary, and a concrete corrective relation. Reuse that validated
        # semantic result instead of a fixed vocabulary gate.
        "actions_present": sum(bool(value) for value in anchor_scores.values()) >= 2,
        "evidence_boundary_present": any(bool(value) for value in anchor_scores.values()),
    }
    recognized = sum(bool(value) for value in anchor_scores.values())
    evidence_bound = sum(bool(value) for value in evidence_scores.values())
    gates.update({
        "professional_anchor_coverage": recognized >= MIN_RECOGNIZED_ANCHORS,
        "evidence_binding_coverage": evidence_bound >= MIN_EVIDENCE_BOUND_ANCHORS,
    })
    detail = {
        **gates,
        "recognized_anchors": recognized,
        "evidence_bound_anchors": evidence_bound,
        "recognized_anchor_floor": MIN_RECOGNIZED_ANCHORS,
        "evidence_bound_anchor_floor": MIN_EVIDENCE_BOUND_ANCHORS,
        "independence_note": "quality-floor checks reuse strict anchor evidence; lenient is not independent of strict",
    }
    return (1.0 if all(gates.values()) else 0.0), detail


def resolve_source_aliases(artifact):
    mappings = {}
    def definitions(node):
        if isinstance(node,dict):
            doc = next((str(v) for v in node.values() if isinstance(v,str) and v in ("review_dossier.pdf", "applicable_regulatory_authority.pdf")),None)
            if doc:
                for key in ("id", "source_id", "document_id", "alias"):
                    if isinstance(node.get(key),str):mappings[node[key]]=doc
            for k,v in node.items():
                if isinstance(v,str) and v in ("review_dossier.pdf", "applicable_regulatory_authority.pdf"):mappings[k]=v
                definitions(v)
        elif isinstance(node,list):
            for c in node:definitions(c)
    definitions(artifact)
    def expand(node):
        if isinstance(node,dict):return {k:expand(v) for k,v in node.items()}
        if isinstance(node,list):return [expand(v) for v in node]
        return mappings.get(node,node) if isinstance(node,str) else node
    return expand(artifact)


def grade(target: Path) -> dict:
    artifact, load_error = load_artifact(target)
    artifact = resolve_source_aliases(artifact) if artifact is not None else None
    records = candidate_records(artifact) if artifact is not None else []
    semantic = adjudicate(json.dumps(artifact,ensure_ascii=False,indent=2), json.loads((HERE / "semantic_source.json").read_text())) if artifact is not None else None
    anchor_scores = {}
    anchor_records = {}
    evidence_scores = {}
    for anchor in GROUND["anchor_ids"]:
        verdict = semantic["items"][anchor] if semantic else None
        score = verdict["fraction"] if verdict else 0.0
        quotes = verdict["quotes"] if verdict else []
        index = next((i for i,r in enumerate(records) if any(q.strip() in json.dumps(r,ensure_ascii=False,indent=2) for q in quotes if len(q.strip())>8)), None)
        if score and index is None:
            index = next((i for i,r in enumerate(records) if any(normalized(q.strip().strip(',').strip('"')) in flatten(r) for q in quotes if len(q.strip())>8)), None)
        anchor_scores[anchor] = score
        anchor_records[anchor] = index
        evidence_scores[anchor] = evidence_match(anchor, records[index] if index is not None else None)

    group_scores = {}
    for dimension, anchors in GROUND["dimension_anchors"].items():
        group_scores[dimension] = sum(anchor_scores[anchor] for anchor in anchors) / len(anchors)
    group_scores["evidence_binding"] = sum(evidence_scores.values()) / max(sum(anchor_scores.values()), 1)

    integrity, integrity_detail = source_integrity(target)
    # Correct fragments cannot compensate for an overall authorization decision
    # that reverses the supplied packet's unresolved evidence boundary.
    disposition_ok = bool(semantic and semantic["items"]["AUTHORIZATION_DECISION"]["fraction"] == 1)
    gate = float(integrity and disposition_ok)
    strict = round(gate * sum(WEIGHTS[name] * group_scores[name] for name in WEIGHTS), 6)
    lenient, lenient_detail = score_lenient(artifact, anchor_scores, evidence_scores, disposition_ok)
    lenient_detail["authorization_decision_correct"] = disposition_ok
    lenient = float(bool(lenient) and disposition_ok and integrity)
    group_points = {name: round(WEIGHTS[name] * group_scores[name], 6) for name in WEIGHTS}
    checkpoints = {
        anchor: {
            "recognized": bool(anchor_scores[anchor]),
            "evidence_bound": bool(evidence_scores[anchor]),
            "candidate_record": anchor_records[anchor],
        }
        for anchor in GROUND["anchor_ids"]
    }
    diagnostics = []
    if load_error:
        diagnostics.append(load_error)
    if not integrity:
        diagnostics.append("source_integrity_gate_failed")
    if not disposition_ok:
        diagnostics.append("authorization_decision_gate_failed")

    return {
        "reward": strict,
        "rewards": {"strict": strict, "lenient": lenient},
        "score_type": "haccp_authorization_semantic_audit",
        "reward_formulas": {
            "strict": "source_integrity_gate * authorization_decision_gate * sum(dimension_weight * semantic_hit_rate)",
            "lenient": "authorization_decision_gate * json_readable * decision_present * findings_present * actions_present * evidence_boundary_present * recognized_anchor_count_at_least_8 * evidence_bound_anchor_count_at_least_7",
        },
        "semantic_judge": semantic,
        "checkpoint_count": len(GROUND["anchor_ids"]),
        "gate_factor": gate,
        "gates": {"source_integrity": integrity, "authorization_decision_correct": disposition_ok, "source_files": integrity_detail},
        "group_scores": {name: round(value, 6) for name, value in group_scores.items()},
        "group_points": group_points,
        "group_weights": WEIGHTS,
        "checkpoints": checkpoints,
        "lenient_detail": lenient_detail,
        "diagnostic_errors": diagnostics,
    }


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/haccp_audit.json")
    print(json.dumps(grade(target), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

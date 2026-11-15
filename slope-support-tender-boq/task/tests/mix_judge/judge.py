"""Source-bound semantic review for professional BOQ equivalence and controls."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
sys.path.insert(0, str(TESTS))
import validator  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def responses_endpoint(base: str) -> str:
    base = base.strip().rstrip("/")
    if base.endswith("/responses"):
        return base
    if base.endswith("/v1"):
        return base + "/responses"
    return base + "/v1/responses"


def compact(value: object) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def build_evidence(workbook: Path) -> tuple[dict, dict]:
    truth = json.loads((TESTS / "ground_truth.json").read_text(encoding="utf-8"))
    provenance = json.loads((TESTS / "reference/quantity_provenance.json").read_text(encoding="utf-8"))
    tables = validator.workbook_tables(workbook)
    selected = validator.select_boq_tables(tables, truth["sections"])
    candidate_units = [{"id": "C-WORKBOOK", "text": f"Workbook {workbook.name}; selected BOQ sheets: {', '.join(table['name'] for table in selected) or 'none'}"}]
    item_number = 0
    for table in selected:
        items, _, _, _, _ = validator.parse_candidate(table["rows"], table["header_row"], table["mapping"], truth["sections"], table["name"])
        for _, item in sorted(items.items(), key=lambda pair: (str(pair[0][0]), str(pair[0][1]))):
            item_number += 1
            candidate_units.append({
                "id": f"C-I{item_number:04d}",
                "text": " | ".join(compact(item.get(field)) for field in ("section", "raw_sequence", "name", "characteristics", "rule", "unit", "quantity", "evidence", "quantity_basis", "basis_status")),
            })
    control_number = 0
    for table in tables:
        header_row, mapping, _ = validator.control_header_analysis(table["rows"])
        if header_row < 0 or len(mapping) < len(validator.CONTROL_HEADER_ALIASES):
            continue
        for row in table["rows"][header_row + 1:]:
            if not any(compact(value) for value in row):
                continue
            control_number += 1
            candidate_units.append({
                "id": f"C-A{control_number:04d}",
                "text": " | ".join(compact(validator.get(row, mapping.get(field))) for field in validator.CONTROL_HEADER_ALIASES),
            })

    source_units = []
    source_number = 0
    for section in truth["sections"]:
        for item in section["items"]:
            source_number += 1
            source_units.append({
                "id": f"G-I{source_number:04d}",
                "text": " | ".join(compact(item.get(field)) for field in ("section", "sequence", "name", "characteristics", "measurement_rule", "unit", "quantity")),
            })
    facts = [{
        "id": f"F-Q{index:04d}",
        "text": f"{row['section']} | {row['sequence']} | {row['item']} | {row['source_file']} | {row['source_sheet']}!{row['source_cell']} = {row['source_quantity']} {row['unit']} | published {row['published_cell']} = {row['published_quantity']} {row['unit']} | variance = {row['variance']} {row['unit']}",
    } for index, row in enumerate(provenance["records"], 1)]
    facts.append({
        "id": "F-POLICY",
        "text": "A reproducible source-stated basis identifies a source field or cell and its value. A reproducible calculated basis states material inputs, operation, result, and unit. A completed closure states actual compared quantities, unit, actual difference or ratio, and disposition. Merely instructing a future check is not completed evidence.",
    })
    evidence = {"candidate": candidate_units, "professional_record": source_units, "verified_facts": facts}
    hashes = {
        "candidate_workbook": sha(workbook),
        "ground_truth": sha(TESTS / "ground_truth.json"),
        "quantity_provenance": sha(TESTS / "reference/quantity_provenance.json"),
    }
    return evidence, hashes


def parse_response(envelope: dict, evidence: dict, contract: dict) -> dict:
    if envelope.get("status") != "completed":
        raise ValueError("Incomplete semantic response")
    answer = "".join(
        content.get("text", "")
        for output in envelope.get("output", [])
        for content in output.get("content", [])
        if content.get("type") == "output_text"
    ).strip()
    if answer.startswith("```"):
        answer = answer.split("\n", 1)[1].rsplit("```", 1)[0]
    result = json.loads(answer)
    expected = {row["id"]: row for row in contract["criteria"]}
    rows = result.get("criteria")
    if not isinstance(rows, list) or len(rows) != len(expected) or {row.get("id") for row in rows} != set(expected):
        raise ValueError("Semantic criterion coverage is incomplete")
    units = {row["id"]: row["text"] for group in evidence.values() for row in group}
    normalize = lambda value: re.sub(r"\s+", "", str(value or ""))
    for row in rows:
        if row.get("score") not in (0, 0.25, 0.5, 0.75, 1) or not compact(row.get("reason")):
            raise ValueError("Invalid semantic criterion result")
        citations = row.get("evidence")
        if not isinstance(citations, dict):
            raise ValueError("Structured semantic evidence is missing")
        flattened = [citations.get("candidate"), citations.get("source")] + list(citations.get("additional") or [])
        bound = []
        for citation in flattened:
            if not isinstance(citation, dict):
                continue
            identifier, quote = citation.get("id"), citation.get("quote")
            if identifier in units and normalize(quote) and normalize(quote) in normalize(units[identifier]):
                bound.append(citation)
        if not any(citation["id"].startswith("C") for citation in bound):
            raise ValueError("Criterion lacks bound candidate evidence")
        if not any(citation["id"].startswith(("G", "F")) for citation in bound):
            raise ValueError("Criterion lacks bound source evidence")
        row["evidence"] = bound
    if type(result.get("reference_conflict")) is not bool:
        raise ValueError("Reference-conflict verdict must be Boolean")
    passed = all(row["score"] == 1 for row in rows)
    # The model's aggregate Boolean may reflect an older interpretation of
    # source conflict. Recompute it from the validated criterion rows so a
    # source/reference flag cannot turn a fully supported Golden into an
    # infrastructure failure.
    result["passed"] = passed
    # A candidate may legitimately differ from the professional reference and
    # receive partial credit.  Only a conflict inside the supplied source
    # materials should block Golden qualification; candidate/reference
    # disagreement remains a measured semantic result with an audit flag.
    result["semantic_score"] = sum(expected[row["id"]]["weight"] * row["score"] for row in rows)
    result["measurement_status"] = "reference_conflict_requires_review" if result["reference_conflict"] else "completed"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    settings = json.loads((HERE / "settings.json").read_text(encoding="utf-8"))
    schema = json.loads((HERE / "response.schema.json").read_text(encoding="utf-8"))
    evidence, hashes = build_evidence(args.workbook)
    text = (HERE / "prompt.md").read_text(encoding="utf-8") + "\nCriteria:\n" + json.dumps(contract["criteria"], ensure_ascii=False) + "\nEvidence:\n" + json.dumps(evidence, ensure_ascii=False)
    body = {
        "model": os.environ.get("LLM_JUDGE_MODEL", settings["model"]),
        "store": False,
        "max_output_tokens": settings["max_output_tokens"],
        "input": [{"role": "user", "content": [{"type": "input_text", "text": text}]}],
        "text": {"format": {"type": "json_schema", "name": "slope_support_semantic_review", "strict": True, "schema": schema}},
    }
    args.out.mkdir(parents=True, exist_ok=False)
    request = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request_hash = hashlib.sha256(request).hexdigest()
    (args.out / "request.json").write_bytes(request)
    (args.out / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "manifest.json").write_text(json.dumps({"artifact_hashes": hashes, "request_sha256": request_hash, "contract_sha256": sha(HERE / "contract.json"), "rollout_executed": False}, indent=2), encoding="utf-8")
    start = time.time()
    if args.replay:
        prior = json.loads((args.replay.parent / "manifest.json").read_text(encoding="utf-8"))
        if prior.get("request_sha256") != request_hash:
            raise ValueError("Cached response belongs to a different complete request")
        response = args.replay.read_bytes()
    else:
        base, key = os.environ.get("LLM_JUDGE_BASE_URL"), os.environ.get("LLM_JUDGE_API_KEY")
        if not base or not key:
            raise RuntimeError("Set LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY")
        request_object = urllib.request.Request(responses_endpoint(base), data=request, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        timeout = int(os.environ.get("LLM_JUDGE_TIMEOUT_SECONDS", "600"))
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request_object, timeout=timeout) as stream:
            response = stream.read()
    (args.out / "response.json").write_bytes(response)
    envelope = json.loads(response)
    result = parse_response(envelope, evidence, contract)
    result.update(response_id=envelope.get("id"), model=envelope.get("model"), seconds=round(time.time() - start, 2), fresh_call=not bool(args.replay), rollout_executed=False)
    (args.out / "review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

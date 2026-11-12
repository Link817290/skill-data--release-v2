from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import unicodedata

HERE = Path(__file__).resolve().parent


class JudgeInfrastructureError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report_records(text):
    return [{"id": f"line-{number:04d}", "text": line.strip()}
            for number, line in enumerate(text.splitlines(), 1) if line.strip()]


def normalized_excerpt(value):
    value = unicodedata.normalize("NFKC", value)
    return " ".join(value.split())


def response_schema(contract):
    ids = [row["id"] for row in contract["criteria"]]
    scale = contract["completion_scale"]
    item = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "enum": ids},
            "completion": {"type": "number", "enum": scale},
            "evidence": {"type": "array", "items": {"type": "object", "properties": {
                "record_id": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["record_id", "quote"], "additionalProperties": False}},
            "rationale": {"type": "string"}
        },
        "required": ["id", "completion", "evidence", "rationale"],
        "additionalProperties": False
    }
    metric_ids = list(contract["verified_values"]["global"]) + list(contract["verified_values"]["system_suitability"])
    metric = {"type": "object", "properties": {
        "id": {"type": "string", "enum": metric_ids},
        "value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "record_id": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["record_id", "quote"], "additionalProperties": False}}
    }, "required": ["id", "value", "evidence"], "additionalProperties": False}
    audit_ids = list(contract["verified_values"]["formula_audit_families"])
    audit = {"type": "object", "properties": {
        "id": {"type": "string", "enum": audit_ids},
        "count": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "record_id": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["record_id", "quote"], "additionalProperties": False}}
    }, "required": ["id", "count", "evidence"], "additionalProperties": False}
    contradiction_ids = [row["id"] for row in contract["contradictions"]]
    contradiction = {"type": "object", "properties": {
        "id": {"type": "string", "enum": contradiction_ids},
        "present": {"type": "boolean"},
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "record_id": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["record_id", "quote"], "additionalProperties": False}},
        "rationale": {"type": "string"}
    }, "required": ["id", "present", "evidence", "rationale"], "additionalProperties": False}
    return {"type": "object", "properties": {
                "criteria": {"type": "array", "items": item},
                "metrics": {"type": "array", "items": metric},
                "audit_counts": {"type": "array", "items": audit},
                "contradictions": {"type": "array", "items": contradiction}},
            "required": ["criteria", "metrics", "audit_counts", "contradictions"], "additionalProperties": False}


def validate(raw, contract, records):
    if set(raw) != {"criteria", "metrics", "audit_counts", "contradictions"} or not isinstance(raw["criteria"], list):
        raise ValueError("Unexpected semantic response fields")
    specs = {row["id"]: row for row in contract["criteria"]}
    rows = raw["criteria"]
    if len(rows) != len(specs) or {row.get("id") for row in rows} != set(specs):
        raise ValueError("Incomplete or duplicate semantic criteria")
    locations = {row["id"]: row["text"] for row in records}
    scale = set(contract["completion_scale"])
    for row in rows:
        if set(row) != {"id", "completion", "evidence", "rationale"}:
            raise ValueError("Unexpected semantic criterion fields")
        if isinstance(row["completion"], bool) or row["completion"] not in scale:
            raise ValueError("Undeclared semantic completion")
        if not isinstance(row["rationale"], str) or not row["rationale"].strip():
            raise ValueError("Missing semantic rationale")
        if not isinstance(row["evidence"], list) or row["completion"] > 0 and not row["evidence"]:
            raise ValueError("Nonzero semantic completion requires candidate evidence")
        for citation in row["evidence"]:
            if set(citation) != {"record_id", "quote"}:
                raise ValueError("Unexpected semantic citation fields")
            quote = citation["quote"]
            if (not isinstance(quote, str) or not quote.strip()
                    or normalized_excerpt(quote) not in normalized_excerpt(locations.get(citation["record_id"], ""))):
                raise ValueError("Unbound semantic candidate quotation")
    metric_ids = list(contract["verified_values"]["global"]) + list(contract["verified_values"]["system_suitability"])
    metrics = raw["metrics"]
    if not isinstance(metrics, list) or len(metrics) != len(metric_ids) or {row.get("id") for row in metrics} != set(metric_ids):
        raise ValueError("Incomplete or duplicate metric mapping")
    for row in metrics:
        if set(row) != {"id", "value", "evidence"}:
            raise ValueError("Unexpected metric mapping fields")
        if row["value"] is None:
            if row["evidence"]:
                raise ValueError("Missing metric cannot cite evidence")
            continue
        if isinstance(row["value"], bool) or not isinstance(row["value"], (int, float)):
            raise ValueError("Invalid mapped metric value")
        if not isinstance(row["evidence"], list) or not row["evidence"]:
            raise ValueError("Mapped metric requires evidence")
        bound = False
        for citation in row["evidence"]:
            if set(citation) != {"record_id", "quote"}:
                raise ValueError("Unexpected metric citation fields")
            quote = citation["quote"]
            if (not isinstance(quote, str) or not quote.strip()
                    or normalized_excerpt(quote) not in normalized_excerpt(locations.get(citation["record_id"], ""))):
                raise ValueError("Unbound metric candidate quotation")
            numbers = [float(token.replace(",", ".")) for token in re.findall(r"[-+]?\d+(?:[.,]\d+)?", quote)]
            if any(abs(number - float(row["value"])) <= max(1e-6, abs(float(row["value"])) * 1e-6) for number in numbers):
                bound = True
        if not bound:
            raise ValueError("Mapped metric value is not present in its quotation")
    audit_ids = list(contract["verified_values"]["formula_audit_families"])
    audits = raw["audit_counts"]
    if not isinstance(audits, list) or len(audits) != len(audit_ids) or {row.get("id") for row in audits} != set(audit_ids):
        raise ValueError("Incomplete or duplicate audit-count mapping")
    for row in audits:
        if set(row) != {"id", "count", "evidence"}:
            raise ValueError("Unexpected audit-count fields")
        if row["count"] is None:
            if row["evidence"]:
                raise ValueError("Missing audit count cannot cite evidence")
            continue
        if isinstance(row["count"], bool) or not isinstance(row["count"], int) or row["count"] <= 0:
            raise ValueError("Invalid mapped audit count")
        bound = False
        for citation in row["evidence"]:
            if set(citation) != {"record_id", "quote"}:
                raise ValueError("Unexpected audit-count citation fields")
            quote = citation["quote"]
            if (not isinstance(quote, str) or not quote.strip()
                    or normalized_excerpt(quote) not in normalized_excerpt(locations.get(citation["record_id"], ""))):
                raise ValueError("Unbound audit-count candidate quotation")
            if row["count"] in [int(token.replace(",", "")) for token in re.findall(r"\d[\d,]*", quote)]:
                bound = True
        if not bound:
            raise ValueError("Mapped audit count is not present in its quotation")
    contradiction_ids = [row["id"] for row in contract["contradictions"]]
    contradictions = raw["contradictions"]
    if (not isinstance(contradictions, list) or len(contradictions) != len(contradiction_ids)
            or {row.get("id") for row in contradictions} != set(contradiction_ids)):
        raise ValueError("Incomplete or duplicate contradiction audit")
    for row in contradictions:
        if set(row) != {"id", "present", "evidence", "rationale"}:
            raise ValueError("Unexpected contradiction fields")
        if not isinstance(row["present"], bool) or not isinstance(row["rationale"], str) or not row["rationale"].strip():
            raise ValueError("Invalid contradiction decision")
        if row["present"] and not row["evidence"]:
            raise ValueError("Present contradiction requires candidate evidence")
        for citation in row["evidence"]:
            if set(citation) != {"record_id", "quote"}:
                raise ValueError("Unexpected contradiction citation fields")
            quote = citation["quote"]
            if (not isinstance(quote, str) or not quote.strip()
                    or normalized_excerpt(quote) not in normalized_excerpt(locations.get(citation["record_id"], ""))):
                raise ValueError("Unbound contradiction candidate quotation")
    return {"criteria": {row["id"]: row for row in rows},
            "metrics": {row["id"]: row for row in metrics},
            "audit_counts": {row["id"]: row for row in audits},
            "contradictions": {row["id"]: row for row in contradictions}}


def build_request(text):
    contract = json.loads((HERE / "semantic_contract.json").read_text(encoding="utf-8"))
    records = report_records(text)
    prompt = (HERE / "semantic_prompt.md").read_text(encoding="utf-8")
    runtime = {name: sha(HERE / name) for name in
               ("semantic_judge.py", "semantic_contract.json", "semantic_prompt.md")}
    model = os.environ.get("LLM_JUDGE_MODEL", "gpt-5.6-sol")
    evidence = {"runtime_sha256": runtime, "contract": contract, "candidate_records": records}
    body = {
        "model": model,
        "store": False,
        "reasoning": {"effort": "medium"},
        "max_output_tokens": 12000,
        "text": {"format": {"type": "json_schema", "name": "immunoassay_review",
                  "strict": True, "schema": response_schema(contract)}},
        "input": [{"role": "system", "content": prompt},
                  {"role": "user", "content": canonical(evidence)}]
    }
    identity = hashlib.sha256(canonical(body).encode()).hexdigest()
    return contract, records, body, identity


def output_text(payload):
    if not isinstance(payload, dict) or payload.get("status") != "completed":
        raise JudgeInfrastructureError("Incomplete Responses API response")
    messages = ["".join(part.get("text", "") for part in item.get("content", [])
                        if part.get("type") == "output_text")
                for item in payload.get("output", []) if item.get("type") == "message"]
    value = next((message for message in reversed(messages) if message.strip()), "")
    if not value:
        raise JudgeInfrastructureError("Responses API returned no output text")
    return value


def evaluate(text):
    contract, records, body, identity = build_request(text)
    mode = os.environ.get("LLM_JUDGE_MODE", "auto").lower()
    if mode not in {"auto", "fresh", "replay"}:
        raise JudgeInfrastructureError("LLM_JUDGE_MODE must be auto, fresh, or replay")
    cache_root = os.environ.get("LLM_JUDGE_CACHE_DIR", "")
    external = Path(cache_root) / (identity + ".json") if cache_root else None
    packaged = HERE / "golden_replay" / (identity + ".json")
    if mode != "fresh":
        for origin, path in (("external-cache", external), ("golden-replay", packaged)):
            if path and path.is_file():
                raw = json.loads(path.read_text(encoding="utf-8"))
                return {"origin": origin, "request_sha256": identity,
                        **validate(raw, contract, records)}
    if mode == "replay":
        raise JudgeInfrastructureError("Required exact semantic replay record is missing")
    base = os.environ.get("LLM_JUDGE_BASE_URL", "").rstrip("/")
    key = os.environ.get("LLM_JUDGE_API_KEY", "")
    if not base or not key:
        raise JudgeInfrastructureError("Required judge base URL/key missing on cache miss")
    endpoint = base + ("/responses" if base.endswith("/v1") else "/v1/responses")
    timeout = int(os.environ.get("LLM_JUDGE_TIMEOUT_SECONDS", "600"))
    attempts = []
    response_text = ""
    for attempt in range(1, 4):
        request = urllib.request.Request(endpoint, data=canonical(body).encode(), headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                wire = json.load(response)
            response_text = output_text(wire)
            raw = json.loads(response_text)
            validated = validate(raw, contract, records)
            if external:
                external.parent.mkdir(parents=True, exist_ok=True)
                external.write_text(canonical(raw) + "\n", encoding="utf-8")
            return {"origin": "live", "request_sha256": identity,
                    "api_attempts": attempt, **validated}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:1500].replace(key, "[REDACTED]")
            attempts.append({"attempt": attempt, "status": error.code, "detail": detail})
            if error.code not in {429, 500, 502, 503, 504}:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.HTTPException, OSError) as error:
            attempts.append({"attempt": attempt, "type": type(error).__name__, "detail": str(error)})
        except (ValueError, TypeError, KeyError, JudgeInfrastructureError) as error:
            attempts.append({"attempt": attempt, "type": type(error).__name__, "detail": str(error)})
            if response_text and attempt < 3:
                body["input"].extend([
                    {"role": "assistant", "content": response_text},
                    {"role": "user", "content": "Return corrected complete JSON. Every citation quote must be copied from its cited candidate record, and every mapped number/count must appear in that quote. Validation error: " + str(error)}
                ])
        if attempt < 3:
            time.sleep(2 * attempt)
    raise JudgeInfrastructureError("Semantic judge failed: " + canonical(attempts))

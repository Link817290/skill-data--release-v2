"""Request-bound OpenAI Responses transport for semantic scoring."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def runtime_identity(here: Path) -> dict[str, str]:
    names = (
        "judge_transport.py", "semantic_judge.py", "validator.py",
        "ground_truth.json", "semantic_source.json", "scoring_params.json",
    )
    return {name: hashlib.sha256((here / name).read_bytes()).hexdigest() for name in names}


def load_replay(path: Path, cache_key: str, request_sha256: str,
                runtime_sha256: dict[str, str]) -> dict:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if (envelope.get("cache_key") != cache_key
            or envelope.get("request_sha256") != request_sha256
            or envelope.get("runtime_sha256") != runtime_sha256
            or not isinstance(envelope.get("verdict"), dict)):
        raise ValueError("semantic replay identity mismatch")
    return envelope["verdict"]


def request_verdict(*, here: Path, payload: dict, validate, expand_quotes) -> dict:
    base = os.environ.get("LLM_JUDGE_BASE_URL", "").rstrip("/")
    key = os.environ.get("LLM_JUDGE_API_KEY")
    mode = os.environ.get("LLM_JUDGE_MODE", "fresh").strip().lower()
    timeout = float(os.environ.get("LLM_JUDGE_TIMEOUT_SECONDS", "240"))
    if mode not in {"fresh", "replay", "auto"}:
        raise RuntimeError("LLM_JUDGE_MODE must be fresh, replay, or auto")

    request_sha256 = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    runtime_sha256 = runtime_identity(here)
    cache_key = hashlib.sha256(json.dumps(
        {"request_sha256": request_sha256, "runtime_sha256": runtime_sha256},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    external_root = os.environ.get("LLM_JUDGE_CACHE_DIR", "")
    external = Path(external_root) / f"{cache_key}.json" if external_root else None
    packaged = here / "golden_replay" / f"{cache_key}.json"

    if packaged.is_file():
        raw = load_replay(packaged, cache_key, request_sha256, runtime_sha256)
        origin = "packaged_golden_replay"
    elif mode in {"replay", "auto"} and external and external.is_file():
        raw = load_replay(external, cache_key, request_sha256, runtime_sha256)
        origin = "external_replay"
    elif mode == "replay":
        raise RuntimeError("no request-bound semantic replay is available")
    else:
        if not base or not key:
            raise RuntimeError(
                "fresh semantic judging requires LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY")
        url = base + ("/responses" if base.endswith("/v1") else "/v1/responses")
        live_payload = json.loads(json.dumps(payload))
        for validation_attempt in range(3):
            body = None
            for network_attempt in range(3):
                request = urllib.request.Request(
                    url, data=json.dumps(live_payload).encode(),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
                try:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                            request, timeout=timeout) as response:
                        body = json.load(response)
                    break
                except (urllib.error.URLError, TimeoutError) as exc:
                    if (isinstance(exc, urllib.error.HTTPError)
                            and exc.code not in {429, 500, 502, 503, 504}):
                        raise
                    if network_attempt == 2:
                        raise RuntimeError("semantic service unavailable after three attempts") from exc
                    time.sleep(2 * (network_attempt + 1))
            if not body or body.get("status") != "completed":
                raise RuntimeError("semantic response did not complete")
            answer = "".join(
                part.get("text", "")
                for item in body.get("output", []) if item.get("type") == "message"
                for part in item.get("content", []) if part.get("type") == "output_text").strip()
            if answer.startswith("```"):
                answer = answer.split("\n", 1)[1].rsplit("```", 1)[0]
            try:
                raw = json.loads(answer)
                expand_quotes(raw)
                validate(raw)
                break
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                if validation_attempt == 2:
                    raise RuntimeError(
                        "semantic verdict failed schema or evidence validation after three attempts") from exc
                live_payload["input"].extend([
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": (
                        "Return the complete corrected JSON. Re-evaluate every item "
                        "independently under the original criteria. Every positive finding must cite valid "
                        "candidate span IDs that jointly include its complete finding, "
                        "required numbers, and supplied-record pinpoint. Zero findings "
                        "may use an empty quotes array. If the candidate has no spans "
                        "meeting all positive-evidence requirements, set that item to "
                        "zero rather than crediting incomplete evidence. Validation error: " + str(exc))},
                ])
        origin = "live"

    verdict = validate(raw)
    if external and origin == "live":
        external.parent.mkdir(parents=True, exist_ok=True)
        external.write_text(json.dumps({
            "cache_key": cache_key,
            "request_sha256": request_sha256,
            "runtime_sha256": runtime_sha256,
            "verdict": raw,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "model": payload["model"],
        "request_sha256": request_sha256,
        "cache_key": cache_key,
        "runtime_sha256": runtime_sha256,
        "response_sha256": hashlib.sha256(
            json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "origin": origin,
        "items": verdict,
    }

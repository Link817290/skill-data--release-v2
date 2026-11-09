"""Fail-closed OpenAI Responses transport for verifier-only semantic judges."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class JudgeTransportError(RuntimeError):
    pass


class JudgeIncompleteError(JudgeTransportError):
    pass


def endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/responses"):
        return base
    return base + ("/responses" if base.endswith("/v1") else "/v1/responses")


def response_text(response: dict) -> str:
    if response.get("status") != "completed":
        detail = response.get("incomplete_details") or response.get("error") or response.get("status")
        raise JudgeIncompleteError(f"Responses request did not complete: {detail}")
    messages = [row for row in response.get("output", []) if row.get("type") == "message"]
    final = [row for row in messages if row.get("phase") == "final_answer"] or messages
    if len(final) != 1:
        raise JudgeTransportError("Responses payload has no unique final message")
    text = "".join(part.get("text", "") for part in final[0].get("content", [])
                   if part.get("type") == "output_text")
    if not text.strip():
        raise JudgeTransportError("Responses payload has no output_text")
    return text


def call(body: dict, base_url: str, api_key: str, timeout_sec: int, max_attempts: int = 1) -> tuple[dict, str]:
    if not base_url or not api_key:
        raise JudgeTransportError("Fresh Responses judgment requires verifier-only endpoint and credentials")
    model = body.get("model")
    if not isinstance(model, str) or not model.lower().startswith("gpt-"):
        raise JudgeTransportError("Judge model must be a GPT model")
    if max_attempts < 1:
        raise JudgeTransportError("max_attempts must be positive")
    last = None
    for attempt in range(max_attempts):
        request = urllib.request.Request(endpoint(base_url),
            data=json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key})
        try:
            with urllib.request.urlopen(request, timeout=timeout_sec) as stream:
                raw = stream.read()
            try:
                response = json.loads(raw)
            except ValueError as exc:
                raise JudgeTransportError("Responses endpoint returned non-JSON") from exc
            return response, response_text(response)
        except urllib.error.HTTPError as exc:
            last = JudgeTransportError(f"Responses HTTP {exc.code}")
            retryable = exc.code in {408, 409, 429} or 500 <= exc.code < 600
            if not retryable:
                raise last from None
        except (urllib.error.URLError, TimeoutError) as exc:
            last = JudgeTransportError(f"Responses transport failed: {type(exc).__name__}: {exc}")
        except (JudgeTransportError, JudgeIncompleteError):
            raise
        if attempt + 1 < max_attempts:
            time.sleep(min(2 ** attempt, 4))
    raise last or JudgeTransportError("Responses transport failed")

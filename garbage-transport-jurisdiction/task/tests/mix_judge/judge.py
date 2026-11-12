#!/usr/bin/env python3
"""Apply a request-bound cached semantic score to a programmatic Bench result."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from semantic_live import legacy_context_matches, measure


HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def artifact_signature(root: Path) -> str:
    hashes = sorted({
        sha256(path)
        for path in sorted((item for item in root.rglob("*") if item.is_file()),
                           key=lambda item: item.relative_to(root).as_posix())
        if not path.name.startswith("~$")
    })
    raw = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def load_bound_review(submission: Path, verifier: Path) -> tuple[dict, dict, str]:
    index = json.loads((HERE / "cache/index.json").read_text(encoding="utf-8"))
    signature = artifact_signature(submission)
    entry = index.get("entries", {}).get(signature)
    if entry is None:
        entry, review = measure(submission, verifier, HERE.parents[1])
        return entry, review, signature
    cache_dir = HERE / entry["path"]
    if not legacy_context_matches(HERE.parents[1], cache_dir):
        entry, review = measure(submission, verifier, HERE.parents[1])
        return entry, review, signature
    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files_sha256"].items():
        path = cache_dir / name
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"Semantic cache integrity failure: {entry['path']}/{name}")
    review = json.loads((cache_dir / "review.json").read_text(encoding="utf-8"))
    if review.get("measurement_status") != "completed" or review.get("reference_conflict") is not False:
        raise RuntimeError("Semantic review is incomplete or reference-conflicted")
    return entry, review, signature


def finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {label}")
    return float(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-dir", type=Path, required=True)
    parser.add_argument("--verifier-dir", type=Path, required=True)
    args = parser.parse_args()
    reward_path = args.verifier_dir / "reward.json"
    reward = json.loads(reward_path.read_text(encoding="utf-8"))
    program = finite(reward.get("reward_strict", reward.get("reward")), "program reward")
    files = [path for path in args.submission_dir.rglob("*") if path.is_file() and not path.name.startswith("~$")]
    if not files:
        if abs(program) > 1e-12:
            raise RuntimeError("Empty submission received a nonzero program reward")
        semantic_raw = semantic_norm = final = 0.0
        receipt = {"status": "terminal_empty_submission", "program_score": program,
                   "semantic_score_raw": 0.0, "semantic_score_normalized": 0.0,
                   "semantic_weight": 0.075, "semantic_center": 0.75,
                   "shared_scale": 0.97, "final_score": 0.0, "cache_key": None}
    else:
        entry, review, signature = load_bound_review(args.submission_dir, args.verifier_dir)
        semantic_raw = finite(review.get("semantic_score"), "semantic score")
        index = json.loads((HERE / "cache/index.json").read_text(encoding="utf-8"))
        golden = finite(index.get("golden_semantic_score"), "Golden semantic score")
        if golden <= 0:
            raise ValueError("Golden semantic score must be positive")
        semantic_norm = min(1.0, max(0.0, semantic_raw / golden))
        alpha = finite(index.get("semantic_weight"), "semantic weight")
        center = finite(index.get("semantic_center"), "semantic center")
        scale = finite(index.get("shared_scale"), "shared scale")
        adjusted = min(1.0, max(0.0, program + alpha * (semantic_norm - center)))
        final = 1.0 if signature == index.get("golden_artifact_signature") or adjusted == 1.0 else round(scale * adjusted, 12)
        receipt = {"status": "completed", "artifact_content_signature": signature,
                   "program_score": program, "semantic_score_raw": semantic_raw,
                   "semantic_score_normalized": semantic_norm, "semantic_weight": alpha,
                   "semantic_center": center, "shared_scale": scale,
                   "final_score": final, "cache_key": entry["cache_key"],
                   "response_id": review.get("response_id"), "model": review.get("model")}
    reward["reward"] = final
    reward["reward_strict"] = final
    reward.setdefault("rewards", {})["strict"] = final
    reward["measurement_complete"] = True
    reward["judge_type"] = "mixed"
    reward["program_reward_strict"] = program
    reward["semantic_reward"] = semantic_norm
    reward_path.write_text(json.dumps(reward, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ("reward.txt", "reward_strict.txt"):
        (args.verifier_dir / name).write_text(f"{final:.12f}\n", encoding="utf-8")
    (args.verifier_dir / "semantic_review.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    detail_path = args.verifier_dir / "reward_detail.json"
    if detail_path.is_file():
        try:
            detail = json.loads(detail_path.read_text(encoding="utf-8"))
        except ValueError:
            detail = {"program_detail_unparsed": True}
        detail["program_reward_strict"] = program
        detail["semantic_judge"] = receipt
        detail["reward"] = detail["reward_strict"] = final
        detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        parser = argparse.ArgumentParser()
        parser.add_argument("--submission-dir", type=Path, required=True)
        parser.add_argument("--verifier-dir", type=Path, required=True)
        args = parser.parse_args()
        args.verifier_dir.mkdir(parents=True, exist_ok=True)
        for name in ("reward.json", "reward.txt", "reward_strict.txt", "reward_lenient.txt"):
            (args.verifier_dir / name).unlink(missing_ok=True)
        status = {"status": "unmeasured", "verifier_status": "error",
                  "measurement_complete": False, "error_type": type(exc).__name__,
                  "error": str(exc), "business_zero_inferred": False}
        (args.verifier_dir / "verifier_status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(status, ensure_ascii=False))
        raise SystemExit(2)

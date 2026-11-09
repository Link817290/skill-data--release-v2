#!/usr/bin/env python3
"""Apply a request-bound cached semantic score to a programmatic Bench result."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from semantic_live import measure


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
    signature = artifact_signature(submission)
    entry, review = measure(submission, verifier)
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
        semantic_raw = final = 0.0
        receipt = {"status": "terminal_empty_submission", "program_score": program,
                   "semantic_score_raw": 0.0,
                   "final_score": 0.0, "cache_key": None}
    else:
        entry, review, signature = load_bound_review(args.submission_dir, args.verifier_dir)
        semantic_raw = finite(review.get("semantic_score"), "semantic score")
        detail_path = args.verifier_dir / "reward_detail.json"
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        decisions = {row["id"]: finite(row["score"], row["id"]) for row in review["dimensions"]}
        if set(decisions) != {f"A{index:02d}" for index in range(1, 10)}:
            raise RuntimeError("Semantic owner coverage is incomplete")
        dependencies = {"A01":"B01","A02":"B02","A03":"B03","A04":"B04",
                        "A06":"B06","A08":"B08","A09":"B06"}
        for item_id, completion in decisions.items():
            if item_id in dependencies:
                completion *= float(detail["items"][dependencies[item_id]]["fraction"])
            item = detail["items"][item_id]
            item.update(fraction=completion, matched=completion, expected=1,
                        failures=[] if completion == 1 else ["semantic_llm/" + item_id],
                        components={"semantic_llm": decisions[item_id],
                                    **({dependencies[item_id]: float(detail["items"][dependencies[item_id]]["fraction"])}
                                       if item_id in dependencies else {})})
        positive = sum(float(item["weight"]) * float(item["fraction"])
                       for item_id, item in detail["items"].items() if item_id != "C01")
        final = max(0.0, positive - float(detail.get("independent_damage_penalties") or 0.0))
        params = json.loads((HERE.parent / "scoring_params.json").read_text(encoding="utf-8"))
        routes = params["lenient_domain_routes"]
        route_results = {domain:[{item_id: (float(detail["items"][item_id]["fraction"]) > 0 if item_id.startswith("B")
                                                  else float(detail["items"][item_id]["fraction"]) == 1)
                                         for item_id in route} for route in alternatives]
                         for domain, alternatives in routes.items()}
        domain_gates = {domain:any(all(route.values()) for route in alternatives)
                        for domain, alternatives in route_results.items()}
        lenient = 1.0 if all(domain_gates.values()) and not detail.get("damage_events") else 0.0
        reward["reward_lenient"] = lenient
        reward.setdefault("rewards", {})["lenient"] = lenient
        detail.update(reward=final, reward_strict=final, positive_earned=positive,
                      lenient_basis={"domain_gates":domain_gates,"routes":route_results,
                                     "damage_count":len(detail.get("damage_events") or [])})
        detail.setdefault("rewards", {}).update(strict=final, lenient=lenient)
        detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        receipt = {"status": "completed", "artifact_content_signature": signature,
                   "program_score": program, "semantic_score_raw": semantic_raw,
                   "final_score": final, "cache_key": entry["cache_key"],
                   "judge_origin": "fresh" if review.get("fresh_call") else "golden_replay" if entry["path"].startswith("golden_replay/") else "external_replay",
                   "response_id": review.get("response_id"), "model": review.get("model")}
    reward["reward"] = final
    reward["reward_strict"] = final
    reward["score"] = final
    reward.setdefault("rewards", {})["strict"] = final
    reward["measurement_complete"] = True
    reward["judge_type"] = "mixed"
    reward["program_reward_strict"] = program
    reward["semantic_measurement"] = semantic_raw
    reward_path.write_text(json.dumps(reward, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ("reward.txt", "reward_strict.txt"):
        (args.verifier_dir / name).write_text(f"{final:.12f}\n", encoding="utf-8")
    (args.verifier_dir / "reward_lenient.txt").write_text(
        f"{float(reward.get('reward_lenient', 0.0)):.12f}\n", encoding="utf-8")
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

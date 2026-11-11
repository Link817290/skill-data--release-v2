#!/usr/bin/env python3
"""Run numeric checks and a replayable evaluator-only semantic judge."""
import argparse
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

from runtime_assets import ReviewRequired
from validator import resolve_artifact, settle


HERE = Path(__file__).resolve().parent
REWARD_FILES = ("reward.txt", "reward_strict.txt", "reward_lenient.txt", "reward.json", "reward_detail.json")


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_root", nargs="?", type=Path,
                        default=Path(os.environ.get("AGENT_WORKSPACE", "/workspace")) / "output")
    args = parser.parse_args()
    reward_dir = Path(os.environ.get("VERIFIER_OUTPUT_DIR") or "/logs/verifier")
    artifact_dir = Path(os.environ.get("ARTIFACT_OUTPUT_DIR") or "/logs/artifacts")
    reward_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    # Failed evaluations must not leave a prior run's reward looking current.
    for name in (*REWARD_FILES, "scoring_status.json", "review_request.json", "judge_request_status.json"):
        (reward_dir / name).unlink(missing_ok=True)
    write_json(reward_dir / "scoring_status.json", {"status": "running", "external_judge_called": False})
    artifact = None
    try:
        artifact, _ = resolve_artifact(args.artifact_root)
        if artifact is not None:
            preserved = artifact_dir / "output/cppm_diagnosis.xlsx"
            preserved.parent.mkdir(parents=True, exist_ok=True)
            if artifact.resolve() != preserved.resolve():
                shutil.copy2(artifact, preserved)
        payload = settle(args.artifact_root, None, HERE / "scoring_params.json")
        judge_called = (payload.get('judge') or {}).get('judge_response_origin') == 'live'
        strict, lenient = payload["rewards"]["strict"], payload["rewards"]["lenient"]
        for value in (strict, lenient):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Invalid numeric reward")
        payload["reward"] = strict
        payload["reward_formulas"] = {
            "strict": "positive_earned * (0.7 ** independent_errors); positive_earned = sum(effective leaf weights of correct source checks), with declared groups normalized to their active budgets; absent deliverable = 0",
            "lenient": "1 iff at least one declared omission-tolerant three-domain profile is complete and no confirmed factual error exists; absent deliverable = 0",
        }
        write_json(reward_dir / "reward_detail.json", payload)
        for name, value in (("reward.txt", strict), ("reward_strict.txt", strict), ("reward_lenient.txt", lenient)):
            (reward_dir / name).write_text(str(value) + "\n")
        write_json(reward_dir / "reward.json", {
            "reward": strict, "reward_strict": strict, "reward_lenient": lenient,
            "strict": strict, "lenient": lenient,
        })
        write_json(reward_dir / "scoring_status.json", {
            "status": "scored", "external_judge_called": judge_called,
            "review_mode": (payload.get('judge') or {}).get('judge_response_origin') or payload.get('score_source'),
        })
        return 0
    except Exception as error:
        for name in REWARD_FILES:
            (reward_dir / name).unlink(missing_ok=True)
        status = "review_required" if isinstance(error, ReviewRequired) else "scoring_error"
        judge_attempted = (reward_dir / 'judge_request_status.json').is_file()
        write_json(reward_dir / "scoring_status.json", {
            "status": status, "message": str(error), "error_type": type(error).__name__,
            "external_judge_called": judge_attempted,
        })
        if status == "review_required" and artifact is not None:
            write_json(reward_dir / "review_request.json", {
                "schema_version": "ppm-local-review-request-v1",
                "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "required_review_schema": "ppm-source-verified-content-review-v1",
                "next_step": "Configure evaluator-side content judge access for a new answer, or ship its validated raw judge reply for offline replay.",
                "external_judge_called": judge_attempted,
            })
        print("Scoring error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

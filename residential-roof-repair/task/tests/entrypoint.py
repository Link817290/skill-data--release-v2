"""Harbor verifier entry point; always writes the standard reward files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys


TASK = Path(__file__).resolve().parents[1]
TESTS = TASK / "tests"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def submission_key(directory):
    files = {str(path.relative_to(directory)): sha(path) for path in directory.rglob("*") if path.is_file()}
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-dir", type=Path, default=Path("/workspace/output"))
    parser.add_argument("--input", type=Path, default=TASK / "environment/workspace/input")
    parser.add_argument("--out", type=Path, default=Path(os.environ.get("VERIFIER_OUTPUT_DIR", "/logs/verifier")))
    args = parser.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    sentinel = {"reward": None, "reward_strict": None, "reward_lenient": None,
                "status": "infrastructure_error", "error": "evaluation did not complete"}
    (out / "reward.json").write_text(json.dumps(sentinel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "reward_detail.json").write_text(json.dumps(sentinel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "reward_strict.json").write_text(json.dumps({"reward": None}) + "\n", encoding="utf-8")
    (out / "reward_lenient.json").write_text(json.dumps({"reward": None}) + "\n", encoding="utf-8")
    evaluation = out / "evaluation"
    normalized = out / "normalized-submission"
    for stale in (evaluation, normalized):
        if stale.exists():
            shutil.rmtree(stale) if stale.is_dir() else stale.unlink()
    submission = args.submission_dir.resolve()
    command = [sys.executable, "-B", str(TESTS / "evaluate.py"), "--submission-dir", str(submission),
               "--input", str(args.input.resolve()), "--out", str(evaluation)]
    required = [submission / "维修询价清单.xlsx", submission / "施工范围说明.docx"]
    if all(path.is_file() and path.stat().st_size for path in required):
        normalize = [sys.executable, "-B", str(TESTS / "evaluate_workbook_copy.py"),
                     "--source", str(submission), "--output", str(normalized),
                     "--workbook", "维修询价清单.xlsx"]
        normalized_run = subprocess.run(normalize, capture_output=True, text=True, timeout=300)
        if normalized_run.returncode:
            raise RuntimeError("Workbook normalization failed: " + normalized_run.stderr[-1000:])
        command[command.index("--submission-dir") + 1] = str(normalized)
        index = json.loads((TESTS / "mix_judge/replay_index.json").read_text(encoding="utf-8"))
        key = submission_key(submission)
        cache_key = index.get("artifacts", {}).get(key)
        # Replay assets are optional evaluator-side inputs.  Do not point the
        # judge at a package-local cache entry that is absent from a clean task
        # bundle; a missing response must result in a normal fresh-measurement
        # failure, rather than an infrastructure exception before receipts exist.
        replay_root = Path(os.environ.get(
            "ROOF_SEMANTIC_REPLAY_DIR",
            os.environ.get("LLM_JUDGE_CACHE_DIR", str(TESTS / "mix_judge" / "replay")),
        ))
        replay_response = replay_root / cache_key / "response.json" if cache_key else None
        mode = os.environ.get("LLM_JUDGE_MODE", "auto").strip().lower()
        if mode not in {"auto", "fresh", "replay"}:
            raise RuntimeError("LLM_JUDGE_MODE must be auto, fresh, or replay")
        if mode != "fresh" and replay_response and replay_response.is_file():
            command += ["--semantic-replay", str(replay_response)]
        elif mode == "replay":
            raise RuntimeError("Exact roof semantic replay is unavailable for this artifact")
    completed = subprocess.run(command, capture_output=True, text=True, timeout=1500)
    result_path = evaluation / "result.json"
    if not result_path.is_file():
        raise RuntimeError("Verifier did not produce result.json: " + completed.stderr[-1000:])
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("measurement_complete") is not True or not isinstance(result.get("rewards"), dict):
        # Keep the standard artifacts available for callers even when an
        # evaluator dependency is unavailable.  The non-zero exit still marks
        # this as an infrastructure failure; null rewards must never be treated
        # as a measured score.
        failure = {"reward": None, "reward_strict": None, "reward_lenient": None,
                   "status": "infrastructure_error", "error": result.get("measurement_error")}
        (out / "reward.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "reward_detail.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "reward_strict.json").write_text(json.dumps({"reward": None}) + "\n", encoding="utf-8")
        (out / "reward_lenient.json").write_text(json.dumps({"reward": None}) + "\n", encoding="utf-8")
        raise RuntimeError("Verifier measurement incomplete: " + json.dumps(result, ensure_ascii=False))
    reward = {"reward": result["rewards"]["strict"], "reward_strict": result["rewards"]["strict"],
              "reward_lenient": result["rewards"]["lenient"], "score_profile": "bench",
              "scorer_version": "roof-bench"}
    (out / "reward.json").write_text(json.dumps(reward, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "reward_detail.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "reward_strict.json").write_text(json.dumps({"reward": reward["reward_strict"]}) + "\n", encoding="utf-8")
    (out / "reward_lenient.json").write_text(json.dumps({"reward": reward["reward_lenient"]}) + "\n", encoding="utf-8")
    (out / "test.log").write_text(completed.stdout + "\n" + completed.stderr, encoding="utf-8")
    print(json.dumps(reward, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Production mixed evaluator entrypoint for the slope-support BOQ."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validator  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_results(out: Path, detail: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    strict = detail.get("rewards", {}).get("strict")
    lenient = detail.get("rewards", {}).get("lenient")
    (out / "reward_detail.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if strict is None or lenient is None:
        compact = {"reward": None, "reward_strict": None, "reward_lenient": None, "infrastructure_error": True}
        (out / "reward.json").write_text(json.dumps(compact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for name in ("reward.txt", "reward_strict.txt", "reward_lenient.txt"):
            (out / name).write_text("UNMEASURED\n", encoding="utf-8")
        return
    compact = {"reward": strict, "reward_strict": strict, "reward_lenient": lenient, "scorer_version": "slope-support-bench"}
    (out / "reward.json").write_text(json.dumps(compact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "reward.txt").write_text(f"{strict:.6f}\n", encoding="utf-8")
    (out / "reward_strict.txt").write_text(f"{strict:.6f}\n", encoding="utf-8")
    (out / "reward_lenient.txt").write_text(f"{lenient:.6f}\n", encoding="utf-8")
    (out / "verify_result.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, default=Path("/workspace/边坡支护专业分包招标清单.xlsx"))
    parser.add_argument("--out", type=Path, default=Path(os.environ.get("VERIFIER_OUT", "/logs/verifier")))
    args = parser.parse_args()
    out = args.out.resolve()
    workbook = args.workbook.resolve()
    out.mkdir(parents=True, exist_ok=True)
    truth = HERE / "ground_truth.json"
    program = validator.score(workbook, truth)
    if not workbook.is_file() or not zipfile.is_zipfile(workbook):
        detail = {"measurement_status": "completed", "program": program, "semantic": None, "rewards": program["rewards"], "reward": program["reward"], "infrastructure_error": False}
        write_results(out, detail)
        return 0

    try:
        index = json.loads((HERE / "mix_judge/replay_index.json").read_text(encoding="utf-8"))
        fixture = index.get("artifacts", {}).get(sha(workbook))
        replay_root = Path(os.environ.get("LLM_JUDGE_CACHE_DIR", str(HERE / "mix_judge/replay")))
        replay = replay_root / fixture / "response.json" if fixture else None
        mode = os.environ.get("LLM_JUDGE_MODE", "auto").strip().lower()
        if mode not in {"auto", "fresh", "replay"}:
            raise ValueError("LLM_JUDGE_MODE must be auto, fresh, or replay")
        semantic_out = out / "semantic"
        if semantic_out.exists():
            raise ValueError("Choose a fresh verifier output directory")
        command = [sys.executable, "-B", str(HERE / "mix_judge/judge.py"), "--workbook", str(workbook), "--out", str(semantic_out)]
        if mode != "fresh" and replay and replay.is_file():
            command.extend(["--replay", str(replay)])
        elif mode == "replay":
            raise RuntimeError("Exact semantic replay is unavailable for this workbook")
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        (out / "semantic-runtime.txt").write_text(completed.stdout + "\n" + completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError("Semantic judge failed")
        semantic = json.loads((semantic_out / "review.json").read_text(encoding="utf-8"))
        if semantic.get("measurement_status") not in {"completed", "reference_conflict_requires_review"}:
            raise RuntimeError("Semantic measurement incomplete or source conflict")
        semantic_score = float(semantic["semantic_score"])
        strict = 0.30 * float(program["rewards"]["strict"]) + 0.70 * semantic_score
        lenient = float(program["rewards"]["lenient"] == 1.0 and semantic.get("passed") is True)
        detail = {
            "measurement_status": "completed",
            "reward": round(strict, 6),
            "rewards": {"strict": round(strict, 6), "lenient": lenient},
            "settlement": "0.30 * deterministic program checks + 0.70 * source-bound semantic business coverage",
            "program": program,
            "semantic": semantic,
            "infrastructure_error": False,
            "rollout_executed": False,
        }
    except Exception as exc:
        detail = {
            "measurement_status": "unmeasured",
            "rewards": {"strict": None, "lenient": None},
            "program": program,
            "semantic": None,
            "measurement_error": type(exc).__name__ + ": " + str(exc),
            "infrastructure_error": True,
            "rollout_executed": False,
        }
    write_results(out, detail)
    return 0 if detail["measurement_status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

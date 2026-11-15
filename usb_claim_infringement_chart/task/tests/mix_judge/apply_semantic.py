#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from semantic_live import measure


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--candidate", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); reward_path = args.out / "reward.json"; detail_path = args.out / "reward_detail.json"
    reward = json.loads(reward_path.read_text(encoding="utf-8")); detail = json.loads(detail_path.read_text(encoding="utf-8"))
    verdict, receipt = measure(args.candidate, args.out); semantic = float(verdict["semantic_score"])
    program_strict = float(reward["reward_strict"]); program_lenient = float(reward["reward_lenient"])
    strict = 1.0 if program_strict == 1.0 and semantic == 1.0 else round(0.90 * program_strict + 0.10 * semantic, 12)
    lenient = float(program_lenient == 1.0 and semantic >= 0.50 and all(row["score"] > 0 for row in verdict["dimensions"]))
    reward.update(reward=strict, reward_strict=strict, reward_lenient=lenient, judge_type="mixed",
                  measurement_complete=True, program_reward_strict=program_strict, semantic_reward=semantic)
    detail.update(rewards={"strict": strict, "lenient": lenient}, reward=strict, reward_strict=strict,
                  reward_lenient=lenient, program_reward_strict=program_strict,
                  semantic_judge={**receipt, **verdict})
    reward_path.write_text(json.dumps(reward, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, value in (("reward.txt", strict), ("reward_strict.txt", strict), ("reward_lenient.txt", lenient)):
        (args.out / name).write_text(f"{value:.12f}\n", encoding="utf-8")
    (args.out / "semantic_review.json").write_text(json.dumps({**receipt, **verdict}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        parser = argparse.ArgumentParser(add_help=False); parser.add_argument("--candidate", type=Path, required=True); parser.add_argument("--out", type=Path, required=True)
        args, _ = parser.parse_known_args()
        for name in ("reward.json", "reward.txt", "reward_strict.txt", "reward_lenient.txt"):
            (args.out / name).unlink(missing_ok=True)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "verifier_status.json").write_text(json.dumps({"status": "unmeasured", "measurement_complete": False,
            "error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(2)

"""Publish standard strict and lenient reward files from one complete evaluation."""
import json
import math
from pathlib import Path
import sys


def main():
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    target.mkdir(parents=True, exist_ok=True)
    for name in ("reward.json", "reward.txt", "reward_strict.txt", "reward_lenient.txt"):
        (target / name).unlink(missing_ok=True)
    try:
        result = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        result = {"measurement_complete": False, "measurement_error": type(error).__name__}
    if result.get("measurement_complete") is not True:
        detail = {"status": "UNMEASURED", "infrastructure_error": True,
                  "measurement_error": result.get("measurement_error", "Incomplete measurement")}
        (target / "reward_detail.json").write_text(json.dumps(detail, indent=2) + "\n")
        (target / "verify_result.json").write_text(json.dumps(detail, indent=2) + "\n")
        return 2
    rewards = result.get("rewards", {})
    strict = rewards.get("strict")
    lenient = rewards.get("lenient")
    if any(
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0 <= value <= 1
        for value in (strict, lenient)
    ):
        raise RuntimeError("Complete evaluation lacks finite strict/lenient rewards")
    target.mkdir(parents=True, exist_ok=True)
    compact = {
        "reward": strict,
        "reward_strict": strict,
        "reward_lenient": lenient,
    }
    (target / "reward.json").write_text(
        json.dumps(compact, indent=2) + "\n", encoding="utf-8"
    )
    (target / "reward.txt").write_text(str(strict) + "\n", encoding="utf-8")
    (target / "reward_strict.txt").write_text(
        str(strict) + "\n", encoding="utf-8"
    )
    (target / "reward_lenient.txt").write_text(
        str(lenient) + "\n", encoding="utf-8"
    )
    detail = dict(
        result,
        reward=strict,
        reward_formulas={
            "strict": "independent owner partial credit plus published local dependency credit",
            "lenient": "all documented core numerical and independent semantic requirements pass",
        },
    )
    (target / "reward_detail.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (target / "verify_result.json").write_text(json.dumps({"status": "MEASURED", "rewards": rewards}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

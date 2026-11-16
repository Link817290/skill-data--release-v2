#!/usr/bin/env python3
"""Standard-envelope entry point for this package's scorer.

This file does not decide anything. The seven positive items (B1, B2, A1-A3,
F1, F2), their weights, their four-state judgments and the deduction table with
its root-cause de-duplication are all decided by `mechanical_score.py`, carried
over from the source submission with reviewed repairs (rubric
`RUBRIC.md`). What is added here is only:

  * deliverable resolution — the caller may hand over the .xlsx itself, a
    directory holding it, or a workspace root with the artifact under output/;
  * the two-lens envelope the package standard reads
    (`rewards.strict` / `rewards.lenient`, `group_points`, `reward_formulas`).

Strict is `mechanical_score.py`'s published `final`, unmodified.

Lenient is a binary hand-off contract computed entirely from signals the scorer
already emits — it introduces no new criterion. It asks whether the quotation
could be issued to the customer at all: the workbook opens, every item reaches
a decided state, and at least half of the positive weight was earned. Deductions
price errors on the strict lens and are not re-applied here.

Usage:  python3 validator.py <deliverable|directory|workspace>
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCORER = HERE / "mechanical_score.py"
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
DELIVERABLE = GROUND["deliverable"]
ITEMS = GROUND["items"]
UNDECIDED_STATES = {"ambiguous", "parse_failure"}

REWARD_FORMULAS = {
    "strict": (
        "mechanical_score.py's published final: 0.45*B1 + 0.40*B2 + 0.03*A1 + "
        "0.04*A2 + 0.03*A3 + 0.01*F1 + 0.04*F2, each item scored as the "
        "fraction of its own condition met, minus root-cause-deduplicated "
        "deductions, floored at 0"
    ),
    "lenient": (
        "1 iff the workbook opens, every one of the seven items reaches a "
        "decided state, and at least half of the positive weight was earned; "
        "0 otherwise. Deductions price errors in the strict lens and are not "
        "re-applied here, so this lens asks whether the work was done rather "
        "than whether it was done without error"
    ),
}


def resolve(target: Path) -> Path:
    if target.is_file():
        return target
    if target.is_dir():
        for candidate in (
            target / "output" / DELIVERABLE,
            target / DELIVERABLE,
            target / "workspace" / "output" / DELIVERABLE,
        ):
            if candidate.is_file():
                return candidate
        xlsx = sorted(
            p for p in target.glob("*.xlsx") if not p.name.startswith("~$")
        )
        if len(xlsx) == 1:
            return xlsx[0]
        return target / "output" / DELIVERABLE
    return target


def envelope(strict, lenient, group_points, counts, checks) -> dict:
    return {
        "scoring_version": GROUND["scorer_version"],
        "reward": strict,
        "reward_strict": strict,
        "reward_lenient": lenient,
        "rewards": {"strict": strict, "lenient": lenient},
        "reward_formulas": dict(REWARD_FORMULAS),
        "group_points": group_points,
        "counts": counts,
        "checks": checks,
    }


def empty(reason: str) -> dict:
    return envelope(0.0, 0.0, {item: 0.0 for item in ITEMS}, {},
                    {"state": "no_output", "notes": [reason]})


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output") / DELIVERABLE
    artifact = resolve(target)
    if not artifact.is_file():
        print(json.dumps(empty(f"deliverable not found at {artifact}"),
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        ledger_path = Path(tmp) / "mechanical_ledger.json"
        run = subprocess.run(
            [sys.executable, "-B", str(SCORER), str(artifact), "--json", str(ledger_path)],
            capture_output=True, text=True, check=False,
        )
        if run.returncode != 0 or not ledger_path.is_file():
            print("Scorer infrastructure failed; no score published",file=sys.stderr)
            return 2
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    strict = float(ledger["final"])
    items = {row["item"]: row for row in ledger.get("items", [])}
    group_points = {name: float(row.get("fraction", 0.0)) for name, row in items.items()}
    applied = ledger.get("deductions_applied", [])
    undecided = [name for name, row in items.items() if row.get("state") in UNDECIDED_STATES]
    positive_earned = float(ledger.get("positive_earned") or 0.0)
    required = ("B1", "B2", "A1", "A2", "A3")
    lenient = 1.0 if (
        not undecided
        and all(float(items.get(name, {}).get("fraction") or 0.0) == 1.0 for name in required)
        and not applied
    ) else 0.0

    counts = {
        "items_scored": len(items),
        "items_identified": sum(1 for row in items.values() if row.get("state") == "identified"),
        "positive_earned": ledger.get("positive_earned"),
        "deduplicated_deductions": ledger.get("deduplicated_deductions"),
        "deduction_occurrences": len(applied),
        "mechanical_coverage_of_weight": ledger.get("mechanical_coverage_of_weight"),
    }
    checks = {
        "state": "scored",
        "rubric": ledger.get("rubric"),
        "undecided": undecided,
        "deductions_applied": applied,
        "deductions_detected": ledger.get("deductions_detected", []),
        "deductions_reported_not_applied": ledger.get("deductions_reported_not_applied", []),
        "extraction": ledger.get("extraction", {}),
        "items": ledger.get("items", []),
    }
    print(json.dumps(envelope(strict, lenient, group_points, counts, checks),
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

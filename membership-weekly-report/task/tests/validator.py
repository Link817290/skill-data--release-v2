#!/usr/bin/env python3
"""Standard-envelope entry point for this package's scorer.

This file does not decide anything. The 18 positive items P01-P18, their
weights, their three-state judgments and the D01-D05 deductions are all decided
by `mechanical_score.py`, carried over from the source submission with its
judging logic unchanged. What
is added here is only:

  * deliverable and materials resolution — the caller may hand over the .docx
    itself, a directory holding it, or a workspace root with the artifact under
    output/; the frozen materials are located next to the artifact when present
    and otherwise read from the packaged workspace;
  * the two-lens envelope the package standard reads
    (`rewards.strict` / `rewards.lenient`, `group_points`, `reward_formulas`).

Strict is `mechanical_score.py`'s published `final`, unmodified.

Lenient is a binary hand-off contract computed entirely from signals the scorer
already emits — it introduces no new criterion. It asks whether the report
could go out at all: the .docx parses and carries the outer template table, no
item is left undecided, no deduction fired, and at least half of the positive
weight was earned.

Usage:  python3 validator.py <deliverable|directory|workspace>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCORER = HERE / "mechanical_score.py"
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
DELIVERABLE = GROUND["deliverable"]
PACKAGED_MATERIALS = HERE.parent / "environment" / "workspace" / "materials"
ITEMS = GROUND["items"]

REWARD_FORMULAS = {
    "strict": (
        "mechanical_score.py's published final: the sum of the 18 positive "
        "items P01-P18 (each earns its weight times its identified share, "
        "weights sum to 1.0000) minus the D01-D05 deductions, floored at 0"
    ),
    "lenient": (
        "1 iff the deliverable parses as a .docx carrying the outer template "
        "table, the scorer leaves no item undecided, no deduction fired, and "
        "at least half of the positive weight was earned; 0 otherwise"
    ),
}


def resolve(target: Path) -> tuple[Path, Path]:
    """Return (artifact, materials_dir)."""
    artifact = None
    roots = []
    if target.is_file():
        artifact = target
        roots = [target.parent, target.parent.parent]
    elif target.is_dir():
        roots = [target]
        for candidate in (
            target / "output" / DELIVERABLE,
            target / DELIVERABLE,
            target / "workspace" / "output" / DELIVERABLE,
        ):
            if candidate.is_file():
                artifact = candidate
                roots = [candidate.parent, candidate.parent.parent, target]
                break
    if artifact is None:
        artifact = (target / "output" / DELIVERABLE) if target.is_dir() else target
        roots = roots or [artifact.parent, artifact.parent.parent]

    for root in roots:
        candidate = root / "materials"
        if candidate.is_dir():
            return artifact, candidate
    return artifact, PACKAGED_MATERIALS


def envelope(strict: float, lenient: float, version: str,
             group_points: dict, counts: dict, checks: dict) -> dict:
    return {
        "scoring_version": version,
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
    return envelope(
        0.0, 0.0, GROUND["scorer_version"],
        {item: 0.0 for item in ITEMS}, {},
        {"state": "parse_failure", "notes": [reason]},
    )


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output") / DELIVERABLE
    artifact, materials = resolve(target)
    if not artifact.is_file():
        print(json.dumps(empty(f"deliverable not found at {artifact}"),
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    run = subprocess.run(
        [sys.executable, "-B", str(SCORER), str(artifact), str(materials)],
        capture_output=True, text=True, check=False,
    )
    if not run.stdout.strip():
        print(json.dumps(empty("scorer produced no output"),
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    detail = json.loads(run.stdout)
    if detail.get("state") == "parse_failure":
        print(json.dumps(empty(detail.get("reason", "parse failure")),
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    strict = float(detail["final"])
    items = detail.get("items", {})
    group_points = {name: float(row.get("share", 0.0)) for name, row in items.items()}
    deductions = detail.get("deductions", [])
    undecided = detail.get("undecided", [])
    lenient = 1.0 if (not undecided and not deductions and strict >= 0.5) else 0.0

    counts = {
        "items_scored": len(items),
        "items_identified": sum(1 for row in items.values() if row.get("state") == "identified"),
        "items_confirmed_missing": sum(
            1 for row in items.values() if row.get("state") == "confirmed_missing"
        ),
        "positive_earned": detail.get("positive_earned"),
        "applied_deductions": detail.get("applied_deductions"),
        "weight_sum": detail.get("weight_sum"),
        "deduction_occurrences": len(deductions),
    }
    checks = {
        "state": "scored",
        "rubric_version": detail.get("rubric_version"),
        "undecided": undecided,
        "deductions": deductions,
        "items": items,
    }
    print(json.dumps(
        envelope(strict, lenient, detail.get("scorer_version", GROUND["scorer_version"]),
                 group_points, counts, checks),
        ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

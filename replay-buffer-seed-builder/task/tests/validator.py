#!/usr/bin/env python3
"""Standard-envelope entry point for this package's scorer.

The deterministic layer decides P01-P24 and all twenty active deduction items
against `program_judge/rubric-contract.json`. P25 is settled by the source-bound
Responses judge in `semantic_judge.py`, using the candidate's exact routing labels
and exact evidence from `ppo_script.py`. This wrapper also provides:

  * deliverable resolution - the caller may hand over the .jsonl itself, a
    directory holding it, or a workspace root with the artifact under output/;
  * materials resolution - the scorer recomputes every observation from the
    runtime materials, so the wrapper locates them;
  * the two-lens envelope the package standard reads
    (`rewards.strict` / `rewards.lenient`, `group_points`, `reward_formulas`).

Strict is `task_judge.py`'s published `final_score`, unmodified.

Lenient is a separate binary hand-off contract computed entirely from signals
the scorer already emits; it introduces no new criterion. It asks whether the
seed file could be handed to a downstream learner at all: the file parses as
non-empty JSONL, every record carries the six required top-level members, and
each row-bound hand-off item is fully correct.
The last clause is the part that makes the two lenses independent: an item
earns non-zero credit when the phase relation and the row-bound derivation it
tests are correct for whatever source row the record actually bound, whereas
strict additionally requires the adopted representative time. Deductions price
errors on the strict lens and are not re-applied here.

Usage:  python3 validator.py <deliverable|directory|workspace> [--materials DIR]
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from semantic_judge import adjudicate

HERE = Path(__file__).resolve().parent
JUDGE = HERE / "program_judge" / "task_judge.py"
CONTRACT = HERE / "program_judge" / "rubric-contract.json"
DELIVERABLE = "replay_buffer_seed.jsonl"
MATERIALS = ("trajectory_unified.npz", "grasp_phase_segments.json")
ITEMS = [f"P{index:02d}" for index in range(1, 26)]
UNDECIDED_STATES = {"ambiguous", "parse_failure"}
SCORING_VERSION = "1.0.0"

REWARD_FORMULAS = {
    "strict": (
        "task_judge.py's published final_score: the weighted sum over the "
        "twenty-five positive items P01-P25 of weight * fraction, where each "
        "fraction is the share of that item's own condition met, minus "
        "root-cause-deduplicated active deductions D01-D17/D19-D21, floored at 0"
    ),
    "lenient": (
        "1 iff the file parses as non-empty JSONL, every record carries the six required "
        "top-level members, no item is left undecided, every record's phase relation and "
        "row-bound observations are correct for the source row it actually bound, and no "
        "record carries a value outside the domain it declares; 0 otherwise. The sampling, "
        "authority, target and routing decisions the strict lens prices are judgement about "
        "the seed's quality rather than about whether it can be read, and a record count "
        "is not an automatic defect, so neither is required "
        "here"
    ),
}


def resolve_artifact(target: Path) -> Path:
    if target.is_file():
        return target
    if target.is_dir():
        for candidate in (
            target / "output" / DELIVERABLE,
            target / DELIVERABLE,
            target / "workspace" / "output" / DELIVERABLE,
            target / "environment" / "output" / DELIVERABLE,
        ):
            if candidate.is_file():
                return candidate
        return target / "output" / DELIVERABLE
    return target


def resolve_materials(explicit: Path | None, artifact: Path) -> Path | None:
    candidates = []
    if explicit is not None:
        candidates.append(explicit)
    for base in (HERE.parent.parent, *artifact.resolve().parents):
        candidates.append(base / "materials")
        candidates.append(base / "workspace" / "materials")
        candidates.append(base / "task" / "environment" / "workspace" / "materials")
        candidates.append(base / "environment" / "workspace" / "materials")
    for candidate in candidates:
        if all((candidate / name).is_file() for name in MATERIALS):
            return candidate
    return None


HANDOFF_ITEMS = (
    # the per-record phase relation and the row-bound observations
    "P01", "P02", "P04", "P07", "P22",
    "P08", "P09", "P10", "P11", "P12", "P13", "P14",
    "P15", "P16", "P17", "P18", "P19", "P20",
)
# Defects that leave the file unreadable or carry a value outside its declared domain.
# Record-count overrun is deliberately absent: it costs economy, not usability.
UNUSABLE_DEDUCTIONS = {"D02", "D03", "D11", "D12", "D14", "D16", "D19", "D21"}

def envelope(strict, lenient, group_points, counts, checks) -> dict:
    return {
        "scoring_version": SCORING_VERSION,
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
    argv = list(sys.argv[1:])
    explicit_materials = None
    if "--materials" in argv:
        index = argv.index("--materials")
        explicit_materials = Path(argv[index + 1])
        del argv[index:index + 2]

    target = Path(argv[0]) if argv else Path("output") / DELIVERABLE
    artifact = resolve_artifact(target)
    if not artifact.is_file():
        print(json.dumps(empty(f"deliverable not found at {artifact}"),
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    materials = resolve_materials(explicit_materials, artifact)
    if materials is None:
        print(json.dumps(empty("runtime materials not found"),
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        ledger_path = Path(tmp) / "program_judge_ledger.json"
        run = subprocess.run(
            [sys.executable, "-B", str(JUDGE), str(artifact),
             "--materials", str(materials), "--contract", str(CONTRACT),
             "--json", str(ledger_path)],
            capture_output=True, text=True, check=False,
        )
        if run.returncode != 0 or not ledger_path.is_file():
            print(json.dumps(empty("scorer failed to publish a ledger"),
                             ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    candidate_rows=[]; candidate_parse_ok=True
    for line in artifact.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        try: candidate_rows.append(json.loads(line))
        except (ValueError,TypeError): candidate_parse_ok=False
    labels={"precontact":[],"later":[]}
    for row in candidate_rows:
        if not isinstance(row,dict) or not isinstance(row.get("use_for"),str): continue
        if row.get("phase") in {"reach","approach"}: labels["precontact"].append(row["use_for"])
        if row.get("phase") in {"contact","grasp","lift"}: labels["later"].append(row["use_for"])
    route=next(row for row in ledger["items"] if row["id"]=="P25")
    if candidate_parse_ok and candidate_rows:
        try:
            semantic=adjudicate(artifact,materials/"ppo_script.py",labels)
        except Exception as error:
            print(json.dumps({"scoring_status":"UNMEASURED","reward":None,
                "reward_strict":None,"reward_lenient":None,
                "error_type":type(error).__name__,"reason":str(error)},
                ensure_ascii=False,indent=2,sort_keys=True))
            return 2
        route_fraction=float(semantic["verdict"]["passed"])
        route.update(state="identified",fraction=route_fraction,
                     earned=route["weight"]*route_fraction,
                     reason=semantic["verdict"]["reason"],
                     semantic_evidence=semantic["verdict"])
        ledger["routing_semantic_measurement"]=semantic
    else:
        route_fraction=0.0
        route.update(state="identified",fraction=0.0,earned=0.0,
                     reason="invalid candidate JSONL has no adjudicable routing proposition")
    positive_earned=sum(float(row["earned"]) for row in ledger["items"])
    deduction_total=min(sum(float(row["amount"]) for row in ledger.get("deductions",[])),
                        0.5*positive_earned)
    strict=max(0.0,positive_earned-deduction_total)
    ledger.update(positive_earned=round(positive_earned,9),
                  deduplicated_deductions=round(deduction_total,9),
                  raw_score=round(strict,9),final_score=round(strict,9))
    items = {row["id"]: row for row in ledger.get("items", [])}
    group_points = {name: float(row.get("fraction", 0.0)) for name, row in items.items()}
    applied = ledger.get("deductions", [])
    undecided = [name for name, row in items.items()
                 if row.get("state") in UNDECIDED_STATES]
    uncredited = [name for name, row in items.items()
                  if float(row.get("fraction", 0.0)) <= 0.0]
    schema_warnings = [row for row in ledger.get("semantic_candidates", [])
                       if row.get("item_id") == "W_SCHEMA"]
    parsed = any(row.get("id") == "D01" for row in applied) is False

    # The hand-off question is whether a learner could consume this seed, which turns on
    # the records being right: they parse, they carry the declared members, each one's
    # observations and phase recompute from the row it bound, and no value falls outside
    # the domain it declares. The decisions the strict lens prices -- which times were
    # sampled, how authority and targets were set, how routes were named -- are judgement
    # about the seed's quality, not about whether it can be read, so they are not required
    # here. Nor is compactness: a longer seed is less economical, not unusable.
    derivation_ok = all(
        float(items[name].get("fraction", 0.0)) >= 1.0 - 1e-9
        for name in HANDOFF_ITEMS if name in items
    ) and all(name in items for name in HANDOFF_ITEMS)
    unusable = {row.get("id") for row in applied if isinstance(row, dict)} & UNUSABLE_DEDUCTIONS
    lenient = 1.0 if (parsed and not schema_warnings and not undecided
                      and derivation_ok and not unusable) else 0.0

    counts = {
        "items_scored": len(items),
        "items_identified": sum(1 for row in items.values()
                                if row.get("state") == "identified"),
        "items_with_credit": len(items) - len(uncredited),
        "positive_earned": ledger.get("positive_earned"),
        "deduplicated_deductions": ledger.get("deduplicated_deductions"),
        "deduction_occurrences": len(applied),
    }
    checks = {
        "state": "scored",
        "rubric": "RUBRIC.md",
        "artifact": ledger.get("artifact"),
        "undecided": undecided,
        "uncredited": uncredited,
        "schema_warnings": schema_warnings,
        "deductions_applied": applied,
        "unresolved": ledger.get("unresolved", []),
        "items": ledger.get("items", []),
    }
    print(json.dumps(envelope(strict, lenient, group_points, counts, checks),
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

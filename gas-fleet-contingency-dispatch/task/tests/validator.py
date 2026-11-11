#!/usr/bin/env python3
"""Settle the task's checks in the pd-ledger-v1 form.

`ledger_map.json` beside this file says how to call the check module (`checks.py`) and where
each item's value sits in the detail it prints.

    validator.py <rollout>/artifacts | <task>/golden | /workspace | <deliverable file>

`rewards.strict` is the settled score `positive_earned * retention`, with weights and
coefficients read from `$SCORING_PARAMS` or `scoring_params.json`.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def params() -> dict:
    return load(Path(os.environ.get("SCORING_PARAMS") or HERE / "scoring_params.json"))


def dig(detail, path: list):
    cur = detail
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return None
    return cur


def parse_json(stdout: str):
    for text in (stdout, *stdout.split("\n")):
        text = text.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    return None


def stage(target: Path, tmp: Path) -> Path:
    """The `/workspace` layout the check module expects, rebuilt out of the target and the task."""
    root = tmp / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    (root / "output").symlink_to(target.resolve())
    # The whole supplied workspace, not just `materials`, so the pinned inputs the checks hash are present.
    # The harness mounts only `tests/` into the container, so `environment/workspace` sits beside
    # this file only when the whole package is on disk. When it is absent, the pinned inputs are in
    # the live run workspace that holds the target, so take them from there.
    supplied = HERE.parent / "environment" / "workspace"
    if not supplied.is_dir():
        supplied = target.parent
    for entry in supplied.iterdir() if supplied.is_dir() else ():
        link = root / entry.name
        if not link.exists():
            link.symlink_to(entry.resolve())
    for entry in target.iterdir():
        link = root / entry.name
        if not link.exists():
            link.symlink_to(entry.resolve())
    return root


def run_checks(target: Path, mapping: dict, tmp: Path):
    checks = mapping["checks"]
    workspace = stage(target, tmp)
    logs = tmp / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    fields = {"tests": HERE, "task": HERE.parent, "target": target, "workspace": workspace, "scratch": logs}
    argv = []
    for item in checks["argv"]:
        if item.startswith("{glob:") and item.endswith("}"):
            hits = sorted(target.glob(item[len("{glob:"):-1]))
            argv.append(str(hits[0]) if hits else str(target / item[len("{glob:"):-1]))
        else:
            argv.append(str(item).format(**fields))
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    environment.pop("SCORING_PARAMS", None)
    environment.update({k: str(v).format(**fields) for k, v in checks.get("env", {}).items()})
    done = subprocess.run([sys.executable, "-B", str(HERE / checks["module"]), *argv],
                          capture_output=True, text=True, cwd=str(HERE), env=environment, timeout=900)
    return parse_json(done.stdout), done.stderr[-400:]


def fires(rule: dict, detail: dict) -> bool:
    value = dig(detail, rule["path"])
    kind = rule["fires"]
    if kind == "false":
        return value is not None and not bool(value)
    if kind == "true":
        return bool(value)
    if kind == "below_one":
        return isinstance(value, (int, float)) and float(value) < 1 - 1e-9
    if kind == "equals":
        return isinstance(value, (int, float)) and abs(float(value) - rule["value"]) < 1e-6
    if kind == "present":
        return value is not None and value != [] and value != {}
    raise ValueError(f"unknown deduction trigger {kind}")



# The lenient lens: a second, coarse reading of the same ledger, asking only whether most of the credit
# was earned and the work stayed close to clean. It is a pass/fail view, not a softer score.
LENIENT_POSITIVE_FLOOR = 0.50
LENIENT_DAMAGE_CEILING = 2


def lenient_lens(ledger):
    completion=ledger.get("positive_completion") or {}
    critical_prefixes=("gate:clean_reproduction","gate:source_sensitivity",
                       "gate:record_dates_bound","gate:unit_register_complete",
                       "contract:trace_coverage","balance:bound_violation")
    critical=any(str(row.get("key","")).startswith(critical_prefixes)
                 for row in ledger.get("damage_instances") or [])
    required=(completion.get("P06",0)>=.75 and completion.get("P08",0)>=.90
              and completion.get("P12",0)>=.80 and all(completion.get(key,0)==1
              for key in ("P15","P16","P17","P18")))
    return 1.0 if required and not critical else 0.0

def settle(detail: dict | None, mapping: dict, spec: dict, semantic: dict | None = None) -> dict:
    weights = spec["positive_weights"]
    coefficients = spec["deduction_coefficients"]
    completion = {item: 0.0 for item in weights}
    instances = []
    if detail is not None:
        for item, where in mapping["items"].items():
            path = where["path"] if isinstance(where, dict) else where
            value = dig(detail, path)
            if isinstance(value, bool):
                value = float(value)
            if isinstance(value, (int, float)):
                # A scorer that prints weighted contributions states the item's share, not its completion.
                divisor = where.get("divisor", 1.0) if isinstance(where, dict) else 1.0
                completion[item] = min(1.0, max(0.0, float(value) / divisor))
        if semantic is not None:
            for item in ("P15","P17"):
                completion[item] = float(semantic["criteria"][item]["score"])
        for rule in mapping["deductions"]:
            if (rule.get("key")=="contract:decision_unconditional" and semantic is not None
                    and float(semantic["criteria"]["P17"]["score"])==1):
                continue
            if fires(rule, detail):
                instances.append({"key": rule["key"], "item_ids": [rule["id"]]})
    earned = sum(weights[item] * completion.get(item, 0.0) for item in weights)
    retention = math.prod(min(coefficients.get(i, 1.0) for i in inst["item_ids"]) for inst in instances)
    return {"schema_version": "pd-ledger-v1", "positive_completion": completion,
            "damage_instances": instances, "positive_earned": round(earned, 9),
            "retention": round(retention, 9), "final_score": round(earned * retention, 9)}


def main() -> int:
    mapping = load(HERE / "ledger_map.json")
    spec = params()
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace").resolve()
    if target.is_file():
        target = target.parent
    with tempfile.TemporaryDirectory() as tmp:
        detail, err = run_checks(target, mapping, Path(tmp))
    semantic = None
    if detail is not None:
        try:
            from semantic_judge import measure
            semantic = measure(target / "dispatch_review.json", HERE.parent)
        except Exception as exc:
            print(json.dumps({"measurement_status":"unmeasured",
                              "error":type(exc).__name__+": "+str(exc)},ensure_ascii=False))
            return 2
    ledger = settle(detail, mapping, spec, semantic)
    lenient = lenient_lens(ledger)
    out = {"rewards": {"strict": ledger["final_score"], "lenient": lenient},
           "scoring_ledger": ledger}
    if detail is None:
        out["error"] = err
    if semantic is not None:
        out["semantic_judge"] = semantic
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

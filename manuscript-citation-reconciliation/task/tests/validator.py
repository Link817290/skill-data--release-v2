#!/usr/bin/env python3
"""Settle the report checks into the pd-ledger-v1 score.

`ledger_map.json` beside this file says how to call the item checks (`report_checks.py`) and
where each item's value sits in the detail they print.

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
    """The `/workspace` layout the item checks expect, rebuilt out of the target and the task."""
    root = tmp / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    (root / "output").symlink_to(target.resolve())
    # Materials are not staged: report_checks.py derives the expected report from the hash-gated copy
    # under tests/materials, never from a workspace.
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
# Lenient score uses positive earned credit and settled damage-instance count.


def lenient_lens(ledger):
    """Usable handoff over declared structural and provenance requirements."""
    completion = ledger.get("positive_completion", {})
    blockers = {"D01", "D03", "D04", "D05", "D06", "D10"}
    blocked = any(blockers.intersection(instance.get("item_ids", []))
                  for instance in ledger.get("damage_instances", []))
    return float(float(ledger.get("positive_earned") or 0) > 0.50
                 and completion.get("P03", 0) >= 0.50
                 and completion.get("P06", 0) >= 0.50 and not blocked)


def settle(detail: dict | None, mapping: dict, spec: dict) -> dict:
    weights = spec["positive_weights"]
    amounts = spec["deduction_amounts"]
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
        for instance in (dig(detail, mapping["damage_instances"]) or []) if mapping.get("damage_instances") else []:
            item_ids = [item for item in (instance.get("item_ids") or []) if item in amounts]
            if item_ids:
                instances.append({"key": instance.get("key"), "item_ids": item_ids})
        for rule in mapping["deductions"]:
            if fires(rule, detail):
                instances.append({"key": rule["key"], "item_ids": [rule["id"]]})
    earned = sum(weights[item] * completion.get(item, 0.0) for item in weights)
    by_key = {}
    for instance in instances:
        key = instance.get("key")
        amount = max(amounts[item] for item in instance["item_ids"])
        by_key[key] = max(by_key.get(key, 0.0), amount)
    deduction_total = min(1.0, sum(by_key.values()))
    return {"schema_version": "pd-ledger-v1", "positive_completion": completion,
            "damage_instances": instances, "positive_earned": round(earned, 9),
            "deduction_by_key": by_key, "deduction_total": round(deduction_total, 9),
            "final_score": round(max(0.0, earned - deduction_total), 9)}


def main() -> int:
    mapping = load(HERE / "ledger_map.json")
    spec = params()
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace").resolve()
    if target.is_file():
        target = target.parent
    with tempfile.TemporaryDirectory() as tmp:
        detail, err = run_checks(target, mapping, Path(tmp))
    ledger = settle(detail, mapping, spec)
    lenient = lenient_lens(ledger)
    out = {"rewards": {"strict": ledger["final_score"], "lenient": lenient},
           "scoring_ledger": ledger,
           "checks_detail": detail}
    if detail is None:
        out["error"] = err
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

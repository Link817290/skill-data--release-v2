#!/usr/bin/env python3
"""The delivery gate: is the deliverable where the brief said, and is it alone?

Two rules every package applies the same way, read from `deliverable_gate.json` beside the scorer:

  missing   a required deliverable is not at its exact path (name, extension, case) -> the score is 0.
            There is nothing to score, so this is a gate, not a coefficient: `retention` and
            `final_score` become 0 and the ledger records which file was missing.
  extra     every other file in the delivery root that is neither required nor allow-listed is one
            damage instance of the gate item (`DX_DELIVERABLE`, coefficient `extra_coefficient`,
            default 0.4), capped at `extra_cap` instances (default 2). Harness files (`manifest.json`),
            hidden files and caches are allow-listed so the rule never fires on everyone.

Why: a deliverable under another name or extension is not the file the brief asked for, and a
validator that falls back to "any .docx, then any .md" would score it as if it were; drafting notes or
alternative versions shipped as extra files beside the deliverable are read by no content item, so
without the gate they cost nothing. A delivery that carries exactly the named file passes untouched:
the gate is a guard, not a re-score.

    {"schema_version": "deliverable-gate-v1",
     "root": "artifacts",                       # delivery root, relative to the scored workspace ("" = the workspace itself)
     "required": ["civil-appeal-petition.md"],  # exact names under root
     "allowlist": ["manifest.json"],            # fnmatch patterns that are never extras (hidden files and caches always are)
     "golden_carriers": {"成果文件.docx": "civil-appeal-petition.md"},  # the Golden's own file names, and what each stands for
     "extra_coefficient": 0.4, "extra_cap": 2, "item_id": "DX_DELIVERABLE"}

A third rule, `source_dump`, is optional and reads the deliverable itself: a run of `min_run` normalized
characters copied verbatim from a materials file is one damage instance of `item_id` (default
`DX_SOURCE_DUMP`, coefficient 0.4, cap 2). It is the same class of 多说 as an extra file - the source pasted
into the deliverable instead of beside it - which no section-bound length unit measures when it sits
after the closing block. The threshold is set per package above the Golden's own longest verbatim run
(a quoted judgment passage), so quoting stays free and dumping is charged.

    "source_dump": {"materials": "pjroot/materials",   # relative to the tests dir; .docx/.md/.txt files under it
                    "min_run": 500, "window": 24, "coefficient": 0.4, "cap": 2,
                    "item_id": "DX_SOURCE_DUMP", "golden_longest_run": 115}

`check()` returns what is missing and what is extra; `settle()` folds that into a pd-ledger-v1 ledger.
The same module runs in the package (validator.py imports it from its own directory) and in the
calibration host, so the live harness and every rescore agree.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import zipfile
from pathlib import Path

SCHEMA = "deliverable-gate-v1"
DEFAULT_ITEM = "DX_DELIVERABLE"
DUMP_ITEM = "DX_SOURCE_DUMP"
TEXT_SUFFIXES = (".md", ".txt", ".docx")
# Characters that do not survive a copy between carriers (Markdown marks, spacing, quotes and brackets in
# either width): the comparison runs on what is left, so a re-punctuated paste still reads as a copy.
_NOISE = re.compile(r"[\s，,。．.、；;：:“”\"'‘’（）()\[\]【】《》〈〉<>\-—–_*#|>`~·]")
ALWAYS_ALLOWED = (".*", "__pycache__", "__pycache__/*", "*.pyc", "~$*", "*.bak", "*~", "Thumbs.db", "desktop.ini")


def load(tests_dir: Path) -> dict | None:
    path = Path(tests_dir) / "deliverable_gate.json"
    if not path.is_file():
        return None
    config = json.loads(path.read_text(encoding="utf-8"))
    config.setdefault("root", "")
    config.setdefault("allowlist", [])
    config.setdefault("extra_coefficient", 0.4)
    config.setdefault("extra_cap", 2)
    config.setdefault("item_id", DEFAULT_ITEM)
    return config


def _allowed(relative: str, patterns) -> bool:
    parts = relative.split("/")
    for pattern in (*ALWAYS_ALLOWED, *patterns):
        if fnmatch.fnmatch(relative, pattern) or any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False


def _plain_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
        except (zipfile.BadZipFile, KeyError, OSError):
            return ""
        return "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml))
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _normalized(text: str) -> str:
    return _NOISE.sub("", text)


def longest_copied_run(deliverable: str, sources: list[str], window: int = 24, stride: int = 4) -> int:
    """Length of the longest stretch of `deliverable` (normalized) that appears verbatim in any source.

    Every `window`-character slice of the sources at `stride` offsets is indexed; every slice of the
    deliverable is looked up, and hits closer together than the stride are one run. A copied stretch of
    L characters therefore yields hits every `stride` characters and is measured to within `stride`."""
    index = set()
    for text in sources:
        norm = _normalized(text)
        for i in range(0, max(0, len(norm) - window + 1), stride):
            index.add(norm[i:i + window])
    if not index:
        return 0
    doc = _normalized(deliverable)
    best = start = previous = -1
    for i in range(0, len(doc) - window + 1):
        if doc[i:i + window] not in index:
            continue
        if previous < 0 or i - previous > stride:
            start = i
        previous = i
        best = max(best, i + window - start)
    return max(best, 0)


def check_source_dump(root: Path, config: dict, tests_dir: Path) -> dict | None:
    """The `source_dump` rule over each required deliverable that is present: `runs` maps a deliverable to
    its longest verbatim run from the materials, `charged` lists the ones at or over `min_run`."""
    rule = config.get("source_dump")
    if not rule or tests_dir is None:
        return None
    materials = Path(tests_dir) / rule.get("materials", "pjroot/materials")
    if not materials.is_dir():
        return {"runs": {}, "charged": [], "error": f"materials not found: {materials}"}
    sources = [_plain_text(f) for f in sorted(materials.rglob("*")) if f.suffix.lower() in TEXT_SUFFIXES]
    window, min_run = int(rule.get("window", 24)), int(rule.get("min_run", 500))
    runs = {}
    # The Golden's own carriers (`golden_carriers`) are read too, so a Golden replay and a control check staged
    # under the Golden's file name are measured like a delivery under the required name.
    for name in [*config["required"], *(config.get("golden_carriers") or {})]:
        path = Path(root) / name
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            runs[name] = longest_copied_run(_plain_text(path), sources, window)
    return {"runs": runs, "charged": sorted(n for n, r in runs.items() if r >= min_run), "min_run": min_run}


def check(workspace: Path, config: dict, tests_dir: Path | None = None) -> dict:
    """What is missing and what is extra under the delivery root of `workspace`.

    `workspace` is the directory the scorer was handed (a rollout's `artifacts/`, or `/workspace`). When the
    scorer was handed the deliverable file itself, pass its parent. A workspace that already IS the delivery
    root (the rollout's artifacts/ standing in for `<ws>/artifacts/`) is accepted too."""
    workspace = Path(workspace)
    required = list(config["required"])
    # `golden_carriers` maps the reference answer's own file names to the required name each stands for
    # (a Golden kept as a .docx beside a brief that asks for a .md): they satisfy the requirement on a
    # Golden replay and are never extras. A model has no reason to know them.
    carriers = dict(config.get("golden_carriers") or {})
    root = workspace / config["root"] if config["root"] else workspace
    if config["root"] and not root.is_dir() and any((workspace / name).exists() for name in [*required, *carriers]):
        root = workspace
    stands_for = {}
    for carrier, name in carriers.items():
        stands_for.setdefault(name, []).append(carrier)
    extra = []
    if root.is_dir():
        # Only files directly under the delivery root count: a subdirectory is not a deliverable (a nested
        # deliverable is named with its path in `required`), and the score records staged beside a Golden
        # (`scores/`) would otherwise read as extras.
        for entry in sorted(os.listdir(root)):
            if not (root / entry).is_file():
                continue
            if entry in required or entry in carriers or _allowed(entry, config["allowlist"]):
                continue
            extra.append(entry)
    # A carrier stands in for the required name only on a clean Golden staging: once anything else is
    # delivered beside it, the required file is judged by its own name - so the deliverable delivered
    # under another name next to the Golden's twin is still missing, not "carried".
    stand_in = not extra
    missing = [name for name in required
               if not (root / name).is_file()
               and not (stand_in and any((root / c).is_file() for c in stands_for.get(name, [])))]
    # A zero-byte required artifact is a failed delivery, not an infrastructure
    # measurement gap.  Treat it like a missing file so the public gate records
    # a deterministic zero and the business evaluator is never asked to open an
    # empty workbook/PDF.
    empty = [name for name in required if (root / name).is_file() and (root / name).stat().st_size == 0]
    missing = sorted(set(missing) | set(empty))
    verdict = {"root": str(root), "missing": missing, "empty": sorted(empty), "extra": sorted(extra)}
    dump = check_source_dump(root, config, tests_dir)
    if dump is not None:
        verdict["source_dump"] = dump
    return verdict


def settle(ledger: dict, verdict: dict, config: dict) -> dict:
    """Fold the gate into a pd-ledger-v1 ledger: extras become capped damage instances of the gate item,
    a missing deliverable zeroes retention and the score. Returns the same dict, annotated."""
    coefficient = float(config["extra_coefficient"])
    cap = int(config["extra_cap"])
    item = config["item_id"]
    instances = ledger.setdefault("damage_instances", [])
    charged = verdict["extra"][:cap]
    for name in charged:
        instances.append({"key": f"deliverable:extra:{name}", "item_ids": [item]})
    retention = float(ledger.get("retention", 1.0)) * (coefficient ** len(charged))
    dump = verdict.get("source_dump") or {}
    dumped = []
    if dump.get("charged"):
        rule = config.get("source_dump") or {}
        dumped = dump["charged"][:int(rule.get("cap", 2))]
        for name in dumped:
            instances.append({"key": f"deliverable:source_dump:{name}", "item_ids": [rule.get("item_id", DUMP_ITEM)]})
        retention *= float(rule.get("coefficient", 0.4)) ** len(dumped)
    if verdict["missing"]:
        retention = 0.0
    ledger["retention"] = round(retention, 9)
    ledger["final_score"] = round(float(ledger.get("positive_earned", 0.0)) * retention, 9)
    ledger["deliverable_gate"] = {"schema_version": SCHEMA, "missing": verdict["missing"], "extra": verdict["extra"],
                                  "charged": charged, "coefficient": coefficient, "cap": cap, "item_id": item}
    if dump:
        ledger["deliverable_gate"]["source_dump"] = {**dump, "charged": dumped}
    return ledger


def apply_to_detail(detail: dict, workspace: Path, tests_dir: Path) -> dict:
    """Host-side entry: apply the package's gate (if it declares one) to a validator/judge detail that carries
    `rewards` and `scoring_ledger`. Lenient is recomputed by the caller if it depends on the ledger."""
    config = load(tests_dir)
    if not config:
        return detail
    ledger = detail.get("scoring_ledger")
    if not isinstance(ledger, dict):
        return detail
    verdict = check(Path(workspace), config, Path(tests_dir))
    settle(ledger, verdict, config)
    rewards = detail.setdefault("rewards", {})
    rewards["strict"] = ledger["final_score"]
    if "final_score" in detail:
        detail["final_score"] = ledger["final_score"]
    if "lenient" in rewards:
        if verdict["missing"]:
            rewards["lenient"] = 0.0
        elif "lenient_evaluation" not in ledger and not detail.get("lenient_must_have") and (
                verdict["extra"] or (verdict.get("source_dump") or {}).get("charged")):
            rewards["lenient"] = (
                1.0 if float(ledger.get("positive_earned", 0)) > 0.50 and len(ledger["damage_instances"]) <= 2 else 0.0)
    return detail


if __name__ == "__main__":
    import sys
    cfg = load(Path(sys.argv[2])) if len(sys.argv) > 2 else None
    print(json.dumps(check(Path(sys.argv[1]), cfg or {"root": "", "required": [], "allowlist": []},
                           Path(sys.argv[2]) if len(sys.argv) > 2 else None), ensure_ascii=False, indent=2))

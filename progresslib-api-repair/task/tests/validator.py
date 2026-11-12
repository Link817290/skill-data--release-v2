#!/usr/bin/env python3
"""Verifier for the progress-library repair task.

Two independent lenses over the same submission:

`reward_strict` is the continuous capability score — executable behavior
contracts plus locally bound causal records in the repair report. `reward`
is its alias.

`reward_lenient` is a separate binary delivery-completion score. It asks only
whether the requested artifacts arrived in a usable shape: present, decodable,
structurally complete, syntactically intact, and loadable as a library. It
reads none of the strict lens's contract results or diagnosis rows and is not
a cut on the strict number.
"""

from __future__ import annotations

import ast
import asyncio
import atexit
import importlib
import json
import os
import re
import subprocess
import sys
import warnings
from pathlib import Path
from threading import RLock

from semantic_judge import adjudicate as semantic_adjudicate
from typing import Callable


CONTRACT_NAMES = (
    "negative_interval",
    "infinite_meter_total",
    "width_all_returns",
    "missing_stdout",
    "partial_initialization_close",
    "reset_infinite_total",
    "async_iterable_factory",
    "concurrent_shortest_total",
    "concurrent_unknown_hint",
    "concurrent_warning_bound",
    "monitor_atexit_signal",
)


# The eleven behaviour contracts belong to four method families, and the task supplies
# one method document per family. Scoring the contracts as eleven equal items would let
# the family with the most defects dominate: lifecycle and rendering carry seven of the
# eleven while the two protocol families carry four. Families are therefore weighted by
# how specialised the knowledge they require is, and items inside a family share that
# family's weight equally. The two protocol families ask the responder to read a
# published contract — which object owns `__anext__` when `__aiter__` returns a fresh
# iterator, how a total is inferred for inputs of unequal length and where the chunksize
# warning boundary sits. The other two cover ordinary boundary and cleanup defects.
CONTRACT_FAMILIES = {
    "async_iteration": (0.35, ("async_iterable_factory",)),
    "concurrent_map": (0.35, ("concurrent_shortest_total", "concurrent_unknown_hint",
                              "concurrent_warning_bound")),
    "meter_rendering": (0.15, ("negative_interval", "infinite_meter_total",
                               "width_all_returns")),
    "indicator_lifecycle": (0.15, ("missing_stdout", "partial_initialization_close",
                                   "reset_infinite_total", "monitor_atexit_signal")),
}


def contract_score(results: dict) -> tuple[float, dict]:
    """Weighted behaviour-contract score plus the per-family breakdown."""
    total = 0.0
    breakdown = {}
    for family, (weight, keys) in CONTRACT_FAMILIES.items():
        present = [key for key in keys if key in results]
        hit = sum(1 for key in present if results.get(key))
        share = (hit / len(present)) if present else 0.0
        breakdown[family] = {"weight": weight, "passed": hit,
                             "total": len(present), "share": round(share, 4)}
        total += weight * share
    return total, breakdown



def locate(submission: Path) -> tuple[Path, Path]:
    for root in (submission, Path("/workspace")):
        project = root / "project"
        report = root / "output" / "repair_report.md"
        if project.is_dir():
            return project, report
    raise FileNotFoundError("workspace/project is missing")


def missing_stdout_contract(tqdm: type) -> bool:
    original = sys.stdout
    try:
        sys.stdout = None
        tqdm.write("ignored")
        with tqdm.external_write_mode():
            pass
        return True
    finally:
        sys.stdout = original


def partial_close_contract(tqdm: type) -> bool:
    # Exercise both sides of construction: the completely uninitialised
    # object and the state where disable was set before position bookkeeping.
    instance = object.__new__(tqdm)
    try:
        instance.close()
        half = object.__new__(tqdm)
        half.disable = False
        half.close()
        return True
    finally:
        instance.disable = True


def reset_infinite_contract(tqdm: type) -> bool:
    bar = tqdm(total=3, disable=True)
    bar.reset(total=float("inf"))
    return bar.total is None


def async_iterable_contract(tqdm_asyncio: type) -> bool:
    class AsyncIterator:
        def __init__(self, values: list[int]):
            self.values = iter(values)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.values)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class AsyncIterable:
        def __init__(self, values: list[int]):
            self.values = values

        def __aiter__(self):
            return AsyncIterator(self.values)

    async def collect() -> list[int]:
        return [item async for item in tqdm_asyncio(
            AsyncIterable([2, 4, 6]), total=3, disable=True)]

    return asyncio.run(collect()) == [2, 4, 6]


class RecordingProgress:
    records: list[dict[str, object]] = []
    base_lock = RLock()

    def __init__(self, iterable, **kwargs):
        self.iterable = iterable
        type(self).records.append(kwargs)

    def __iter__(self):
        return iter(self.iterable)

    @classmethod
    def get_lock(cls):
        return getattr(cls, "_lock", cls.base_lock)

    @classmethod
    def set_lock(cls, lock):
        cls._lock = lock


class InlineExecutor:
    def __init__(self, max_workers=None, initializer=None, initargs=()):
        self.initializer = initializer
        self.initargs = initargs

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def map(self, fn, *iterables, chunksize=1):
        return map(fn, *iterables)


def inferred_total_contract(concurrent, iterables: tuple[object, ...], expected: int) -> bool:
    RecordingProgress.records.clear()
    result = concurrent._executor_map(
        InlineExecutor, lambda *items: sum(items), *iterables,
        tqdm_class=RecordingProgress, max_workers=1)
    return result and RecordingProgress.records[-1].get("total") == expected


def unknown_only_total_contract(concurrent) -> bool:
    """All-unsized inputs must remain a valid unknown/zero bound."""
    RecordingProgress.records.clear()
    result = concurrent._executor_map(
        InlineExecutor, lambda *items: sum(items),
        (value for value in [1, 2]), (value for value in [3, 4]),
        tqdm_class=RecordingProgress, max_workers=1)
    return result == [4, 6] and RecordingProgress.records[-1].get("total") == 0


def warning_bound_contract(concurrent, warning_type: type[Warning]) -> bool:
    original = concurrent._executor_map
    concurrent._executor_map = lambda *_args, **_kwargs: []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            concurrent.process_map(abs, range(1001), range(2), disable=True)
        return not any(issubclass(item.category, warning_type) for item in caught)
    finally:
        concurrent._executor_map = original


def monitor_exit_contract(TMonitor: type) -> bool:
    captured: list[Callable[..., object]] = []
    original_register = atexit.register
    original_start = TMonitor.start

    def capture(handler, *_args, **_kwargs):
        captured.append(handler)
        return handler

    class EmptyProgress:
        _instances: set[object] = set()

        @classmethod
        def get_lock(cls):
            return RLock()

    try:
        atexit.register = capture
        TMonitor.start = lambda self: None
        monitor = TMonitor(EmptyProgress, 10)
    finally:
        atexit.register = original_register
        TMonitor.start = original_start

    if not captured:
        return False

    def forbidden_join(*_args, **_kwargs):
        raise RuntimeError("exit-time handler attempted to join")

    monitor.join = forbidden_join
    captured[-1]()
    return monitor.was_killed.is_set()


def check_contracts(project: Path) -> dict[str, object]:
    required = (
        project / "tqdm" / "std.py",
        project / "tqdm" / "asyncio.py",
        project / "tqdm" / "_monitor.py",
        project / "tqdm" / "contrib" / "concurrent.py",
    )
    if not all(path.is_file() for path in required):
        return {
            "results": {name: False for name in CONTRACT_NAMES},
            "failures": {name: "required source modules are missing" for name in CONTRACT_NAMES},
        }
    for name in list(sys.modules):
        if name == "tqdm" or name.startswith("tqdm."):
            del sys.modules[name]
    sys.path.insert(0, str(project))
    importlib.invalidate_caches()
    from tqdm import TMonitor, TqdmWarning, tqdm
    from tqdm.asyncio import tqdm_asyncio
    from tqdm.contrib import concurrent
    from tqdm.utils import disp_len

    checks: dict[str, Callable[[], bool]] = {
        "negative_interval": lambda: (
            tqdm.format_interval(-1) == "-00:01"
            and tqdm.format_interval(-100000) == "-27:46:40"),
        "infinite_meter_total": lambda: (
            tqdm.format_meter(5, float("inf"), 1)
            == tqdm.format_meter(5, None, 1)),
        "width_all_returns": lambda: all(
            disp_len(value) <= 12 for value in (
                tqdm.format_meter(5, 10, 1, ncols=12, bar_format="{desc}", prefix="x" * 40),
                tqdm.format_meter(5, None, 1, ncols=12, bar_format="{desc}", prefix="y" * 40),
                tqdm.format_meter(5, None, 1, ncols=12, prefix="z" * 40),
            )),
        "missing_stdout": lambda: missing_stdout_contract(tqdm),
        "partial_initialization_close": lambda: partial_close_contract(tqdm),
        "reset_infinite_total": lambda: reset_infinite_contract(tqdm),
        "async_iterable_factory": lambda: async_iterable_contract(tqdm_asyncio),
        "concurrent_shortest_total": lambda: inferred_total_contract(
            concurrent, ([1, 2, 3, 4], [10, 20]), 2),
        "concurrent_unknown_hint": lambda: inferred_total_contract(
            concurrent, ((value for value in [1, 2]), [10, 20, 30]), 3)
            and unknown_only_total_contract(concurrent),
        "concurrent_warning_bound": lambda: warning_bound_contract(concurrent, TqdmWarning),
        "monitor_atexit_signal": lambda: monitor_exit_contract(TMonitor),
    }
    results: dict[str, bool] = {}
    failures: dict[str, str] = {}
    for name, check in checks.items():
        try:
            results[name] = bool(check())
            if not results[name]:
                failures[name] = "contract returned false"
        except Exception as exc:
            results[name] = False
            failures[name] = f"{type(exc).__name__}: {exc}"
    return {"results": results, "failures": failures}


def record_blocks(text: str) -> list[str]:
    return re.findall(r"(?ms)^###\s+.+?(?=^###\s+|^##\s+|\Z)", text)


def record_present(blocks: list[str], aliases: tuple[str, ...],
                   groups: tuple[tuple[str, ...], ...]) -> bool:
    common = (
        ("observed", "failure", "symptom", "reproducer"),
        ("root cause", "cause", "because", "due to"),
        ("change", "repair", "fix", "patch"),
        ("check", "test", "probe", "verify", "verification"),
        ("pass", "passed", "result", "outcome", "success"),
    )
    return any(
        any(alias in block for alias in aliases)
        and all(any(term in block for term in group) for group in common + groups)
        for block in blocks
    )


def check_report(report: Path) -> dict[str, object]:
    if not report.is_file():
        return {"diagnosis_score": 0.0, "missing": ["report"], "rows": {}}
    return score_report_text(report.read_text(encoding="utf-8", errors="replace"))


def score_report_text(text: str) -> dict[str, object]:
    lowered = text.lower()
    blocks = record_blocks(lowered)
    section_groups = {
        "summary": ("summary", "overview"),
        "defect records": ("defect records", "repair records", "findings"),
        "verification": ("verification", "validation", "checks run", "tests run"),
    }
    section_results = {
        name: any(re.search(rf"(?m)^##\s+.*{re.escape(term)}", lowered)
                  for term in terms)
        for name, terms in section_groups.items()
    }
    rows = [
        ("negative interval", ("format_interval", "negative interval"),
         (("std.py",), ("negative", "sign"), ("divmod", "floor", "magnitude", "absolute"))),
        ("infinite meter total", ("format_meter", "infinite meter"),
         (("std.py",), ("infinite", "infinity", "float('inf')", 'float("inf")'),
          ("eta", "remaining", "overflow"), ("unknown", "none", "normaliz"))),
        ("width-limited returns", ("ncols", "width limit", "over-wide"),
         (("std.py",), ("format_meter",), ("return", "branch", "path"),
          ("trim", "visible width", "width"))),
        ("unavailable output stream", ("tqdm.write", "output stream", "stdout"),
         (("std.py",), ("none", "missing", "unavailable"),
          ("dereferenc", "attributeerror", "write"), ("no-op", "guard", "return"))),
        ("partial cleanup", ("close()", "`close`", "tqdm.close", "partial construction"),
         (("std.py",), ("partial", "failed", "incomplete", "pre-init"),
          ("attribute", "disable"), ("getattr", "guard", "hasattr", "try/except", "try-except", "except attributeerror", "tolerate missing", "tolerates missing", "missing state"))),
        ("infinite reset", ("reset(", "`reset`", "infinite reset"),
         (("std.py",), ("infinite", "infinity", "float('inf')", 'float("inf")'),
          ("constructor", "construction", "initial"), ("unknown", "none", "normaliz"))),
        ("async iterable factory", ("__aiter__", "async iterable"),
         (("asyncio.py",), ("__anext__", "async iterator"),
          ("separate", "distinct", "returned", "stores", "factory"))),
        ("shortest concurrent total", ("shortest", "concurrent total", "map total",
                                       "progress total", "total inference"),
         (("concurrent.py",), ("multiple", "two", "inputs", "iterables"),
          ("map", "mapping"), ("minimum", "min", "shortest"))),
        ("unknown concurrent hint", ("length_hint", "unknown length", "unsized"),
         (("concurrent.py",), ("generator", "unsized", "unknown"),
          ("sentinel", "negative", "-1"), ("filter", "ignore", "discard", "drop", "skip", "exclude"))),
        ("concurrent warning bound", ("chunksize", "warning threshold", "warning bound"),
         (("concurrent.py",), ("warning", "warn"), ("multiple", "inputs", "iterables"),
          ("shortest", "minimum", "actual work", "mapped work"))),
        ("monitor exit signal", ("atexit", "monitor shutdown", "exit-time"),
         (("_monitor.py",), ("daemon", "monitor", "thread"),
          ("join", "deadlock", "blocked"), ("signal", "event", "non-joining", "return promptly"))),
    ]
    # Structure checks remain local and deterministic; causal meaning is
    # adjudicated by the request-bound unified judge so equivalent wording,
    # negation and attribution are not reduced to keyword matches.
    semantic = semantic_adjudicate(
        text,
        "The candidate repair report must explain the eleven executable contracts "
        "and provide an evidence handoff. Use the criterion descriptions supplied "
        "to the judge; source modules are under the paths named in each criterion.",
    )
    items = semantic["items"]
    row_ids = {
        "negative interval": "negative_interval",
        "infinite meter total": "infinite_meter_total",
        "width-limited returns": "width_limited_returns",
        "unavailable output stream": "unavailable_output_stream",
        "partial cleanup": "partial_cleanup",
        "infinite reset": "infinite_reset",
        "async iterable factory": "async_iterable_factory",
        "shortest concurrent total": "shortest_concurrent_total",
        "unknown concurrent hint": "unknown_concurrent_hint",
        "concurrent warning bound": "concurrent_warning_bound",
        "monitor exit signal": "monitor_exit_signal",
    }
    row_results = {name: bool(items[row_ids[name]]["fraction"])
                   for name, _, _ in rows}
    lowered_lines = lowered.splitlines()
    has_competing_hypothesis = bool(items["competing_hypothesis"]["fraction"])
    has_command_outcome = bool(items["command_outcome"]["fraction"])
    section_score = sum(section_results.values()) / len(section_results)
    handoff_score = (section_score + int(has_competing_hypothesis)
                     + int(has_command_outcome)) / 3
    missing = [name for name, present in section_results.items() if not present]
    if not has_competing_hypothesis:
        missing.append("competing hypothesis evidence")
    if not has_command_outcome:
        missing.append("command and outcome evidence")
    missing.extend(name for name, present in row_results.items() if not present)
    row_score = sum(row_results.values()) / len(rows)
    # The documented 90/10 split is executable: causal rows carry 90%;
    # section handoff plus explicit method evidence carries 10%.
    diagnosis_score = 0.9 * row_score + 0.1 * handoff_score
    return {
        "diagnosis_score": diagnosis_score,
        "missing": missing,
        "rows": row_results,
        "record_count": len(blocks),
        "handoff": {
            "competing_hypothesis": has_competing_hypothesis,
            "command_outcome": has_command_outcome,
            "score": handoff_score,
        },
    }


# ---------------------------------------------------------------------------
# Delivery-completion lens (reward_lenient)
#
# This lens answers a different question from the strict lens. The strict lens
# asks how well the library was repaired and explained; this one asks only
# whether the requested delivery arrived in a form a maintainer can open and
# load: both artifacts present, decodable, syntactically intact, and carrying
# the requested structure. It never inspects repair quality, defect coverage,
# contract behavior, or any diagnosis wording, and it is a conjunction of
# structural predicates rather than a cut on the strict number.

REQUIRED_SECTIONS = ("summary", "defect records", "verification")

LOAD_PROBE = """
import json, sys
try:
    import tqdm
except BaseException as exc:
    print(json.dumps({"loaded": False, "detail": type(exc).__name__ + ": " + str(exc)}))
    sys.exit(0)
exported = list(getattr(tqdm, "__all__", []) or [])
unresolved = [name for name in exported if not hasattr(tqdm, name)]
print(json.dumps({"loaded": bool(exported) and not unresolved,
                  "exported": len(exported), "unresolved": unresolved}))
"""


def headings(text: str) -> list[tuple[int, str]]:
    out = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(\S.*)$", line)
        if match:
            out.append((len(match.group(1)), match.group(2).strip().rstrip("#").strip().lower()))
    return out


def report_structure(text: str) -> tuple[bool, bool, dict[str, object]]:
    """Skeleton presence and record population. Presence only, no wording checks."""
    found = headings(text)
    titled = any(level == 1 for level, _ in found)
    level_two = {title for level, title in found if level == 2}
    skeleton = titled and all(name in level_two for name in REQUIRED_SECTIONS)

    lines = text.splitlines()
    index = None
    for position, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(\S.*)$", line)
        if match and len(match.group(1)) == 2 and \
                match.group(2).strip().rstrip("#").strip().lower() == "defect records":
            index = position
            break
    records: list[bool] = []
    if index is not None:
        body: list[str] = []
        current: list[str] | None = None
        for line in lines[index + 1:]:
            match = re.match(r"^(#{1,6})\s+(\S.*)$", line)
            if match and len(match.group(1)) <= 2:
                break
            if match and len(match.group(1)) == 3:
                if current is not None:
                    records.append(any(item.strip() for item in current))
                current = []
                continue
            if current is not None:
                current.append(line)
            else:
                body.append(line)
        if current is not None:
            records.append(any(item.strip() for item in current))
    populated = bool(records) and all(records)
    return skeleton, populated, {
        "title_present": titled,
        "sections_present": sorted(level_two & set(REQUIRED_SECTIONS)),
        "sections_absent": sorted(set(REQUIRED_SECTIONS) - level_two),
        "record_headings": len(records),
        "records_with_body": sum(records),
    }


def sources_parse(project: Path) -> tuple[bool, dict[str, object]]:
    """Every delivered module is syntactically loadable source, none emptied out."""
    modules = sorted(p for p in project.rglob("*.py")
                     if "__pycache__" not in p.parts)
    broken = []
    for path in modules:
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:
            broken.append(f"{path.relative_to(project)}: {type(exc).__name__}")
    return bool(modules) and not broken, {
        "module_count": len(modules), "unparseable": broken[:10]}


def library_loads(project: Path) -> tuple[bool, dict[str, object]]:
    """The delivered tree imports as a library and resolves its own exports."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(project)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run([sys.executable, "-c", LOAD_PROBE], env=env,
                              capture_output=True, text=True, timeout=120,
                              cwd=str(project))
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return False, {"loaded": False, "detail": f"{type(exc).__name__}: {exc}"}
    return bool(payload.get("loaded")), payload


def check_delivery(project: Path, report: Path) -> dict[str, object]:
    checks: dict[str, bool] = {}
    evidence: dict[str, object] = {}

    text = None
    if not report.is_file():
        checks["report_readable"] = False
        evidence["report_readable"] = {"detail": "report path is not a file"}
    else:
        try:
            text = report.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            checks["report_readable"] = False
            evidence["report_readable"] = {"detail": f"UnicodeDecodeError: {exc.reason}"}
        else:
            checks["report_readable"] = bool(text.strip())
            evidence["report_readable"] = {"characters": len(text)}

    if text is None:
        checks["report_skeleton"] = False
        checks["defect_records_populated"] = False
        evidence["report_structure"] = {"detail": "report unavailable"}
    else:
        skeleton, populated, detail = report_structure(text)
        checks["report_skeleton"] = skeleton
        checks["defect_records_populated"] = populated
        evidence["report_structure"] = detail

    parses, parse_detail = sources_parse(project)
    checks["sources_parse"] = parses
    evidence["sources_parse"] = parse_detail

    loads, load_detail = library_loads(project)
    checks["library_loads"] = loads
    evidence["library_loads"] = load_detail

    return {
        "reward_lenient": 1.0 if all(checks.values()) else 0.0,
        "checks": checks,
        "evidence": evidence,
        "unmet": [name for name, ok in checks.items() if not ok],
    }


REWARD_FORMULAS = {
    "strict": "0.55 * (behaviour contracts, weighted by method family: async iteration 0.35, concurrent map 0.35, meter rendering 0.15, indicator lifecycle 0.15, items sharing their family weight equally) + 0.45 * (0.90 * causal records bound to a source location / 11 + 0.10 * verification handoff: requested sections, a rejected competing hypothesis, and a command tied to an outcome). Module retention is a delivery obligation checked by the lenient contract and carries no strict credit.",
    "lenient": "1 iff the repair report is present, UTF-8 decodable and non-empty, "
               "carries the requested title and the three requested sections, holds at least "
               "one defect record heading with every record heading followed by body text, "
               "every delivered module parses as Python source, and the delivered tree "
               "imports as a library with all of its own declared exports resolving; "
               "otherwise 0",
}


def main() -> int:
    submission = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace")
    try:
        project, report = locate(submission)
        contracts = check_contracts(project)
        report_check = check_report(report)
        delivery = check_delivery(project, report)
    except Exception as exc:
        print(json.dumps({
            "reward": 0.0, "reward_strict": 0.0, "reward_lenient": 0.0,
            "rewards": {"strict": 0.0, "lenient": 0.0},
            "reward_formulas": REWARD_FORMULAS,
            "error": f"{type(exc).__name__}: {exc}",
        }, indent=2))
        return 0
    results = contracts["results"]
    api_score, contract_families = contract_score(results)
    diagnosis_score = float(report_check["diagnosis_score"])
    required = (
        project / "tqdm" / "std.py",
        project / "tqdm" / "asyncio.py",
        project / "tqdm" / "_monitor.py",
        project / "tqdm" / "contrib" / "concurrent.py",
    )
    scope = all(path.is_file() for path in required)
    # Repairing the library is the substance of this task; the report documents it.
    # Keeping the delivered modules in place and giving the report its three sections
    # are delivery obligations rather than professional ability, so they are checked by
    # the lenient contract and carry no strict credit.
    row_results = report_check.get("rows") or {}
    bound_rows = (sum(1 for value in row_results.values() if value) / len(row_results)
                  if row_results else 0.0)
    handoff = float(report_check.get("handoff", {}).get("score", 0.0))
    diagnosis = 0.9 * bound_rows + 0.1 * handoff
    score = 0.55 * api_score + 0.45 * diagnosis
    strict = round(score, 4)
    lenient = float(delivery["reward_lenient"])
    detail = {
        "reward_strict": strict,
        "reward_lenient": lenient,
        "reward": strict,
        "rewards": {"strict": strict, "lenient": lenient},
        "reward_formulas": REWARD_FORMULAS,
        "delivery": delivery,
        "components": {
            "behavioral_repair": round(0.55 * api_score, 4),
            "root_cause_diagnosis": round(0.45 * diagnosis, 4),
            "contract_families": contract_families,
        },
        "contracts": contracts,
        "report": report_check,
        "scope_integrity": scope,
    }
    print(json.dumps(detail, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


TESTS = Path(__file__).resolve().parent
DEFAULT_TASK = TESTS.parent
DEFAULT_WORKSPACE = DEFAULT_TASK / "environment" / "workspace"
if (Path("/workspace") / "materials").is_dir():
    DEFAULT_WORKSPACE = Path("/workspace")
WORKSPACE = Path(os.environ.get("TASK_WORKSPACE", DEFAULT_WORKSPACE))
MAT = WORKSPACE / "materials"
OUT = WORKSPACE / "output"
TRUTH = json.loads((TESTS / "ground_truth.json").read_text(encoding="utf-8"))
HASHES = {
    "每日供需.csv": TRUTH["daily_sha256"],
    "機組發電.json": TRUTH["snapshot_sha256"],
}
PLANT_COLUMNS = {
    "大潭": "大潭 (#1-#9)(萬瓩)",
    "通霄": "通霄 (#1-#6、GT#9)(萬瓩)",
}
TRACE_FIELDS = [
    "來源日期", "來源列號", "步序", "歷史大潭_MW", "歷史通霄_MW",
    "歷史合計_MW", "壓力指數", "目標出力_MW", "機組名稱", "廠群",
    "機組狀態", "事故機組", "快照出力_MW", "裝置容量_MW", "前步出力_MW",
    "步調整上限_MW", "下界_MW", "上界_MW", "指令出力_MW", "實際出力_MW",
    "機組負載率", "步總出力_MW", "步殘差_MW", "步可達性",
]
FULL_OUTAGE_NOTES = {"檢修", "歲修", "故障", "計劃停機", "環保停機", "合約限制"}
PARTIAL_NOTES = {"部分檢修", "部分故障"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def close(left, right, tolerance=1e-5) -> bool:
    a, b = number(left), number(right)
    return a is not None and b is not None and abs(a - b) <= tolerance


def mean(checks) -> float:
    values = [float(bool(item)) for item in checks]
    return sum(values) / len(values) if values else 0.0


# --------------------------------------------------------------- carriers ---
# The instruction fixes the eight top-level JSON objects and the CSV header; the
# rubric adds that "JSON key order, trace row order, float formatting, and
# Chinese synonym choices do not affect facts or relations", and that the source
# checks "use file digests, source locations, identifiers, unit conversions, and
# time relations rather than gold wording". These helpers locate a fact by its
# value inside the object the contract names for it, instead of by Golden's own
# key spelling, nesting and container shape.

def _nodes(node):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from _nodes(value)
    elif isinstance(node, list):
        for value in node:
            if isinstance(value, (dict, list)):
                yield from _nodes(value)


def _leaves(node, key=""):
    if isinstance(node, dict):
        for name, value in node.items():
            yield from _leaves(value, str(name))
    elif isinstance(node, list):
        for value in node:
            yield from _leaves(value, key)
    else:
        yield key, node


def _text(node):
    return node if isinstance(node, str) else json.dumps(node, ensure_ascii=False)


def _num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("−", "-").replace("%", "")
        try:
            parsed = float(cleaned)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _keyhit(key, tokens):
    lowered = str(key).lower()
    return any(str(token).lower() in lowered for token in tokens)


def has_number(scope, wanted, tolerance=1e-5, keys=None):
    if wanted is None:
        return False
    for key, value in _leaves(scope):
        if keys and not _keyhit(key, keys):
            continue
        parsed = _num(value)
        if parsed is not None and abs(parsed - wanted) <= tolerance:
            return True
    return False


def has_prose(scope, keys=None, minimum=6):
    for key, value in _leaves(scope):
        if keys and not _keyhit(key, keys):
            continue
        if isinstance(value, str) and len(value.strip()) >= minimum:
            return True
    return False


# The instruction: "Use Traditional Chinese for all explanatory text, decisions,
# limitations, and status reasons in the deliverables". A derived classification
# or a decision written in Latin script or in simplified characters breaks it.
LATIN_ONLY = re.compile(r"^[A-Za-z][A-Za-z0-9 \-_/]*$")
SIMPLIFIED_ONLY = set(
    # simplified forms whose traditional counterpart differs; characters shared by both
    # scripts (考, 下, 可 ...) are deliberately not here.
    "\u6761\u51b3\u4ea7\u4e1a\u4e1a\u52a1\u8fd9\u4e3a\u5904\u89c4\u5219\u8bf4\u65f6\u95f4\u5386\u8fd0\u8f6c\u5e94\u8d44\u8baf\u5f55\u68c0\u9a8c\u8bc1\u8d23\u5355\u673a\u7ec4\u6570\u636e\u53c2\u5b9e\u9645")
LANGUAGE_KEYS = ("\u53ef\u7528\u6027", "\u6a5f\u7d44\u72c0\u614b", "\u72c0\u614b", "status",
                 "\u6c7a\u7b56", "\u7d50\u8ad6", "\u5224\u5b9a", "\u5206\u985e", "\u7d50\u679c",
                 "verdict", "\u53ef\u8abf\u5ea6")


def language_violations(report):
    hits = []
    for scope in ("unit_register", "decision", "scenario", "metrics"):
        node = report.get(scope)
        if node is None:
            continue
        for key, value in _leaves(node):
            if not isinstance(value, str) or not _keyhit(key, LANGUAGE_KEYS):
                continue
            text = value.strip()
            if not text:
                continue
            if LATIN_ONLY.match(text) or any(ch in SIMPLIFIED_ONLY for ch in text):
                hits.append("%s:%s=%s" % (scope, key, text[:40]))
    return hits


# --------------------------------------------------------------- decision ---
# The minutes require "a conditional operational decision". The decision is not a
# positive item; it is charged under D01, the output-contract coefficient: an object
# that is present in name but does not carry a conditional decision consistent with
# the trace it is built on does not satisfy the contract the minutes fix.
#
# Every feasibility word below also occurs inside its own
# negation ("可行" inside "不可行", "可達" inside "不可達"), so the negative forms
# are listed explicitly and vetoed first, and only verdict-bearing keys are read -
# the surrounding caveat prose of a correct decision is full of "不足", "無法".
DECISION_VERDICT_KEYS = ("狀態", "status", "結論", "決策", "判定", "結果", "判斷",
                         "verdict", "conclusion")
INFEASIBLE_MARKERS = ("不可行", "不可達", "不通過", "未通過", "不成立", "不足", "無法",
                      "未全數", "不建議", "不可接受", "缺口", "未達", "不宜",
                      "需配套", "待配套", "不滿足", "未能")
FEASIBLE_MARKERS = ("可行", "可達", "通過", "成立", "充裕", "可接受", "支持", "達成")
UNCONDITIONAL_MARKERS = ("無條件", "無任何條件", "無適用邊界", "已涵蓋全系統",
                         "全系統已通過", "不受任何限制", "可直接據此宣告", "無需條件",
                         "無須條件", "無其他限制")
CONDITIONAL_MARKERS = ("條件", "前提", "須", "不得", "僅", "限於", "假設", "尚待", "覆核")


# A sentence that disclaims an overclaim ("因此不支持無條件宣稱本範圍具備 N-1 覆蓋")
# contains the overclaim's own wording, so a marker only counts when its own clause
# does not negate it.
NEGATORS = ("不", "未", "非", "勿", "毋", "否", "無法", "無從", "難以")
CLAUSE_BREAKS = "，。；、,;.!?！？\n「」\"'"


def claims_unconditional(blob: str) -> bool:
    for mark in UNCONDITIONAL_MARKERS:
        start = 0
        while True:
            index = blob.find(mark, start)
            if index < 0:
                break
            start = index + 1
            window = blob[max(0, index - 12):index]
            for char in reversed(window):
                if char in CLAUSE_BREAKS:
                    window = window[window.rfind(char) + 1:]
                    break
            if any(negator in window for negator in NEGATORS):
                continue
            return True
    return False


def claimed_feasible(report):
    """What the decision object declares: True, False, or None when it declares nothing."""
    node = report.get("decision")
    if node is None:
        return None
    values = [value.strip() for key, value in _leaves(node)
              if isinstance(value, str) and _keyhit(key, DECISION_VERDICT_KEYS)
              and len(value.strip()) >= 2]
    if any(any(mark in text for mark in INFEASIBLE_MARKERS) for text in values):
        return False
    if any(any(mark in text for mark in FEASIBLE_MARKERS) for text in values):
        return True
    return None


def decision_defects(report, steps_present, feasible_steps, utilizations):
    """The two ways the decision object fails the contract, as separate damage keys."""
    reconciles = (steps_present == 14 and feasible_steps == 14
                  and (not utilizations or max(utilizations) <= 1.0 + 1e-7))
    claimed = claimed_feasible(report)
    node = report.get("decision")
    blob = _text(node) if node is not None else ""
    unconditional = (claims_unconditional(blob)
                     or not any(mark in blob for mark in CONDITIONAL_MARKERS))
    return {
        "decision_claim": claimed,
        "trace_supports_feasible": reconciles,
        "not_reconciled": claimed is None or claimed != reconciles,
        "unconditional": bool(unconditional),
    }


# --------------------------------------------------------- trace coverage ---
# The minutes require "one row for every in-scope dispatchable unit at every one of
# the fourteen source dates". Missing required content is banded: one instance, plus
# one more for each further 15% of the required rows that is absent, capped at three,
# under the D01 coefficient.
COVERAGE_BAND = 0.15
COVERAGE_CAP = 3


# A row whose dispatched output falls outside the bounds that same row declares is an
# internal contradiction, and a systematic one is not the same failure as a slip. It is
# banded: two such rows are tolerated as a slip and cost only the P08 checks they lose;
# beyond that it opens one instance plus one more for each further quarter of the trace
# affected, capped at three, under D01's coefficient.
BOUND_SLIP_TOLERANCE = 2
BOUND_BAND = 0.25
BOUND_CAP = 3


def bound_violation_instances(trace):
    affected = 0
    for row in trace:
        low, high = number(row.get("下界_MW")), number(row.get("上界_MW"))
        output = number(row.get("實際出力_MW"))
        if low is None or high is None or output is None:
            continue
        if not (low - 2e-5 <= output <= high + 2e-5):
            affected += 1
    if affected <= BOUND_SLIP_TOLERANCE or not trace:
        return 0, affected
    share = (affected - BOUND_SLIP_TOLERANCE) / len(trace)
    return min(BOUND_CAP, 1 + int(share // BOUND_BAND)), affected


def coverage_instances(steps, expected_units):
    present = {(step, str(row.get("機組名稱"))) for step, group in steps.items() for row in group}
    required = {(step, name) for step in range(1, 15) for name in expected_units}
    missing = required - present
    if not missing:
        return 0, 0.0
    share = len(missing) / len(required)
    return min(COVERAGE_CAP, 1 + int(share // COVERAGE_BAND)), share


def has_list(scope, wanted, tolerance=1e-5):
    """a numeric list equal to `wanted`, in order, anywhere in the scope."""
    for node in _nodes(scope):
        if not isinstance(node, list) or len(node) != len(wanted):
            continue
        parsed = []
        for item in node:
            if isinstance(item,dict):
                values=[value for key,value in item.items() if re.search(r"(絕對|绝对|absolute).*?(變化|变化|change)|absolute_change",str(key),re.I)]
                dates=[value for key,value in item.items() if re.search(r"日期|date",str(key),re.I)]
                parsed.append(_num(values[0]) if len(values)==1 and dates else None)
            else:parsed.append(_num(item))
        if all(item is not None for item in parsed) and all(
                abs(a - b) <= tolerance for a, b in zip(parsed, wanted)):
            return True
    return False


def _kv_nodes(node, key=""):
    yield key, node
    if isinstance(node, dict):
        for name, value in node.items():
            if isinstance(value, (dict, list)):
                yield from _kv_nodes(value, str(name))
    elif isinstance(node, list):
        for value in node:
            if isinstance(value, (dict, list)):
                yield from _kv_nodes(value, key)


def owned(scope, mine, other):
    """the nodes of `scope` that their own key or subtree names `mine` and not `other`."""
    hits = []
    for key, node in _kv_nodes(scope):
        if not isinstance(node, (dict, list)):
            continue
        blob = str(key) + " " + _text(node)
        if mine in blob and other not in blob:
            hits.append(node)
    if not hits and mine in _text(scope) and other not in _text(scope):
        hits = [scope]
    return hits


def shared_derivation(scope,mine,other):
    for _,node in _kv_nodes(scope):
        if not isinstance(node,dict):continue
        if mine not in _text(node) or other not in _text(node):continue
        for key,value in node.items():
            if str(key) not in ("推導","推导","derivation","共同推導","共同推导"):continue
            if not isinstance(value,str) or len(value.strip())<8:continue
            names={p for p in PLANT_COLUMNS if p in value}
            if not names or names==set(PLANT_COLUMNS):return True
    return False


def outage_status(row):
    status=str(row.get("機組狀態","")).strip()
    return status in ("事故退出","事故停機","事故停机","故障停機","故障停机")


def any_owned(hits, test):
    return any(test(node) for node in hits)


LOWER_TOKENS = ("lower", "low", "min", "下限", "下緣", "下界", "底")
UPPER_TOKENS = ("upper", "high", "max", "上限", "上緣", "上界", "頂")
FRACTION_TOKENS = ("fraction", "比例", "分率", "比", "率", "係數", "envelope", "包絡")

# ------------------------------------------------- declared modelling choices ---
# The current operating band and the per-plant adjustment fraction are scenario
# assumptions the minutes leave to the report. The minutes fix the three deliverables,
# the eight top-level objects, the CSV header, the facts to bind and disclose, and the
# conditional decision; they state no admissible range for either quantity. So neither is
# judged against a range: the scorer reads what the report declares and then checks the
# deliverable that was built on it - the per-step targets against the declared band, the
# per-step limits and bounds against the declared fraction. The only bound applied here is
# definitional rather than a screening rule: both are fractions - the band of the pre-event
# dispatchable output, the adjustment fraction of installed capacity - so they live in
# [0, 1], which is also what the report has to mean for its own arithmetic to be readable.
BAND_FLOOR, BAND_CEILING = 0.0, 1.0


def best_declared(candidates, agreement):
    """The declared candidate the deliverable's own trace is built on.

    `agreement` returns the share of the trace a candidate reconciles. A report that
    carries one admissible declaration is read as declaring it; a report that carries
    several - a band beside an unrelated pair of fractions, an adjustment fraction beside
    the band's own lower and upper fractions - is read through the one its trace agrees
    with, since that is the one it modelled with. Ties keep the first declaration in
    document order, and a report whose trace agrees with none of its declarations still
    declares the first one and is then charged on what its trace actually carries.
    """
    best, best_share = None, -1.0
    for value in candidates:
        share = agreement(value)
        if share > best_share:
            best, best_share = value, share
    return best


def band_candidates(report):
    """Every current operating band the report declares, in document order."""
    found = []
    for scope in (report.get("scenario"), report.get("model")):
        if scope is None:
            continue
        for node in _nodes(scope):
            if not isinstance(node, dict):
                continue
            for _, value in node.items():
                if isinstance(value, list) and len(value) == 2:
                    low, high = _num(value[0]), _num(value[1])
                    if low is not None and high is not None and BAND_FLOOR <= low < high <= BAND_CEILING:
                        found.append((low, high))
            lows = [_num(v) for k, v in node.items() if _keyhit(k, LOWER_TOKENS)]
            highs = [_num(v) for k, v in node.items() if _keyhit(k, UPPER_TOKENS)]
            for low in lows:
                for high in highs:
                    if low is not None and high is not None and BAND_FLOOR <= low < high <= BAND_CEILING:
                        found.append((low, high))
    return found


def declared_band(report, agreement=None):
    """The current operating band the report declares."""
    return best_declared(band_candidates(report), agreement or (lambda _: 0.0))


LOST_TOKENS = ("lost", "outage", "trip", "事故", "損失", "退出", "跳脫", "失去")


def declared_lost(report, online_by_name):
    """The single online unit the report declares lost, wherever it states it.

    Only a key that names the event carries the declaration: an untagged mention
    of a unit name is a list of what the snapshot shows, not a contingency."""
    for scope in ("scenario", "model", "metrics", "decision", "unit_register"):
        node = report.get(scope)
        if node is None:
            continue
        for key, value in _leaves(node):
            if not _keyhit(key, LOST_TOKENS):
                continue
            if isinstance(value, str) and value.strip() in online_by_name:
                return value.strip()
    return None


def read_sources():
    daily = []
    with (MAT / "每日供需.csv").open("r", encoding="utf-8-sig", newline="") as stream:
        for line, raw in enumerate(csv.DictReader(stream), 2):
            daily.append({"line": line, "raw": raw, "date": datetime.strptime(raw["日期"], "%Y%m%d")})
    daily.sort(key=lambda item: item["date"])
    selected = daily[-14:]

    snapshot = json.loads((MAT / "機組發電.json").read_text(encoding="utf-8-sig"))
    register = []
    for index, raw in enumerate(snapshot["aaData"]):
        name = str(raw.get("機組名稱", ""))
        plant = next((p for p in PLANT_COLUMNS if name.startswith(p)), None)
        if raw.get("機組類型") != "燃氣" or plant is None:
            continue
        capacity = number(raw.get("裝置容量(MW)"))
        power = number(raw.get("淨發電量(MW)"))
        note = str(raw.get("備註", "")).strip()
        if capacity is None:
            state, ceiling = "不可調度", None
        elif note in FULL_OUTAGE_NOTES:
            state, ceiling = "不可調度", 0.0
        elif note in PARTIAL_NOTES:
            state, ceiling = "降額", max(power or 0.0, 0.0)
        elif note:
            state, ceiling = "不可調度", 0.0
        else:
            state, ceiling = "可調度", capacity
        register.append({
            "json_index": index, "機組名稱": name, "機組類型": "燃氣", "廠群": plant,
            "裝置容量_MW": capacity, "快照淨發電量_MW": power, "備註": note,
            "可用性": state, "可用上限_MW": ceiling,
        })
    dispatchable = [row for row in register if row["可用性"] == "可調度"]
    canonical_lost = sorted(
        [row for row in dispatchable if (row["快照淨發電量_MW"] or 0) > 0],
        key=lambda row: (-row["快照淨發電量_MW"], row["機組名稱"]),
    )[0]
    pre_event = sum(row["快照淨發電量_MW"] or 0.0 for row in dispatchable)
    history = []
    for item in selected:
        plants = {p: float(item["raw"][column]) * 10 for p, column in PLANT_COLUMNS.items()}
        history.append({
            "date": item["date"].strftime("%Y%m%d"), "line": item["line"],
            "plants": plants, "combined": sum(plants.values()),
        })
    values = [row["combined"] for row in history]
    for row in history:
        row["stress"] = (row["combined"] - min(values)) / (max(values) - min(values))
    fractions = {}
    changes = {}
    for plant in PLANT_COLUMNS:
        series = [row["plants"][plant] for row in history]
        changes[plant] = [abs(b - a) for a, b in zip(series, series[1:])]
        cap = sum(row["裝置容量_MW"] for row in dispatchable if row["廠群"] == plant)
        ratios = sorted(value / cap for value in changes[plant])
        fractions[plant] = ratios[math.ceil(0.9 * len(ratios)) - 1]
    return {
        "daily": daily, "selected": selected, "snapshot": snapshot, "register": register,
        "dispatchable": dispatchable, "canonical_lost": canonical_lost, "pre_event": pre_event,
        "history": history, "fractions": fractions, "changes": changes,
    }


def load_trace(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        rows = list(reader)
    return header, rows


def by_step(rows):
    result = {}
    for row in rows:
        step_num = number(row.get("步序"))
        if step_num is None or int(step_num) != step_num:
            continue
        result.setdefault(int(step_num), []).append(row)
    return result


def canonical_cell(value):
    """RUBRIC.md: "float formatting ... do not affect facts or relations"."""
    text = str(value).strip()
    parsed = number(text)
    if parsed is None:
        return text
    # `+ 0.0` folds -0.0 onto 0.0, and rounding to 1e-6 is an order of magnitude
    # tighter than any tolerance this scorer applies to the same quantities. It is
    # what keeps the reproduction check from depending on the CPython version:
    # 3.12's compensated sum prints -0.0 for a step residual where 3.10 prints 0.0.
    return round(parsed + 0.0, 6)


def canonical_report(node):
    """The same rounding as `canonical_cell`, applied to a parsed JSON report."""
    if isinstance(node, dict):
        return {key: canonical_report(value) for key, value in node.items()}
    if isinstance(node, list):
        return [canonical_report(value) for value in node]
    if isinstance(node, bool) or node is None or isinstance(node, str):
        return node
    if isinstance(node, (int, float)):
        return round(float(node) + 0.0, 6)
    return node


def canonical_rows(rows):
    return sorted(
        [{key: canonical_cell(row.get(key, "")) for key in TRACE_FIELDS} for row in rows],
        key=lambda row: (int(float(row["步序"])), str(row["機組名稱"])),
    )


def clean_reproduction(report, trace, script):
    try:
        with tempfile.TemporaryDirectory(prefix="dispatch-reproduce-") as temporary:
            root = Path(temporary)
            shutil.copytree(MAT, root / "materials")
            (root / "output").mkdir()
            shutil.copyfile(script, root / "output" / "dispatch_model.py")
            proc = subprocess.run(
                [sys.executable, str(root / "output" / "dispatch_model.py")],
                cwd=root, capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                return False, False, f"clean reproduction failed: {(proc.stderr or proc.stdout)[-300:]}"
            rebuilt_report = json.loads((root / "output" / "dispatch_review.json").read_text(encoding="utf-8"))
            _, rebuilt_trace = load_trace(root / "output" / "dispatch_trace.csv")
            exact = (canonical_report(rebuilt_report) == canonical_report(report)
                     and canonical_rows(rebuilt_trace) == canonical_rows(trace))

            daily_path = root / "materials" / "每日供需.csv"
            with daily_path.open("r", encoding="utf-8-sig", newline="") as stream:
                source_rows = list(csv.DictReader(stream))
                fields = list(source_rows[0])
            original = float(source_rows[-1][PLANT_COLUMNS["大潭"]])
            source_rows[-1][PLANT_COLUMNS["大潭"]] = str(original + 1.0)
            with daily_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(source_rows)
            proc2 = subprocess.run(
                [sys.executable, str(root / "output" / "dispatch_model.py")],
                cwd=root, capture_output=True, text=True, timeout=60,
            )
            if proc2.returncode != 0:
                return exact, False, "source sensitivity run failed"
            _, changed_trace = load_trace(root / "output" / "dispatch_trace.csv")
            last_step = [row for row in changed_trace if int(float(row.get("步序", -1))) == 14]
            sensitive = bool(last_step) and all(close(row.get("歷史大潭_MW"), (original + 1.0) * 10) for row in last_step)
            return exact, sensitive, "ok" if exact and sensitive else "regeneration or source sensitivity mismatch"
    except Exception as exc:
        return False, False, f"reproduction exception: {exc}"


# An affirmative claim that the two records are contemporaneous ("兩者為同時量測"). The minutes say the
# historic records are "not a claim that the two files are contemporaneous", so such a claim is a
# fabrication. A match counts only when its own clause does not negate it: "兩者不是同時量測",
# "並非同時記錄" and "不宣稱兩份檔案為同時量測" are not claims.
SAME_TIME_CLAIM = re.compile(r"(?<!不是)(?<!並非)(?<!不)(?<!非)(?:為|是|屬|係)?同時(?:量測|記錄|取得)")
SEPARATION_TOKENS = ("45", "不同時", "非同時", "跨期")


def claims_same_time(text: str) -> bool:
    for match in SAME_TIME_CLAIM.finditer(text):
        window = text[:match.start()]
        for index in range(len(window) - 1, -1, -1):
            if window[index] in CLAUSE_BREAKS:
                window = window[index + 1:]
                break
        if not any(negator in window for negator in NEGATORS):
            return True
    return False


def contemporaneity_claims(report):
    hits = []
    for scope in ("scenario", "decision", "limitations"):
        node = report.get(scope)
        if node is None:
            continue
        for _, value in _leaves(node):
            if isinstance(value, str) and claims_same_time(value):
                hits.append("%s:%s" % (scope, value[:60]))
    return hits


def limitation_signals(report):
    text = _text(report.get("limitations")) if report.get("limitations") is not None else ""
    return mean([
        (any(token in text for token in SEPARATION_TOKENS) and not claims_same_time(text)),
        ("每日" in text or "日尺度" in text or "次小時" in text),
        ("彙總" in text or "單機" in text),
        ("輸電" in text or "燃料" in text or "穩定" in text),
    ])


def score():
    intact = all((MAT / name).is_file() and digest(MAT / name) == value for name, value in HASHES.items())
    required = [OUT / "dispatch_review.json", OUT / "dispatch_trace.csv", OUT / "dispatch_model.py"]
    present = all(path.is_file() and path.stat().st_size > 0 for path in required)
    if not intact or not present:
        return {
            "gate": False,
            "failure": "material integrity failed" if not intact else "required output missing",
            "source_integrity": float(intact), "required_outputs": float(present),
        }
    try:
        report = json.loads(required[0].read_text(encoding="utf-8"))
        header, trace = load_trace(required[1])
        expected = read_sources()
    except Exception as exc:
        return {"gate": False, "failure": f"output parse failed: {exc}"}

    top_keys = {"source_binding", "unit_register", "scenario", "model", "metrics", "decision", "evidence", "limitations"}
    format_ok = top_keys.issubset(report) and header == TRACE_FIELDS
    steps = by_step(trace)
    clean_ok, sensitive_ok, reproduce_message = clean_reproduction(report, trace, required[2])

    online_by_name = {
        row["機組名稱"]: row for row in expected["dispatchable"]
        if (row["快照淨發電量_MW"] or 0.0) > 0
    }
    declared_lost_name = declared_lost(report, online_by_name)
    lost = online_by_name.get(declared_lost_name, expected["canonical_lost"])

    envelope_scope = {key: report.get(key) for key in ("scenario", "model")}
    envelope_checks = []
    accepted_fractions = {}
    plants = list(PLANT_COLUMNS)
    for plant in plants:
        other = [name for name in plants if name != plant][0]
        nodes_here = owned(envelope_scope, plant, other)
        wanted_cap = sum(row["裝置容量_MW"] for row in expected["dispatchable"] if row["廠群"] == plant)
        # The adjustment fraction is a declared assumption, not an answer the minutes fix,
        # so it is read from the plant's own node and the trace is then checked against it.
        candidates = []
        for node in nodes_here:
            for key, value in _leaves(node):
                if not _keyhit(key, FRACTION_TOKENS):
                    continue
                parsed = _num(value)
                if parsed is not None and 0.0 < parsed <= 1.0 and parsed not in candidates:
                    candidates.append(parsed)
        unit_caps = {row["機組名稱"]: row["裝置容量_MW"] for row in expected["dispatchable"]
                     if row["廠群"] == plant and row["機組名稱"] != lost["機組名稱"]}
        limit_rows = [row for row in trace if str(row.get("機組名稱")) in unit_caps]

        def limit_agreement(value, caps=unit_caps, rows=limit_rows):
            """The share of this plant's trace rows whose step limit is that fraction of capacity."""
            return mean([close(row.get("步調整上限_MW"), caps[str(row.get("機組名稱"))] * value, 2e-5)
                         for row in rows])

        declared_fraction = best_declared(candidates, limit_agreement)
        fraction_ok = declared_fraction is not None
        accepted_fractions[plant] = declared_fraction if fraction_ok else expected["fractions"][plant]
        envelope_checks.extend([
            any_owned(nodes_here, lambda n: has_number(n, wanted_cap)),
            fraction_ok,
            any_owned(nodes_here, lambda n: has_list(n, expected["changes"][plant])),
            any_owned(nodes_here, lambda n: has_prose(
                n, keys=("rule", "規則", "方法", "定義", "說明", "method", "推導"), minimum=8)) or shared_derivation(envelope_scope,plant,other),
        ])

    def band_agreement(candidate):
        """The share of the fourteen steps whose targets recompute from that band."""
        low_band, high_band = candidate
        hits = []
        for index, wanted in enumerate(expected["history"], 1):
            group = steps.get(index, [])
            if not group:
                continue
            target = expected["pre_event"] * (low_band + (high_band - low_band) * wanted["stress"])
            hits.append(all(close(row.get("目標出力_MW"), target, 2e-5) for row in group))
        return mean(hits)

    band = declared_band(report, band_agreement)
    band_ok = band is not None
    low_band, high_band = band if band_ok else (0.0, 0.0)
    stress_checks = [band_ok]
    for index, wanted in enumerate(expected["history"], 1):
        group = steps.get(index, [])
        target = expected["pre_event"] * (low_band + (high_band - low_band) * wanted["stress"])
        stress_checks.extend([
            bool(group) and all(close(row.get("壓力指數"), wanted["stress"], 2e-7) for row in group),
            bool(group) and all(close(row.get("目標出力_MW"), target, 2e-5) for row in group),
        ])

    expected_units = {row["機組名稱"]: row for row in expected["dispatchable"]}
    constraint_checks = []
    previous_expected = {
        name: (0.0 if name == lost["機組名稱"] else unit["快照淨發電量_MW"] or 0.0)
        for name, unit in expected_units.items()
    }
    for step in range(1, 15):
        group = steps.get(step, [])
        unique = {row.get("機組名稱"): row for row in group if row.get("機組名稱") in expected_units}
        if len(unique) != len(expected_units):
            constraint_checks.extend([False] * (len(expected_units) * 12))
            continue
        for name, unit in expected_units.items():
            row = unique[name]
            limit = 0.0 if name == lost["機組名稱"] else unit["裝置容量_MW"] * accepted_fractions[unit["廠群"]]
            low = high = 0.0 if name == lost["機組名稱"] else None
            if name != lost["機組名稱"]:
                low = max(0.0, previous_expected[name] - limit)
                high = min(unit["裝置容量_MW"], previous_expected[name] + limit)
            output = number(row.get("實際出力_MW"))
            source_capacity=unit["裝置容量_MW"]
            row_total=sum(number(item.get("實際出力_MW")) or 0.0 for item in group)
            row_target=number(row.get("目標出力_MW"))
            constraint_checks.extend([
                close(row.get("裝置容量_MW"), unit["裝置容量_MW"]),
                close(row.get("快照出力_MW"), unit["快照淨發電量_MW"] or 0.0),
                close(row.get("步調整上限_MW"), limit, 2e-5),
                close(row.get("下界_MW"), low, 2e-5), close(row.get("上界_MW"), high, 2e-5),
                output is not None and low - 2e-5 <= output <= high + 2e-5,
                close(row.get("指令出力_MW"), output, 2e-5),
                (row.get("事故機組") == "是") == (name == lost["機組名稱"]),
                outage_status(row) == (name == lost["機組名稱"]),
                source_capacity>0 and close(row.get("機組負載率"),(output or 0.0)/source_capacity,2e-7),
                close(row.get("步總出力_MW"),row_total,2e-5),
                row_target is not None and close(row.get("步殘差_MW"),row_total-row_target,2e-5)
                and (str(row.get("步可達性") or "").strip() in ("可達","達成") if abs(row_total-row_target)<=1e-4 else str(row.get("步可達性") or "").strip() in ("不可達","未達")),
            ])
        previous_expected = {name: number(unique[name].get("實際出力_MW")) or 0.0 for name in expected_units}

    metrics = report.get("metrics")
    if metrics is None:
        metrics = {}
    step_rows = [next(iter(steps[s]), {}) for s in sorted(steps) if steps[s]]
    recomputed = []
    for step in sorted(steps):
        group = steps[step]
        outputs = [number(row.get("實際出力_MW")) for row in group]
        targets = [number(row.get("目標出力_MW")) for row in group]
        if any(value is None for value in outputs) or not targets or any(value is None for value in targets):
            continue
        total = sum(outputs)
        target = targets[0]
        recomputed.append({"total": total, "residual": total-target,
                           "target_consistent": all(close(value,target,2e-5) for value in targets)})
    residuals = [abs(row["residual"]) for row in recomputed]
    utilizations = [
        (number(row.get("實際出力_MW")) or 0.0) / expected_units[row.get("機組名稱")]["裝置容量_MW"]
        for row in trace if row.get("機組名稱") in expected_units and expected_units[row.get("機組名稱")]["裝置容量_MW"]
    ]
    feasible = sum(row["target_consistent"] and abs(row["residual"]) <= 1e-4 for row in recomputed)
    final_total = recomputed[-1]["total"] if recomputed else None
    metric_checks = [
        has_number(metrics, 14.0, keys=("steps", "步數", "步序", "情境步")),
        has_number(metrics, float(len(expected_units)),
                   keys=("機組數", "units", "台數", "unit_count", "per_step")),
        has_number(metrics, float(len(trace)), keys=("列數", "rows", "筆數", "row_count")),
        has_number(metrics, float(feasible), keys=("可達", "feasible")),
        bool(residuals) and has_number(metrics, max(residuals), 3e-4, keys=("殘差", "residual")),
        bool(utilizations) and has_number(metrics, max(utilizations), 3e-6,
                                          keys=("負載率", "利用率", "utilization", "utilisation", "load_factor")),
        final_total is not None and has_number(
            metrics, final_total, 3e-4,
            keys=("總出力", "total_output", "final", "末步", "最終", "最末", "合計")),
    ]
    evidence_text = _text(report.get("evidence")) if report.get("evidence") is not None else ""
    decision_checks = [
        "每日供需.csv" in evidence_text, "機組發電.json" in evidence_text,
        "dispatch_trace.csv" in evidence_text, "dispatch_model.py" in evidence_text,
        limitation_signals(report) >= 0.999,
        clean_ok, sensitive_ok,
    ]

    # The register the snapshot fixes is the dispatch set. The per-step checks filter
    # the trace down to the expected units, so a unit outside that set (e.g. 大潭CC#1,
    # 備註 檢修) is checked here: deriving a nonzero output for a unit the source record
    # takes out of service is a source-fidelity failure, charged under D03's coefficient.
    dispatched_excluded = sorted({
        str(row.get("機組名稱")) for row in trace
        if str(row.get("機組名稱")) not in expected_units
        and (number(row.get("實際出力_MW")) or 0.0) != 0.0
    })

    # The minutes: "bind the two record dates". The dates in `source_binding`, reduced to digits, must
    # carry the first and last selected daily record and the snapshot date.
    binding_digits = re.sub(r"\D", "", _text(report.get("source_binding", "")))
    snapshot_date = re.sub(r"\D", "", str(expected["snapshot"].get("DateTime", "")))[:8]
    binding_dates = [expected["history"][0]["date"], expected["history"][-1]["date"], snapshot_date]
    binding_ok = bool(snapshot_date) and all(date in binding_digits for date in binding_dates)

    # The minutes: "classify every in-scope snapshot unit". Every dispatchable unit carries a
    # classification in `unit_register`, and every out-of-service in-scope unit is on the register
    # and classified as not dispatchable.
    names_in_scope = {r["機組名稱"] for r in expected["register"]}
    register_rows = {}
    for node in _nodes(report.get("unit_register")):
        if isinstance(node, dict):
            for value in node.values():
                if isinstance(value, str) and value.strip() in names_in_scope:
                    register_rows.setdefault(value.strip(), []).append(node)
    def classification(node):
        return " ".join(str(v) for k, v in node.items()
                        if isinstance(v, str) and _keyhit(k, LANGUAGE_KEYS + ("可用", "availability", "class")))
    units_ok = True
    registered_dispatchability = {}
    for row in expected["register"]:
        labels = [classification(node) for node in register_rows.get(row["機組名稱"], ())]
        if not any(label.strip() for label in labels):
            units_ok = False
            continue
        available = any(mark in label for label in labels for mark in ("可調度", "可用", "dispatchable", "available"))
        unavailable = any(mark in label for label in labels for mark in
                          ("不可調度", "不可用", "停機", "檢修", "歲修", "故障", "排除", "不納入",
                           "unavailable", "non-dispatchable", "outage"))
        if row["可用性"] == "可調度" and (not available or unavailable):
            units_ok = False
        if row["可用性"] != "可調度" and not unavailable:
            units_ok = False
        registered_dispatchability[row["機組名稱"]] = row["可用性"] == "可調度"

    # A register is a source-of-truth declaration, not just a non-empty label.
    # Reject the common contradiction where an outage/non-dispatchable unit is
    # nevertheless assigned positive output in the trace.
    for row in trace:
        name = str(row.get("機組名稱"))
        if name in registered_dispatchability and not registered_dispatchability[name]:
            if (number(row.get("實際出力_MW")) or 0.0) > 1e-9:
                units_ok = False

    # The minutes: "a conditional operational decision" whose basis names at least one scoped caveat.
    decision_blob = _text(report.get("decision")) if report.get("decision") is not None else ""
    caveat_families = [
        any(t in decision_blob for t in ("跨期", "不同時", "非同時", "45")),
        any(t in decision_blob for t in ("日尺度", "每日", "次小時")),
        any(t in decision_blob for t in ("彙總", "單機")),
        any(t in decision_blob for t in ("輸電", "燃料", "穩定", "備轉")),
    ]
    conditional_ok = (bool(re.search("條件式|有條件|附條件|條件下|條件性|conditional", decision_blob, re.I))
                      and not claims_unconditional(decision_blob) and sum(caveat_families) >= 1)

    contemporaneity = contemporaneity_claims(report)
    coverage_count, coverage_share = coverage_instances(steps, expected_units)
    bound_count, bound_affected = bound_violation_instances(trace)
    decision = decision_defects(report, len(step_rows), feasible, utilizations)

    items = {
        # The envelope facts belong to the same derivation as the band and the targets: the minutes
        # require every model assumption to be disclosed, and the rubric binds an envelope fact to
        # the `scenario`/`model` node that owns that plant. They are settled here rather than
        # discarded, so a deliverable that documents no adjustment envelope is charged for it.
        "P06": mean(stress_checks + envelope_checks),
        "P08": mean(constraint_checks),
        "P12": mean(metric_checks),
        "P15": mean(decision_checks[4:5]),
    }
    language = language_violations(report)
    items["P16"] = float(bool(clean_ok) and bool(sensitive_ok))
    items["P17"] = float(conditional_ok)
    items["P18"] = float(not language)
    deductions = {
        "D01": not format_ok,
        "D02": not clean_ok,
        "D03": bool(clean_ok) and not sensitive_ok,
        "D04": bool(language),
        "D01_coverage_1": coverage_count >= 1,
        "D01_coverage_2": coverage_count >= 2,
        "D01_coverage_3": coverage_count >= 3,
        "D01_decision_not_reconciled": decision["not_reconciled"],
        "D01_decision_unconditional": decision["unconditional"],
        "D03_excluded_dispatched": bool(dispatched_excluded),
        "D03_contemporaneity_claim": bool(contemporaneity),
        "D05": not binding_ok,
        "D06": not units_ok,
        "D01_bounds_1": bound_count >= 1,
        "D01_bounds_2": bound_count >= 2,
        "D01_bounds_3": bound_count >= 3,
    }
    detail = {
        "gate": True,
        "items": {key: round(value, 9) for key, value in items.items()},
        "envelope_disclosure": {
            plant: [bool(value) for value in envelope_checks[index * 4:index * 4 + 4]]
            for index, plant in enumerate(plants)
        },
        # The two declared modelling choices the rest of the settlement is measured against,
        # so an audit can see which declaration the trace was read through.
        "declared_band": list(band) if band_ok else None,
        "accepted_fractions": accepted_fractions,
        "deductions": deductions,
        "language_violations": language,
        "format_contract": format_ok,
        "clean_reproduction": clean_ok,
        "source_sensitivity": sensitive_ok,
        "reproduction_message": reproduce_message,
        "trace_coverage_missing_share": round(coverage_share, 6),
        "decision_reconciliation": decision,
        "dispatched_excluded_units": dispatched_excluded,
        "bound_violation_rows": bound_affected,
        "contemporaneity_claims": contemporaneity,
        "binding_dates": {"required": binding_dates, "bound": binding_ok},
        "unit_register_complete": units_ok,
        "decision_conditional": conditional_ok,
    }
    return detail


if __name__ == "__main__":
    detail = score()
    log_dir = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {"detail": detail}
    (log_dir / "reward_detail.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

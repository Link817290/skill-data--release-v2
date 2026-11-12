#!/usr/bin/env python3
"""Residential egress plan repair validator (pd-ledger-v1).

Usage: validator.py <path>  (the output directory passed by test.sh, a task
workspace or Golden directory, or one of the eight deliverables in it).

The strict score is settled in the standard form

  final = positive_earned * retention
  positive_earned = sum(weight[P] * completion[P])      (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

Each positive item P is one pass/fail check of one of the four dimensions - inspection judgment, geometry
repair, evidence closure, artifact integrity - as listed in CHECKS below; completion is the independent check (0/1). A conclusion error
reduces its own judgment check without erasing independent geometry/evidence/integrity credit.
D01 is the locked-source integrity gate.  D02, D05, D08, D09 and D11 are affirmative errors charged as damage
instances.  A missing or unparsable deliverable, or an unreadable source drawing, returns a ledger with every
completion 0.

The lenient score is binary and is not a cut on the weighted total: it asks only whether this handoff's must-do
items are all met.  See LENIENT_REQUIRED_ITEMS below - it reads the strict scorer's own per-item results and
recomputes nothing.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

import dxfreader


# ---------------------------------------------------------------------------
# The lenient lens.
#
# Lenient asks one question: are this handoff's must-do items all met?  It is binary, it is never a
# threshold on the weighted total (which volume can buy), and it re-parses nothing - every term below
# is a per-item result the strict scorer already settled.
#
# Why these five.  The instruction's "Issued package" paragraph states when the package is ready for
# coordination, and its "Commission" paragraph states two prohibitions.  A handoff missing any one of
# these cannot go to permit coordination at all:
#   P01  the F-HALL-WIDTH finding: the route clear width is recorded as failing, with its observed
#        measurement, the requirement it is compared against, a disposition that actually calls for
#        the route to be widened, and evidence naming both supplied files.  This is the finding the
#        whole handoff exists for, and the instruction spells out the fields it must carry.
#   P27  "a local plan-view repair": the closed boundary drawn in the repaired DXF actually reaches
#        the code clear width off the retained face.  A repair that does not reach it has not
#        repaired anything.
#   P23  "a memo whose dimensions and dispositions agree with the JSON records and the readable DXF":
#        the drawn boundary and the repaired room polygon are the same rectangle.  A drawing and a
#        record that disagree cannot support one release decision, which is the stated purpose.
#   D01  "keep both source files unchanged" - an explicit prohibition; a review of an altered permit
#        drawing is not a review of the submitted drawing.
#   D08  "confine design changes to the first-floor HALL egress geometry and its immediately affected
#        door operation" - an explicit prohibition; redesigning outside the HALL is outside this issue.
# Deliberately NOT here: JSON key names and nesting, memo wording, layer naming style, and the
# inventory/unit bookkeeping items - real requirements, but not what makes the package unusable.
LENIENT_REQUIRED_ITEMS = ("P01", "P23", "P27", "door_core", "swing_core", "D01", "D08")

# Each required positive item, mapped to its own recorded check in result["details"].
_LENIENT_POSITIVE_DETAIL = {"P01": "width_record", "P23": "dxf_json_agree", "P27": "dxf_clear_reached",
                            "door_core": "door_record", "swing_core": "swing_hold"}


def lenient_required_met(details: dict[str, Any], damages: list[dict[str, Any]]) -> float:
    """1.0 iff every item in LENIENT_REQUIRED_ITEMS is met, else 0.0.

    A positive item is met when its own check holds - not when the weighted score is high, and not
    after the conclusion-reversal discount, which is a proportional haircut rather than this item's
    own result.  A deduction item is met when it did not fire.
    """
    damaged = {item for instance in (damages or []) for item in instance.get("item_ids", [])}
    for item in LENIENT_REQUIRED_ITEMS:
        if item.startswith("D"):
            if item in damaged:
                return 0.0
        elif not bool((details or {}).get(_LENIENT_POSITIVE_DETAIL[item])):
            return 0.0
    return 1.0


TOL = 0.18            # CAD tolerance, drawing units (inches)
M_TOL = 0.06          # tolerance on metric declarations
IN_TOL = M_TOL / 0.0254
INCH_M = 0.0254
REQUIRED = ("inspection_report.json", "layer_inventory.json", "extracted_original_layout.json", "violations_before.json", "repaired_layout.json", "changes.json", "repair_memo.md", "repaired_plan.dxf")

# ---------------------------------------------------------------------------
# Disposition vocabulary.  These classify the *meaning* of a record, so that a
# rephrased but equivalent status ("non-compliant", "fails the minimum",
# "carried for confirmation") is treated like the reference wording, while a
# reversed judgement is not.  Order matters: hold beats fail beats pass.
# ---------------------------------------------------------------------------
HOLD_RE = re.compile(
    r"\bhold(?:s|ing)?\b|on hold|unresolved|undetermin|indetermin|not determin|cannot be (?:determin|establish|confirm)"
    r"|no unambiguous|does not establish|doesn'?t establish|not establish|unable to (?:determin|establish|confirm)"
    r"|\bpending\b|await|to be (?:confirm|determin|verif|resolv)|open item|outstanding item|unverifi"
    r"|requires? (?:confirmation|verification|coordination)|\btbc\b|\btbd\b|further review|carried for review"
    # "still outstanding", "left open", "remains for coordination" are the same
    # state written without the reference package's noun phrases.
    r"|\boutstanding\b|still open|left open|remains? (?:for|open|outstanding)|for coordination",
    re.I,
)
FAIL_RE = re.compile(
    r"non-?\s?confor|non-?\s?compli|not\s+(?:confor|compli)|in-?compli|violat|deficien|\bfail"
    r"|insufficient|inadequate|substandard|under-?siz|undersize|short of|falls short|below the|less than the"
    r"|does not meet|doesn'?t meet|not meet|repair required|must be (?:widen|enlarg|increas)|\bwiden|\benlarg"
    # A finding written as a defect, or as a dimension that is too small, is a
    # failure however it is phrased.
    r"|\bdefect|too (?:small|narrow|tight)|smaller than|narrower than",
    re.I,
)
PASS_RE = re.compile(
    r"compli|confor|\bmeet(?:s|ing)?\b|\bmeet the\b|satisf|acceptab|adequate|\bretain|\bkeep(?:s|ing)?\b|\bkept\b|unchanged"
    r"|no change|as drawn|left as|\bremain(?:s|ed|ing)?\b|\bpass(?:es|ed|ing)?\b|above the|exceeds|greater than the"
    r"|(?<!un)resolved|confirmed|closed out|\bestablishes\b|determined",
    re.I,
)
MOVE_RE = re.compile(
    r"shift|\bmov(?:e|es|ed|ing)|relocat|reposition|offset|widen|enlarg|increas|realign|adjust|boundary"
    r"|translat|slide|displac|set ?back|pull(?:ed)? back|re-?draw|re-?position|new position|brings? the clear"
    # "pull the lower wall face back" puts the object between verb and particle.
    r"|pull[a-z]*\b[^.;]{0,40}\bback\b|push[a-z]*\b[^.;]{0,40}\bback\b|\bwall face\b[^.;]{0,20}\bback\b",
    re.I,
)
KEEP_RE = re.compile(r"retain|\bkeep(?:s|ing)?\b|\bkept\b|unchanged|no change|as drawn|left as|\bremain(?:s|ed|ing)?\b", re.I)
SWING_RE = re.compile(r"swing|\boperat|\barcs?\b|handing|hinge|which way the (?:door|leaf)|direction of travel", re.I)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


# A minus sign typeset as U+2212, or a dash used for one, is not the ASCII "-"
# the pattern below looks for, so "-443.27" written with one would parse as
# +443.27 and silently change a coordinate's sign.
DASHES = str.maketrans({"−": "-", "–": "-", "—": "-", "‐": "-", "‑": "-"})


def nums(value: Any) -> list[float]:
    return [float(x) for x in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", str(value).translate(DASHES))]


def as_float(value: Any) -> float | None:
    """Never raise on a submitted field; unparsable values simply do not score."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        found = nums(value)
        if len(found) != 1:
            return None
        out = found[0]
    return out if math.isfinite(out) else None


def has_num(value: Any, expected: float, tol: float = TOL) -> bool:
    return any(abs(x - expected) <= tol for x in nums(value))


def has_measure(value: Any, metric_m: float, tol_m: float = M_TOL) -> bool:
    """Accept the quantity written in metres or in the drawing's native inches."""
    return has_num(value, metric_m, tol_m) or has_num(value, metric_m / INCH_M, tol_m / INCH_M)


def has_measure_at_least(value: Any, minimum_m: float) -> bool:
    """Accept an actual width in metres or inches when it clears the minimum."""
    for number in nums(value):
        metric = number * INCH_M if number > 5 else number
        if metric >= minimum_m - M_TOL:
            return True
    return False


def flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{k} {flatten(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(flatten(v) for v in value)
    return str(value)


def norm_id(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


# The record conventions fix the identifier *values* ("F-HALL-WIDTH",
# "HALL-ROUTE-01") and require them repeated across the JSON records, the memo
# and the change log; they do not prescribe the JSON field name.  "finding_id"
# and "record_id" are therefore the same declaration as "id", so the field name
# a record happens to use does not decide whether its finding is read.
ID_KEY = re.compile(r"(?:^|_)id$", re.I)


def record_ids(record: dict[str, Any]) -> list[str]:
    """Every identifier the record carries, whatever its field is called."""
    out: list[str] = []
    for key, value in record.items():
        key_token = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if (ID_KEY.search(str(key)) or key_token.endswith("id")) and isinstance(value, (str, int, float)):
            out.append(norm_id(value))
    return out


def normalize_record_layout(value: Any) -> Any:
    aliases={"finding":"id","finding_key":"id","check_id":"id","measured_condition":"observed","requirement_basis":"required","evidence_list":"evidence","recommended_action":"disposition","compliance_status":"status"}
    if isinstance(value,dict):
        columns=value.get("columns",value.get("headers")); data=value.get("rows")
        if isinstance(columns,list) and isinstance(data,list) and all(isinstance(r,list) for r in data):
            return [normalize_record_layout(dict(zip(columns,r))) for r in data]
        return {aliases.get(str(k).lower(),k):normalize_record_layout(v) for k,v in value.items()}
    if isinstance(value,list):return [normalize_record_layout(v) for v in value]
    return value


def records(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if any(ID_KEY.search(str(key)) or re.sub(r"[^a-z0-9]", "", str(key).lower()).endswith("id") for key in value):
            out.append(value)
        for child in value.values():
            out.extend(records(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(records(child))
    return out


def subtree(record: Any, key_re: str) -> Any:
    """First value whose key matches key_re, searched depth-first."""
    pattern = re.compile(key_re, re.I)
    if isinstance(record, dict):
        for key, value in record.items():
            if pattern.search(str(key)):
                return value
        for value in record.values():
            found = subtree(value, key_re)
            if found is not None:
                return found
    elif isinstance(record, list):
        for value in record:
            found = subtree(value, key_re)
            if found is not None:
                return found
    return None


# A cue that is explicitly denied states the opposite of the family it belongs
# to: "no widening of the route is called for" is not a failure finding, and
# "no further review is needed" is not a hold.  Without this, a record can be
# classified into whichever family the checks want simply by mentioning that
# family's vocabulary in a denial.  Cues that carry their own negation
# ("does not meet", "non-conforming", "no change") are unaffected, because only
# the text *before* the match is inspected.
CUE_NEGATORS = re.compile(r"\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bnothing\b|\bnone\b|n'?t\b|\bneither\b", re.I)
NEGATION_WINDOW = 24


# `_` and `-` are word characters to `re`, so a `\b`-anchored cue cannot match
# inside an enum value: "coordination_hold_not_a_confirmed_violation" misses
# `\bhold\b`, matches FAIL_RE's boundary-free `violat` and reads as the opposite
# of what it says, with CUE_NEGATORS' `\bnot\b` equally unable to see the denial.
# The separators are word-broken before any cue is looked for, so a disposition
# written as an enum is classified like the same disposition written as prose;
# prose, which already has spaces, is unchanged.
CUE_SEPARATORS = re.compile(r"[_\-/]+")


def cue_text(value: Any) -> str:
    return CUE_SEPARATORS.sub(" ", str(value))


def cue_present(blob: str, pattern: re.Pattern[str]) -> bool:
    blob = cue_text(blob)
    for match in pattern.finditer(blob):
        if not CUE_NEGATORS.search(blob[max(0, match.start() - NEGATION_WINDOW):match.start()]):
            return True
    return False


def verdict(text: Any) -> str:
    blob = cue_text(text)
    if cue_present(blob, HOLD_RE):
        return "hold"
    if cue_present(blob, FAIL_RE):
        return "fail"
    if cue_present(blob, PASS_RE):
        return "pass"
    return "unknown"


# ---------------------------------------------------------------------------
# Conclusion reversal
#
# Three of the four dimensions carry no judgement: geometry_repair is measured
# off coordinates, artifact_integrity off identifiers and layer counts, and most
# of evidence_closure off cited clause numbers and unit pairs.  A submission
# that draws the correct repair and cites the correct clause while stating the
# opposite call on every finding therefore keeps them whole.  The rate below
# counts findings whose stated verdict is the exact opposite of the one the
# supplied record supports, and that undirected credit is withdrawn in
# proportion.  A finding that is merely wrong, missing, or written outside the
# vocabulary classifies as "unknown" and fills no slot.
FINDING_IDS = {"FHALLWIDTH", "FHALLDOOR", "FHALLSWING"}
EXPECTED_VERDICTS = {"F-HALL-WIDTH": "fail", "F-HALL-SWING": "hold"}
# For the two dimensioned findings the exact opposite is the other call; for the
# swing the opposite of "not determinable" is any settled call.
OPPOSITE_VERDICTS = {"fail": ("pass",), "pass": ("fail",), "hold": ("pass", "fail")}
MIN_REVERSAL_SLOTS = 2
REVERSAL_IMMUNE_DIMENSIONS = ()  # Independent geometry/evidence/integrity do not inherit judgement reversals.


def reversal_rate(stated: dict[str, str]) -> tuple[float, dict[str, Any]]:
    slots: dict[str, bool] = {}
    for finding, expected in EXPECTED_VERDICTS.items():
        found = stated.get(finding, "unknown")
        if found == "unknown":
            continue
        slots[finding] = found in OPPOSITE_VERDICTS[expected]
    if len(slots) < MIN_REVERSAL_SLOTS:
        return 0.0, {"slots": slots, "rate": 0.0}
    rate = sum(1 for value in slots.values() if value) / len(slots)
    return rate, {"slots": slots, "rate": round(rate, 6)}


def record_verdict(record: dict[str, Any]) -> str:
    for key_re in (r"compliance|determination|conclusion|assessment|verdict|result",
                   r"disposition|action|outcome|recommend"):
        held = subtree(record, key_re)
        if held is not None:
            found = verdict(flatten(held))
            if found != "unknown":
                return found
    status = subtree(record, r"^status$")
    if status is not None and not re.search(r"repair|workflow|coordination|reviewed|confirmed[_ -]?(?:repair|change)", flatten(status), re.I):
        found = verdict(flatten(status))
        if found != "unknown":
            return found
    return verdict(flatten(record))


def blocks(text: str) -> list[str]:
    """Split markdown into bullet/paragraph blocks so a wrapped bullet stays whole."""
    out: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("|") or re.match(r"\s*(?:[-*+]|\d+[.)]|#{1,6})\s", line):
            if cur:
                out.append(" ".join(cur))
                cur = []
        if line.strip():
            cur.append(line.strip())
    if cur:
        out.append(" ".join(cur))
    return out


# A memo section is a heading plus the bullets under it, and the identifier is
# normally written once, in the heading.  Matching chunk by chunk would return
# the heading alone and would pull a door paragraph that merely mentions
# HALL-ROUTE-01 into the route block.  Each chunk is attributed to the heading
# that owns it, so a section is read as the item its heading names.
HEADING_RE = re.compile(r"^#{1,6}\s|^\*\*[^*]+\*\*[\s:]*$")


def owned_chunks(chunks: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    heading = ""
    for chunk in chunks:
        if HEADING_RE.search(chunk):
            heading = chunk
        out.append((heading, chunk))
    return out


def item_block(chunks: list[str], id_re: str, kw_re: str, other_re: str) -> str:
    rows = owned_chunks(chunks)

    def pick(pattern: str) -> list[str]:
        hit = []
        for heading, chunk in rows:
            text = chunk if heading == chunk else heading + " " + chunk
            if re.search(pattern, text, re.I) and not re.search(other_re, text, re.I):
                hit.append(chunk)
        return hit

    return " ".join(pick(id_re) or pick(kw_re))


def point_list(entity: Any) -> list[tuple[float, float]]:
    try:
        if entity.dxftype() == "LWPOLYLINE":
            return [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
        if entity.dxftype() == "POLYLINE":
            return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
    except Exception:
        return []
    return []


def is_closed(entity: Any) -> bool:
    try:
        return bool(entity.closed if entity.dxftype() == "LWPOLYLINE" else entity.is_closed)
    except Exception:
        return False


def finite(points: list[tuple[float, float]]) -> bool:
    return bool(points) and all(math.isfinite(x) and math.isfinite(y) for x, y in points)


def _cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _crosses(p1, p2, p3, p4) -> bool:
    d1, d2 = _cross(p3, p4, p1), _cross(p3, p4, p2)
    d3, d4 = _cross(p1, p2, p3), _cross(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def simple_polygon(points: list[tuple[float, float]]) -> bool:
    if len(points) < 4 or len(points) > 64 or not finite(points):
        return False
    ring = list(points)
    if abs(ring[0][0] - ring[-1][0]) <= 1e-9 and abs(ring[0][1] - ring[-1][1]) <= 1e-9:
        ring = ring[:-1]
    n = len(ring)
    if n < 3:
        return False
    edges = [(ring[i], ring[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _crosses(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                return False
    return True


def bounds_of(points: list[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    if not finite(points):
        return None
    return (min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points))


def poly_match(points: list[tuple[float, float]], left: float, bottom: float, right: float, top: float) -> bool:
    if len(points) < 4:
        return False
    box = bounds_of(points)
    if box is None:
        return False
    return all(abs(a - b) <= TOL for a, b in zip(box, (left, bottom, right, top)))


def coerce_points(raw: Any) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    if not isinstance(raw, (list, tuple)):
        return out
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            x, y = as_float(item[0]), as_float(item[1])
        elif isinstance(item, dict):
            x, y = as_float(item.get("x")), as_float(item.get("y"))
        else:
            x = y = None
        if x is None or y is None:
            return []
        out.append((x, y))
    return out


def texts_of(model: Any) -> list[tuple[str, str]]:
    out = []
    for entity in model:
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        try:
            value = str(entity.dxf.text if entity.dxftype() == "TEXT" else entity.text)
            out.append((value, str(entity.dxf.layer)))
        except Exception:
            continue
    return out


def layer_counts(model: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity in model:
        name = str(entity.dxf.layer)
        counts[name] = counts.get(name, 0) + 1
    return counts


def entity_state(entity: Any) -> tuple[str, str, tuple[tuple[float, float], ...]]:
    """Stable source-entity state, excluding database identity fields."""
    if hasattr(entity, "_tags"):
        ignored = {
            "LWPOLYLINE": {(43, "0.0")},
            "MTEXT": {(72, "1"), (73, "1"), (44, "1.0")},
            "LEADER": {(73, "3")},
            "DIMENSION": {(50, "0.0")},
        }.get(entity.dxftype(), set())
        attrs = sorted((code, str(value)) for code, value in entity._tags
                       if code not in {5, 330} and (code, str(value)) not in ignored)
    else:
        attrs = sorted((key, str(value)) for key, value in entity.dxfattribs().items()
                       if key not in {"handle", "owner"})
    points = tuple((round(x, 6), round(y, 6)) for x, y in point_list(entity))
    return entity.dxftype(), json.dumps(attrs, sort_keys=True), points


def entity_handle(entity: Any) -> str | None:
    if hasattr(entity, "_tags"):
        value = entity.dxf._first(5)
    else:
        value = getattr(entity.dxf, "handle", None)
    return str(value).upper() if value not in (None, "") else None


def same_polygon(left: list[tuple[float, float]], right: list[tuple[float, float]]) -> bool:
    def clean(points):
        values = list(points)
        if len(values) > 1 and all(abs(a - b) <= TOL for a, b in zip(values[0], values[-1])):
            values.pop()
        return values
    a, b = clean(left), clean(right)
    if len(a) != len(b) or len(a) < 3:
        return False
    for candidate in (b, list(reversed(b))):
        for shift in range(len(candidate)):
            rotated = candidate[shift:] + candidate[:shift]
            if all(abs(x1 - x2) <= TOL and abs(y1 - y2) <= TOL
                   for (x1, y1), (x2, y2) in zip(a, rotated)):
                return True
    return False


# The record conventions fix identifier *values* ("HALL-ROUTE-01",
# "HALL-DOOR-01") and the unit convention; they do not name a JSON field.  A
# record may carry the repaired route polygon and its clear width as
# repaired_layout["room"]["polygon"] and repaired_layout["route"]["clear_width_m"],
# or as `route.polygon_native`, `elements[].route_polygon_native`,
# `elements/HALL-ROUTE-01/geometry/clear_width_metres` and the like, so the
# readers below bind to the object the instruction does fix.
ROUTE_IDENT, DOOR_IDENT = "HALLROUTE01", "HALLDOOR01"
POLY_KEY = re.compile(r"polygon|boundary|outline", re.I)
WIDTH_KEY = re.compile(r"width", re.I)
# A width that is not the *repaired* route's clear width: the condition before the
# repair, the requirement it is compared against, or another object's opening.
BEFORE_KEY = re.compile(r"origin|before|existing|source|as.?built|pre.?repair|prior", re.I)
LIMIT_KEY = re.compile(r"requir|minim|\bmin\b|margin|toleran|deficit|shortfall", re.I)
OTHER_OBJECT = re.compile(r"opening|leaf|jamb|door|header|obstruct", re.I)
METRIC_KEY = re.compile(r"metre|meter|(?:^|_)m(?:$|_)", re.I)
# A face coordinate recorded *inside* a width subtree ("clear_width": {"from_y": ...})
# is a position, not a width, and 129.367 in reads as a plausible 3.29 m if taken
# for one.  Positions are excluded wherever a width is being read.
COORDINATE_KEY = re.compile(r"(?:^|_)[xy]$|coordinate|position|sampled|anchor|insert|profile", re.I)


def object_of(node: Any, key: str) -> str | None:
    """Which of the two fixed identifiers a record speaks for, from its key or its own id fields."""
    texts = [key]
    if isinstance(node, dict):
        texts += [value for value in node.values() if isinstance(value, (str, int, float))]
    for text in texts:
        ident = norm_id(text)
        if DOOR_IDENT in ident:
            return "door"
        if ROUTE_IDENT in ident:
            return "route"
    return None


def route_polygons(document: Any) -> list[list[tuple[float, float]]]:
    """Every polygon carried by a record that names the route identifier."""
    out: list[list[tuple[float, float]]] = []

    def walk(node: Any, key: str, bound: str | None) -> None:
        bound = object_of(node, key) or bound
        if isinstance(node, dict):
            for child_key, child in node.items():
                if bound == "route" and POLY_KEY.search(str(child_key)):
                    points = coerce_points(child)
                    if len(points) >= 4:
                        out.append(points)
                walk(child, str(child_key), bound)
        elif isinstance(node, list):
            for child in node:
                walk(child, key, bound)

    walk(document, "", None)
    return out


def ident_records(document: Any, ident: str) -> list[dict[str, Any]]:
    """Every record whose nearest binding is `ident` ("route" or "door").

    The record conventions require the identifiers repeated across the JSON
    records, the memo and the change log; they do not say under which key, nor
    that the change log be grouped into sections named the way the reference
    happens to name them."""
    out: list[dict[str, Any]] = []

    def walk(node: Any, key: str) -> None:
        if isinstance(node, dict):
            if object_of(node, key) == ident:
                out.append(node)
            for child_key, child in node.items():
                walk(child, str(child_key))
        elif isinstance(node, list):
            for child in node:
                walk(child, key)

    walk(document, "")
    return out


def route_width_m(document: Any, repaired_only: bool = True) -> float | None:
    """The clear width of the route, in metres, as the document states it.

    Only widths bound to the route identifier are read, and only those that are
    neither the requirement nor another object's opening nor a face coordinate
    recorded inside a width subtree, so a value such as the 0.0254 conversion
    basis can never be mistaken for a width.  A value
    under a metre-named key is metres; a bare value is the drawing's native inch,
    which the instruction fixes.  Readings that disagree by more than the metric
    tolerance are ambiguous and none is taken.

    `repaired_only` drops the pre-repair condition as well, which is what
    repaired_layout.json is read for.  extracted_original_layout.json records the
    original condition throughout, so it is read with `repaired_only=False`."""
    found: list[float] = []

    def walk(node: Any, key: str, path: list[str], bound: str | None) -> None:
        bound = object_of(node, key) or bound
        if isinstance(node, dict):
            for child_key, child in node.items():
                walk(child, str(child_key), path + [str(child_key)], bound)
        elif isinstance(node, list):
            for child in node:
                walk(child, key, path + [key], bound)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            if bound != "route" or not any(WIDTH_KEY.search(part) for part in path):
                return
            if any(LIMIT_KEY.search(part) or OTHER_OBJECT.search(part) or COORDINATE_KEY.search(part)
                   for part in path):
                return
            if repaired_only and any(BEFORE_KEY.search(part) for part in path):
                return
            metres = float(node) if any(METRIC_KEY.search(part) for part in path[-2:]) else float(node) * INCH_M
            if 0.3 <= metres <= 5.0:
                found.append(metres)

    walk(document, "", [], None)
    if not found or max(found) - min(found) > M_TOL:
        return None
    return found[0]


def empty(error: str) -> dict[str, Any]:
    return settle({"dimension_scores": {"inspection_judgment": 0.0, "geometry_repair": 0.0, "evidence_closure": 0.0, "artifact_integrity": 0.0}, "details": {"error": error}}, {}, [])


# ---------------------------------------------------------------------------
# pd-ledger-v1 settlement.
# ---------------------------------------------------------------------------
# (item id, dimension, check variable); the weight of each item is read from scoring_params.json.
CHECKS = (
    ("P01", "inspection_judgment", "width_ok"),
    # The swing hold is scored by P08 (the hold note carried in the drawing),
    # P13 (the memo's swing block read as a hold) and the conclusion-reversal
    # discount, which charges a settled swing call across three dimensions.
    ("P08", "geometry_repair", "note_ok"),
    ("P09", "evidence_closure", "code_binding"),
    # P10 scores drawing_binding, unit_pair, ids_stable and inventory_true
    # together, as their mean completion.  All four sit in reversal-immune
    # dimensions, so the reversal discount applies to it.
    ("P10", "evidence_closure", "binding_and_integrity"),
    ("P12", "evidence_closure", "changes_ok"),
    ("P13", "evidence_closure", "memo_ok"),
    ("P16", "artifact_integrity", "cross_values"), ("P17", "artifact_integrity", "dxf_valid"),
    # P20-P23 and P27 cover the repaired route geometry, read from the route
    # identifier and from the repair boundary itself; P24, P25 and P28 cover the
    # recorded original condition and the inventory unit header, and P26 the
    # recorded inspection decision.
    ("P20", "geometry_repair", "route_geometry"),
    ("P21", "geometry_repair", "json_faces"),
    ("P22", "geometry_repair", "dxf_face_retained"),
    ("P27", "geometry_repair", "dxf_clear_reached"),
    ("P23", "geometry_repair", "dxf_json_agree"),
    ("P24", "artifact_integrity", "inventory_unit_header"),
    ("P25", "artifact_integrity", "original_faces"),
    ("P28", "artifact_integrity", "original_anchor"),
    ("P26", "inspection_judgment", "decision_recorded"),
)


# ---------------------------------------------------------------------------
# Affirmative errors charged as damage instances (D02, D05, D08, D09, D11).
#
# Each is quoted from the reference or from the instruction's own requirements,
# is decided from the submitted artifacts and the supplied originals alone, and
# none of them is triggered by the reference handoff.
# ---------------------------------------------------------------------------
HALL_ZONE = (-575.0, 95.0, -285.0, 205.0)   # the HALL and everything immediately on it
DOOR_TAG = re.compile(r"^[1-9]\d{3}$")
INCH_KEY = re.compile(r"(?:^|_)(?:in|ins|inch|inches)$|_in_|inch(?:es)?_", re.I)
METRE_KEY = re.compile(r"met(?:re|er)s?|(?:^|_)m$|_m_", re.I)


def tag_width_in(tag: str) -> int:
    """A door tag NNNN reads N ft N in wide by N ft N in high: 2468 is 28 inches."""
    return int(tag[0]) * 12 + int(tag[1])


def tag_decode_errors(node: Any) -> int:
    """A stated opening width in inches that contradicts the tag in its own record."""
    bad = 0
    if isinstance(node, dict):
        tag = None
        for key, value in node.items():
            if re.search(r"tag|mark|label", str(key), re.I) and isinstance(value, (str, int)) and DOOR_TAG.match(str(value)):
                tag = str(value)
        if tag is not None:
            expected = tag_width_in(tag)
            for key, value in node.items():
                name = str(key)
                if METRE_KEY.search(name) or not INCH_KEY.search(name):
                    continue
                if not re.search(r"width|opening|clear", name, re.I):
                    continue
                stated = as_float(value)
                if stated is not None and abs(stated - expected) > 1.0:
                    bad += 1
        for value in node.values():
            bad += tag_decode_errors(value)
    elif isinstance(node, list):
        for value in node:
            bad += tag_decode_errors(value)
    return bad


def load_params() -> dict[str, Any]:
    path = os.environ.get("SCORING_PARAMS") or str(Path(__file__).with_name("scoring_params.json"))
    return json.loads(Path(path).read_text(encoding="utf-8"))


def settle(result: dict[str, Any], completion: dict[str, float], damages: list[dict[str, Any]]) -> dict[str, Any]:
    params = load_params()
    weights = params["positive_weights"]
    coeffs = params["deduction_coefficients"]
    completion = {pid: max(0.0, min(1.0, float(completion.get(pid, 0.0)))) for pid in weights}
    earned = sum(weights[pid] * completion[pid] for pid in weights)
    retention = 1.0
    for inst in damages:
        retention *= min(float(coeffs[i]) for i in inst["item_ids"])
    final = round(earned * retention, 6)
    lenient = lenient_required_met(result.get("details") or {}, damages)
    result["reward"] = final
    result["rewards"] = {"strict": final, "lenient": lenient}
    result["reward_lenient"] = lenient
    result["reward_formulas"] = {
        "strict": "positive_earned * retention (pd-ledger-v1; weights and coefficients from scoring_params.json)",
        "lenient": ("1.0 iff every item in LENIENT_REQUIRED_ITEMS is met (positive: its own check holds; "
                    "deduction: it did not fire); required items: " + ", ".join(LENIENT_REQUIRED_ITEMS)),
    }
    result["scoring_ledger"] = {
        "schema_version": "pd-ledger-v1",
        "positive_completion": completion,
        "damage_instances": damages,
        "positive_earned": round(earned, 6),
        "retention": round(retention, 6),
        "final_score": final,
    }
    return result


def deliverable(path: Path) -> Path:
    """Map the given path to the output directory holding the deliverables."""
    if path.is_file():
        path = path.parent
    if path.is_dir() and not (path / "repaired_plan.dxf").is_file():
        if (path / "output").is_dir():
            return path / "output"
        hits = sorted(path.rglob("repaired_plan.dxf"), key=lambda p: len(p.parts))
        if hits:
            return hits[0].parent
    return path


def score(out: Path) -> dict[str, Any]:
    if not out.is_dir():
        return empty("output directory missing")
    missing = [name for name in REQUIRED if not (out / name).is_file() or (out / name).stat().st_size == 0]
    if missing:
        return empty("missing outputs: " + ", ".join(missing))
    try:
        gt = json.loads(Path(__file__).with_name("ground_truth.json").read_text(encoding="utf-8"))
        expected = {k: float(v) for k, v in gt["expected_values"].items()}
    except Exception as exc:
        return empty(f"ground truth error: {exc}")
    # The verifier is installed at /tests/validator.py in the task image, so
    # its filesystem parents are not the package checkout.  Prefer the
    # submission-adjacent materialized workspace and the container workspace;
    # keep the optional package-relative location for local reruns.
    test_root = Path(__file__).resolve().parent.parent
    source_roots = [
        out.parent,
        out.parent / "task/environment/workspace",
        out.parent / "environment/workspace",
        test_root / "environment/workspace",
        Path("/workspace"),
    ]
    bad_sources = []
    resolved: dict[str, Path] = {}
    fallback: dict[str, Path] = {}
    for name, digest in gt.get("locked_inputs", {}).items():
        source = next((root / name for root in source_roots if (root / name).is_file()), None)
        if source is None or sha256(source) != digest:
            bad_sources.append(name)
            if source is not None:
                fallback[name] = source
        else:
            resolved[name] = source
    if bad_sources:
        # D01 is charged, but the checks are still computed against whatever source
        # file exists so the coefficient acts on real credit.
        missing_drawing = "residential_floor_plan.dxf" not in resolved and "residential_floor_plan.dxf" not in fallback
        if missing_drawing:
            return empty("source integrity failure: " + ", ".join(bad_sources))
        resolved = {**fallback, **resolved}
    try:
        parsed = {name: normalize_record_layout(json.loads((out / name).read_text(encoding="utf-8"))) for name in REQUIRED if name.endswith(".json")}
        memo = (out / "repair_memo.md").read_text(encoding="utf-8")
        drawing = dxfreader.readfile(out / "repaired_plan.dxf")
    except Exception as exc:
        return empty(f"artifact parse failure: {exc}")
    try:
        source_doc = dxfreader.readfile(resolved["residential_floor_plan.dxf"])
    except Exception as exc:
        return empty(f"source drawing unreadable: {exc}")
    src_model = source_doc.modelspace()
    source_by_handle = {entity_handle(entity): entity_state(entity) for entity in src_model if entity_handle(entity)}
    # The instruction does not name a unique DXF handle. A selected opening is
    # admissible when its explicit handle exists in the locked source drawing;
    # the separate HALL identifiers, measurement, evidence, and scope checks
    # establish whether that source object is the door under review.
    admissible_door_handles = set(source_by_handle)

    # ---- anchors -----------------------------------------------------
    route_min_m = expected["route_min_m"]
    door_min_m = expected["door_min_m"]
    src_route_m = expected["route_source_width_m"]
    src_door_m = expected["door_source_width_m"]
    left, right, top = expected["room_left_in"], expected["room_right_in"], expected["room_top_in"]
    src_bottom = expected["room_bottom_in"]
    repaired_bottom = top - route_min_m / INCH_M
    door_x0, door_x1, door_y = expected["door_x0_in"], expected["door_x1_in"], expected["door_y_in"]
    handles = [str(h) for h in gt.get("evidence", {}).get("drawing_layers", [])]
    handles += sorted(admissible_door_handles)
    handles += [str(gt.get("evidence", {}).get("hall_handle", ""))]
    handles = [h for h in handles if h]

    def handle_in(text: Any) -> bool:
        blob = str(text)
        return any(re.search(r"(?<![0-9A-Za-z])" + re.escape(h) + r"(?![0-9A-Za-z])", blob) for h in handles)

    # ---- inspection judgment ----------------------------------------
    finding_rows: dict[str, dict[str, Any]] = {}
    for source in ("violations_before.json", "inspection_report.json"):
        for row in records(parsed[source]):
            for key in record_ids(row):
                if key in FINDING_IDS and key not in finding_rows:
                    finding_rows[key] = row
    width = finding_rows.get("FHALLWIDTH", {})
    door = finding_rows.get("FHALLDOOR", {})
    swing = finding_rows.get("FHALLSWING", {})
    def bound_target(row):
        text=flatten(row).upper()
        explicit=[]
        for key,value in row.items():
            if re.search(r"target|source.?handle|door.?handle|selected",str(key),re.I) and isinstance(value,(str,int)):
                explicit.extend(re.findall(r"(?<![0-9A-Z])[0-9A-F]{3,}(?![0-9A-Z])",str(value).upper()))
        if explicit:
            return len(set(explicit)) == 1 and explicit[0] in admissible_door_handles
        return any(re.search(r"(?<![0-9A-Z])"+re.escape(handle)+r"(?![0-9A-Z])",text)
                   for handle in admissible_door_handles)
    door_findings=[r for name in ("violations_before.json","inspection_report.json") for r in records(parsed[name]) if "FHALLDOOR" in record_ids(r)]
    swing_findings=[r for name in ("violations_before.json","inspection_report.json") for r in records(parsed[name]) if "FHALLSWING" in record_ids(r)]
    door_target_bound=bool(door_findings) and all(bound_target(r) for r in door_findings)
    swing_target_bound=bool(swing_findings) and all(bound_target(r) for r in swing_findings)
    target_bound=door_target_bound and swing_target_bound


    OBS_RE = r"observ|measur|existing|as-?built|found|source|actual|native|door_opening|opening_width"
    REQ_RE = r"requir|minimum|^min$|code|criterion|allowab|limit|standard"

    def measured(record: dict[str, Any], key_re: str, metric: float) -> bool:
        """Accept the quantity from any semantically matching field.

        Records may carry provenance fields such as ``source_handle`` before an
        ``observed`` object. Reading only the first matching key makes the JSON
        insertion order decide whether the actual measurement is visible.
        """
        pattern = re.compile(key_re, re.I)
        values: list[Any] = []

        def collect(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if pattern.search(str(key)):
                        values.append(value)
                    collect(value)
            elif isinstance(node, list):
                for value in node:
                    collect(value)

        collect(record)
        return any(has_measure(value, metric) for value in values)

    width_verdict = record_verdict(width) if width else "unknown"
    door_verdict = record_verdict(door) if door else "unknown"
    swing_verdict = record_verdict(swing) if swing else "unknown"
    width_ok = bool(
        width
        and width_verdict == "fail"
        and measured(width, OBS_RE, src_route_m)
        and measured(width, REQ_RE, route_min_m)
        and MOVE_RE.search(cue_text(flatten(subtree(width, r"disposition|action|recommend") or width))) is not None
        and "residential_floor_plan.dxf" in flatten(width)
        and "fire_safety_code.pdf" in flatten(width)
    )
    door_ok = bool(
        door
        and door_target_bound
        and door_verdict == "hold"
        and measured(door, OBS_RE, src_door_m)
        and measured(door, REQ_RE, door_min_m)
        and HOLD_RE.search(cue_text(flatten(subtree(door, r"disposition|action|recommend") or door))) is not None
        and "residential_floor_plan.dxf" in flatten(door)
        and "fire_safety_code.pdf" in flatten(door)
    )
    # A hold only counts when it is an argued limitation about *this* opening:
    # it must bind to real drawing evidence, and the other two records must
    # still carry a decision.  Marking every record "to be determined" is not
    # an inspection.
    swing_evidence = flatten(subtree(swing, r"evidence|reference|source|location") or swing) if swing else ""
    swing_bound = bool(
        handle_in(swing_evidence)
        or has_num(swing_evidence, door_x0, TOL)
        or has_num(swing_evidence, door_x1, TOL)
        or has_num(swing_evidence, expected["hall_x"], TOL)
    )
    swing_ok = bool(
        swing
        and swing_target_bound
        and swing_verdict == "hold"
        and width_verdict != "hold"
        and door_verdict == "hold"
        # searched over the record body with the identifier removed, so the
        # literal id "F-HALL-SWING" cannot stand in for a stated limitation
        and SWING_RE.search(cue_text(flatten({k: v for k, v in swing.items() if str(k).lower() != "id"}))) is not None
        and swing_bound
        and "residential_floor_plan.dxf" in flatten(swing)
    )
    inspection = 0.55 * float(width_ok) + 0.25 * float(door_ok) + 0.20 * float(swing_ok)

    def local_route_box(box, x0, x1, minimum):
        return bool(box and abs(box[0]-x0)<=TOL and abs(box[2]-x1)<=TOL
            and box[3]-box[1]>=minimum-TOL and box[1]<=top+TOL and box[3]>=src_bottom-TOL
            and HALL_ZONE[1]-TOL<=box[1] and box[3]<=HALL_ZONE[3]+TOL)
    relocation_text=flatten(parsed["changes.json"])+" "+memo
    linkage_review=bool(re.search(r"north|upper",relocation_text,re.I) and re.search(r"necessar|needed|avoid|because",relocation_text,re.I) and re.search(r"adjacent|door|wall",relocation_text,re.I)
                        and target_bound and swing_ok)
    # ---- geometry repair --------------------------------------------
    repaired = parsed["repaired_layout.json"] if isinstance(parsed["repaired_layout.json"], dict) else {}
    room = repaired.get("room", {}) if isinstance(repaired.get("room"), dict) else {}
    # The literal spelling first, then every polygon the submission binds to the
    # route identifier.
    room_polys = [pts for pts in [coerce_points(room.get("polygon", []))] if len(pts) >= 4] or route_polygons(repaired)
    bounds_ok = any(
        len(pts) >= 4
        and simple_polygon(pts)
        and local_route_box(bounds_of(pts), left, right, route_min_m / INCH_M)
        for pts in room_polys
    )

    model = drawing.modelspace()
    src_layers = layer_counts(src_model)
    new_layers_counts = layer_counts(model)
    new_layers = [name for name in new_layers_counts if name not in src_layers]
    candidate_by_handle = {entity_handle(entity): entity_state(entity) for entity in model if entity_handle(entity)}
    kept = sum(candidate_by_handle.get(handle) == state for handle, state in source_by_handle.items())
    total_src = len(source_by_handle) or 1
    source_retained = kept / total_src >= 0.99

    src_closed_bounds = [bounds_of(point_list(e)) for e in src_model if e.dxftype() in {"LWPOLYLINE", "POLYLINE"} and is_closed(e)]

    def preexisting(box: tuple[float, float, float, float] | None) -> bool:
        if box is None:
            return True
        return any(b is not None and all(abs(a - c) <= TOL for a, c in zip(box, b)) for b in src_closed_bounds)

    repair_polys = []
    for entity in model:
        if entity.dxftype() not in {"LWPOLYLINE", "POLYLINE"} or not is_closed(entity):
            continue
        pts = point_list(entity)
        layer = str(entity.dxf.layer).upper()
        if layer.startswith("REPAIR") or not preexisting(bounds_of(pts)):
            repair_polys.append((pts, layer))
    poly_hit = any(
        simple_polygon(pts) and local_route_box(bounds_of(pts),left,right,route_min_m/INCH_M)
        for pts, _ in repair_polys
    )
    # The repaired boundary agrees with the repaired JSON room within CAD tolerance.
    json_dxf_agree = any(
        bounds_of(pts) is not None and bounds_of(candidate) is not None
        and all(abs(a - b) <= TOL for a, b in zip(bounds_of(pts), bounds_of(candidate)))
        for pts, _ in repair_polys for candidate in room_polys
    )
    poly_hit = poly_hit and json_dxf_agree and source_retained

    # Hard constraint: the repaired clear route must actually reach the code
    # minimum.  Measured from the drawing when a repair boundary exists.
    dxf_width_m = None
    for pts, _ in repair_polys:
        box = bounds_of(pts)
        if box is not None and abs(box[0] - left) <= TOL and abs(box[2] - right) <= TOL:
            dxf_width_m = (box[3] - box[1]) * INCH_M
            break
    json_width_m = as_float(subtree(repaired.get("route", {}), r"clear_width_m|width_m|clear_m"))
    if json_width_m is None:
        json_width_m = route_width_m(repaired)
    width_gate = dxf_width_m is not None and dxf_width_m >= route_min_m - 0.02
    clear_ok = bool(
        source_retained
        and width_gate

        and json_width_m is not None
        and json_width_m >= route_min_m - M_TOL
        and abs(dxf_width_m-json_width_m)<=M_TOL
    )

    door_seg = coerce_points((repaired.get("door", {}) or {}).get("opening_segment", []))
    json_door_ok = len(door_seg) == 2 and (
        (abs(door_seg[0][0] - door_x0) <= TOL and abs(door_seg[1][0] - door_x1) <= TOL)
        or (abs(door_seg[0][0] - door_x1) <= TOL and abs(door_seg[1][0] - door_x0) <= TOL)
    ) and all(abs(p[1] - door_y) <= TOL for p in door_seg)
    dxf_door_ok = False
    for entity in model:
        if entity.dxftype() != "LINE":
            continue
        try:
            a, b = entity.dxf.start, entity.dxf.end
            xs = sorted((float(a.x), float(b.x)))
            ys = (float(a.y), float(b.y))
        except Exception:
            continue
        if abs(xs[0] - min(door_x0, door_x1)) <= TOL and abs(xs[1] - max(door_x0, door_x1)) <= TOL and all(abs(y - door_y) <= TOL for y in ys):
            dxf_door_ok = True
            break
    line_hit = bool(json_door_ok and dxf_door_ok and source_retained)

    src_text_set = {value.strip() for value, _ in texts_of(src_model)}
    new_notes = " ".join(
        value for value, layer in texts_of(model)
        if layer.upper().startswith("REPAIR") or value.strip() not in src_text_set
    )
    note_ok = bool(
        source_retained
        and SWING_RE.search(cue_text(new_notes)) is not None
        and verdict(new_notes) == "hold"
    )

    # ---- geometry repair: repaired route and boundary ---------------
    # These items are bound to the route identifier or to the repair boundary
    # itself, and are read one per substantive record of the repaired handoff
    # (repaired_layout.json, changes.json, repaired_plan.dxf).  The quantities
    # they measure are the corridor's *faces* (y = 129.367 and 169.367, 40.000 in
    # apart, as the drawing's own dimension text 14A4 "16'3 x 3'4" records) and
    # the 1.1 m route minimum.
    room_boxes = [box for box in (bounds_of(pts) for pts in room_polys) if box is not None]
    repair_boxes = [box for box in (bounds_of(pts) for pts, _ in repair_polys) if box is not None]
    route_min_in = route_min_m / INCH_M
    # The repaired route is a closed room polygon whose clear width reaches the
    # route minimum and agrees with the width the JSON states.
    route_geometry = bool(
        any(len(pts) >= 4 and simple_polygon(pts) for pts in room_polys)
        and any(box[3] - box[1] >= route_min_in - TOL for box in room_boxes)
        and json_width_m is not None
        and any(abs((box[3] - box[1]) * INCH_M - json_width_m) <= M_TOL for box in room_boxes)
    )
    # The lower wall face is shifted parallel to the source face: the room's
    # `bottom` moves down and the retained north face stays where it is.
    json_faces = any(local_route_box(box,left,right,route_min_in) and (abs(box[3]-top)<=TOL or linkage_review) for box in room_boxes)
    # The same decision read off the drawing: a closed REPAIR-HALL boundary on
    # the retained north face at the code width.
    dxf_face_retained = any(simple_polygon(pts) and local_route_box(bounds_of(pts),left,right,route_min_in)
                            and (abs(bounds_of(pts)[3]-top)<=TOL or linkage_review) for pts, _ in repair_polys)
    dxf_clear_reached = any(simple_polygon(pts) and local_route_box(bounds_of(pts),left,right,route_min_in)
                            for pts, _ in repair_polys)
    # The drawn boundary and repaired room must agree as actual polygons, not only by bounding box.
    dxf_json_agree = any(simple_polygon(dxf_pts) and simple_polygon(json_pts)
                         and same_polygon(dxf_pts, json_pts)
                         for dxf_pts, _ in repair_polys for json_pts in room_polys)

    geometry = 0.20 * float(bounds_ok) + 0.30 * float(poly_hit) + 0.15 * float(clear_ok) + 0.15 * float(line_hit) + 0.20 * float(note_ok)

    # ---- evidence closure -------------------------------------------
    report_text = flatten(parsed["inspection_report.json"])
    changes = parsed["changes.json"]
    evidence_blob = report_text + " " + memo + " " + flatten(changes)
    clause_cited = "fire_safety_code.pdf" in evidence_blob and re.search(r"5\.5\.30|(?:physical\s+)?page\s*61", evidence_blob, re.I) is not None
    code_binding = bool(
        clause_cited
        and measured(width, REQ_RE, route_min_m)
        and measured(door, REQ_RE, door_min_m)
        and door_ok
    )
    handle_hit = handle_in(evidence_blob)
    anchor_hit = has_num(evidence_blob, expected["hall_x"], TOL) and has_num(evidence_blob, expected["hall_y"], TOL)
    face_hit = has_num(evidence_blob, left, TOL) and has_num(evidence_blob, src_bottom, TOL)
    drawing_binding = bool("residential_floor_plan.dxf" in evidence_blob and (handle_hit or anchor_hit or face_hit))
    unit_pair = bool(
        (has_num(evidence_blob, src_route_m, M_TOL) and has_num(evidence_blob, src_route_m / INCH_M, IN_TOL))
        or (has_num(evidence_blob, src_door_m, M_TOL) and has_num(evidence_blob, src_door_m / INCH_M, IN_TOL))
    )

    # The change rows are bound to the identifier, and the disposition is read
    # from the record itself rather than from a grouping key: a change log may
    # name the subject `element_id`, `route_id`, `subject_id`, `element`, `target`
    # or `object`, and may or may not be grouped into sections.  The instruction
    # fixes the identifier values and requires them repeated across the change
    # log; it does not fix section names.  What is read is the substance: a route
    # row carrying the before and after widths, and the door held for
    # coordination.
    route_rows = ident_records(changes, "route")
    door_rows = ident_records(changes, "door")
    route_change = next((r for r in route_rows
                         if subtree(r, r"after|repaired|new|proposed") is not None), None)
    hold_row = next((r for r in door_rows if verdict(flatten(r)) == "hold"), None)
    changes_ok = bool(
        route_change is not None
        and has_measure_at_least(subtree(route_change, r"after|repaired|new|proposed"), route_min_m)
        and has_measure(subtree(route_change, r"before|original|existing|source"), src_route_m)
        # The instruction's requirement is that the handoff "distinguish confirmed
        # repairs from items that remain for coordination", which the route change
        # and the hold carry.  The door rows are located, but no compliance
        # conclusion is required of them.
        and hold_row is not None
        and verdict(flatten(hold_row)) == "hold"
        and door_ok
    )

    chunks = blocks(memo)
    route_block = item_block(chunks, r"F-?\s?HALL-?\s?WIDTH|HALL-?ROUTE-?01", r"\broute\b|corridor|hall(?:way)? width|egress path",
                             r"F-?\s?HALL-?\s?DOOR|F-?\s?HALL-?\s?SWING")
    door_block = item_block(chunks, r"F-?\s?HALL-?\s?DOOR", r"\bdoor\b|opening|leaf",
                            r"F-?\s?HALL-?\s?WIDTH|F-?\s?HALL-?\s?SWING|swing")
    swing_block = item_block(chunks, r"F-?\s?HALL-?\s?SWING", r"swing|door operation|arc\b",
                             r"F-?\s?HALL-?\s?WIDTH|F-?\s?HALL-?\s?DOOR")
    memo_ok = bool(
        route_block and has_measure_at_least(route_block, route_min_m) and has_measure(route_block, src_route_m)
        and MOVE_RE.search(cue_text(route_block)) is not None
        and door_block and verdict(door_block) == "hold" and door_ok
        and swing_block and verdict(swing_block) == "hold"
    )
    evidence = 0.25 * float(code_binding) + 0.20 * float(drawing_binding) + 0.15 * float(unit_pair) + 0.20 * float(changes_ok) + 0.20 * float(memo_ok)

    # ---- artifact integrity -----------------------------------------
    ids = {key for row in records(parsed["violations_before.json"]) for key in record_ids(row)}
    ids_stable = bool(
        {"FHALLWIDTH", "FHALLDOOR", "FHALLSWING"}.issubset(ids)
        and "HALL-ROUTE-01" in flatten(parsed["extracted_original_layout.json"])
        and "HALL-ROUTE-01" in flatten(repaired)
        and "HALL-ROUTE-01" in flatten(changes)
        and "HALL-DOOR-01" in flatten(repaired)
    )
    inv_blob = flatten(parsed["layer_inventory.json"])
    inv_nums = nums(inv_blob)
    named = sum(1 for name in src_layers if name in inv_blob)
    counted = sum(1 for name, count in src_layers.items() if name in inv_blob and any(abs(v - count) <= 0.5 for v in inv_nums))
    inventory_true = bool(src_layers and named / len(src_layers) >= 0.9 and counted / len(src_layers) >= 0.6)

    original = parsed["extracted_original_layout.json"]
    orig_route = as_float(subtree(original.get("route", {}) if isinstance(original, dict) else {}, r"clear_width_m|width_m"))
    if orig_route is None:
        # The same identifier-bound reading, for the *original* clear width.
        # extracted_original_layout.json records the original condition
        # throughout, so the pre-repair filter does not apply to it.
        orig_route = route_width_m(original, repaired_only=False)
    before_m = None
    after_m = None
    if route_change is not None:
        before_sub, after_sub = subtree(route_change, r"before|original|existing|source"), subtree(route_change, r"after|repaired|new|proposed")
        before_vals = [v for v in nums(before_sub) if 0.1 < v < 5.0]
        after_vals = [v for v in nums(after_sub) if 0.1 < v < 5.0]
        before_m = before_vals[0] if before_vals else None
        after_m = after_vals[0] if after_vals else None
    cross_values = bool(
        orig_route is not None and json_width_m is not None and before_m is not None and after_m is not None
        and orig_route > 0.05 and json_width_m > 0.05
        and abs(orig_route - before_m) <= M_TOL and abs(json_width_m - after_m) <= M_TOL
        and abs(json_width_m - orig_route) > 1e-6
    )
    repair_geom_valid = bool(repair_polys) and all(simple_polygon(pts) for pts, _ in repair_polys)
    dxf_valid = bool(repair_geom_valid and drawing.header.get("$INSUNITS") is not None and source_retained)

    # ---- original condition, inventory header, decision -------------
    # The inventory records drawing_unit "in" beside insunits_header 4: the
    # drawing declares millimetres while the geometry is inches, and recording
    # the header is what makes the conversion checkable.
    inventory_unit_header = bool(
        re.search(r"insunits", inv_blob, re.I)
        and has_num(inv_blob, 4, 0.5)
        and re.search(r"\bin\b|inch", inv_blob, re.I)
    )
    # The original layout records the room polygon on the two wall faces and the
    # room's label anchor on the HALL text anchor.
    orig_layout = parsed["extracted_original_layout.json"]
    orig_polys = [pts for pts in [coerce_points(((orig_layout.get("room") or {}) if isinstance(orig_layout, dict) else {}).get("polygon", []))] if len(pts) >= 4] \
        or route_polygons(orig_layout)
    orig_boxes = [box for box in (bounds_of(pts) for pts in orig_polys) if box is not None]
    orig_faces = any(abs(box[1] - src_bottom) <= TOL and abs(box[3] - top) <= TOL for box in orig_boxes)
    orig_anchor = bool(has_num(flatten(orig_layout), expected["hall_x"], TOL)
                       and has_num(flatten(orig_layout), expected["hall_y"], TOL))
    # The inspection report records the release decision: a route-widening
    # coordination concept plus explicit holds for the unresolved door evidence.
    decision_held = subtree(parsed["inspection_report.json"], r"^decision$|^summary$|^conclusion$|overall_|recommend|disposition")
    decision_text = cue_text(flatten(decision_held)) if decision_held is not None else ""
    decision_recorded = bool(
        (MOVE_RE.search(decision_text) or re.search(r"repair.{0,24}(?:route|width)|(?:route|width).{0,24}repair", decision_text, re.I))
        and re.search(r"door|opening", decision_text, re.I)
        and re.search(r"hold|pending|coordinate|confirm|verif", decision_text, re.I)
    )

    integrity = 0.30 * float(ids_stable) + 0.25 * float(inventory_true) + 0.25 * float(cross_values) + 0.20 * float(dxf_valid)

    dimensions = {"inspection_judgment": round(inspection, 6), "geometry_repair": round(geometry, 6), "evidence_closure": round(evidence, 6), "artifact_integrity": round(integrity, 6)}
    rate, rate_detail = reversal_rate({"F-HALL-WIDTH": width_verdict, "F-HALL-DOOR": door_verdict, "F-HALL-SWING": swing_verdict})
    for name in REVERSAL_IMMUNE_DIMENSIONS:
        dimensions[name] = round(dimensions[name] * (1.0 - rate), 6)
    inspection, geometry, evidence, integrity = (
        dimensions["inspection_judgment"], dimensions["geometry_repair"],
        dimensions["evidence_closure"], dimensions["artifact_integrity"])
    note_ok = bool(note_ok and target_bound)
    code_binding = bool(code_binding and target_bound)
    changes_ok = bool(changes_ok and target_bound)
    memo_ok = bool(memo_ok and target_bound)
    checks = {"door_target_bound":target_bound,"width_ok": width_ok, "door_ok": door_ok, "swing_ok": swing_ok, "bounds_ok": bounds_ok,
              "poly_hit": poly_hit, "clear_ok": clear_ok, "line_hit": line_hit, "note_ok": note_ok,
              "code_binding": code_binding, "drawing_binding": drawing_binding, "unit_pair": unit_pair,
              "changes_ok": changes_ok, "memo_ok": memo_ok, "ids_stable": ids_stable,
              "inventory_true": inventory_true, "cross_values": cross_values, "dxf_valid": dxf_valid,
              "route_geometry": route_geometry, "json_faces": json_faces,
              "dxf_face_retained": dxf_face_retained, "dxf_clear_reached": dxf_clear_reached,
              "dxf_json_agree": dxf_json_agree, "inventory_unit_header": inventory_unit_header,
              "original_faces": orig_faces, "original_anchor": orig_anchor,
              "decision_recorded": decision_recorded,
              "binding_and_integrity": (float(bool(drawing_binding)) + float(bool(unit_pair))
                                        + float(bool(ids_stable)) + float(bool(inventory_true))) / 4.0}
    completion = {pid: float(checks[var]) * ((1.0 - rate) if dim in REVERSAL_IMMUNE_DIMENSIONS else 1.0)
                  for pid, dim, var in CHECKS}
    # ---- affirmative errors (see the D02/D05/D08/D09/D11 block above) ----
    long_repairs = [box for pts, _ in repair_polys for box in [bounds_of(pts)]
                    if box is not None and box[2] - box[0] > 50.0]
    # D02  RUBRIC.md requires the lower HALL boundary to move "parallel to the
    #          source face" while "the upper face and door opening ... remain
    #          aligned"; golden/changes.json moves `bottom` (129.367 -> 126.060)
    #          and nothing else.  A repair boundary pushed above the source north
    #          face widens the route by taking space from the rooms beyond it.
    fixed_face_moved = any(box[3] > top + TOL for box in long_repairs) and not linkage_review
    # D05  RUBRIC.md: the repaired DXF "must retain the source entities and add
    #          a closed HALL/egress boundary in the same coordinate frame ...
    #          copying the source without a repaired boundary earns no geometry
    #          credit".  Nothing closed was added.
    no_repair_boundary = not repair_polys
    # D08  "confine design changes to the first-floor HALL egress geometry and
    #          its immediately affected door operation": a repair polygon lying
    #          wholly outside the HALL is a design change the issue does not cover.
    out_of_scope = [box for pts, _ in repair_polys for box in [bounds_of(pts)]
                    if box is not None and (box[2] < HALL_ZONE[0] or box[0] > HALL_ZONE[2]
                                            or box[3] < HALL_ZONE[1] or box[1] > HALL_ZONE[3])]
    # D09  An opening tag decoded against the opening the supplied drawing
    #          actually carries: a "2668" is 2 ft 6 in wide, not 31 ft 8 in.
    tag_errors = sum(tag_decode_errors(doc) for doc in parsed.values())
    # D11  "Draw geometry you add to the repaired DXF on new layers whose
    #          names begin with REPAIR-."
    off_layer = sorted({name for name in new_layers if not name.upper().startswith("REPAIR")})

    damages = []
    if fixed_face_moved:
        damages.append({"key": "repair:fixed_north_face_moved", "item_ids": ["D02"]})
    if no_repair_boundary:
        damages.append({"key": "dxf:no_repair_boundary_added", "item_ids": ["D05"]})
    if out_of_scope:
        damages.append({"key": "repair:design_change_outside_hall", "item_ids": ["D08"]})
    def bad_metric_opening(node):
        if isinstance(node,dict):
            for k,v in node.items():
                if isinstance(v,(float,int)) and (METRE_KEY.search(str(k)) or str(k).lower() in ("converted_m","metres","meters")) and abs(float(v)-src_door_m)>.01:
                    return True
                if isinstance(v,(dict,list)) and bad_metric_opening(v):return True
        elif isinstance(node,list):return any(bad_metric_opening(v) for v in node)
        return False
    opening_unit_error = any(not measured(r,OBS_RE,src_door_m) or bad_metric_opening(subtree(r,OBS_RE) or {}) for r in door_findings)
    if opening_unit_error:
        for pid in ("P08","P09","P12","P13"):completion[pid]=0.0
    if tag_errors or not target_bound or opening_unit_error:
        damages.append({"key": "records:door_identity_or_opening_units", "item_ids": ["D09"]})
    if off_layer:
        damages.append({"key": "dxf:added_geometry_off_repair_layer:" + ",".join(off_layer), "item_ids": ["D11"]})
    if bad_sources:
        damages.append({"key": "locked source inputs altered: " + ", ".join(bad_sources), "item_ids": ["D01"]})
    result = {
        "dimension_scores": dimensions,
        "details": {
            "admissible_door_handles":sorted(admissible_door_handles),"door_target_bound":target_bound,"door_identity":door_target_bound,"swing_identity":swing_target_bound,"opening_unit_error":opening_unit_error,"width_record": width_ok, "door_record": door_ok, "swing_hold": swing_ok,
            "verdicts": {"width": width_verdict, "door": door_verdict, "swing": swing_verdict},
            "conclusion_reversal_rate": round(rate, 6), "conclusion_reversal_detail": rate_detail,
            "room_json": bounds_ok, "repair_polyline": poly_hit, "clear_width": clear_ok,
            "door_line": line_hit, "hold_note": note_ok, "source_retained": source_retained,
            "dxf_clear_width_m": dxf_width_m, "json_clear_width_m": json_width_m,
            "code_binding": code_binding, "drawing_binding": drawing_binding, "unit_pair": unit_pair,
            "changes_agreement": changes_ok, "memo_agreement": memo_ok,
            "ids_stable": ids_stable, "inventory_true": inventory_true, "cross_values": cross_values, "dxf_valid": dxf_valid,
            "route_geometry": route_geometry, "json_faces": json_faces,
            "dxf_face_retained": dxf_face_retained, "dxf_clear_reached": dxf_clear_reached,
            "dxf_json_agree": dxf_json_agree,
            "inventory_unit_header": inventory_unit_header, "original_faces": orig_faces,
            "original_anchor": orig_anchor, "decision_recorded": decision_recorded,
            "fixed_face_moved": fixed_face_moved, "no_repair_boundary": no_repair_boundary,
            "design_change_outside_hall": bool(out_of_scope), "opening_tag_errors": tag_errors,
            "added_geometry_off_repair_layer": off_layer,
        },
    }
    if bad_sources:
        result["dimension_scores"] = {k: 0.0 for k in dimensions}
        result["details"]["error"] = "source integrity failure: " + ", ".join(bad_sources)
    return settle(result, completion, damages)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/output")
    print(json.dumps(score(deliverable(target)), indent=2))

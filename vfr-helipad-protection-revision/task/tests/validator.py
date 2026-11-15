#!/usr/bin/env python3
"""Condition-blind continuous scorer for the helipad plan repair handoff (pd-ledger-v1).

Usage: validator.py <output>
  <output> is the output directory holding inspection_report.json, repair_memo.md and repaired_plan.dxf
  (the container passes /workspace/output; rollout artifacts/ or task golden/ also work, a file selects its
  directory, and a directory without the deliverables is searched for inspection_report.json).
  The locked criteria PDFs are read from the output's parent, else tests/../environment/workspace, else /workspace.

The strict score is settled in the standard form
  final = positive_earned * retention
  positive_earned = sum(weight[P] * completion[P])      (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

The positive items are P01 applicability and control, P02/P06/P07 for the twelve professional findings split
by the three disposition classes Golden's own ``findings[].status`` uses, P03 evidence traceability, P04
repaired geometry, P05 cross-deliverable closure, and P08/P09 for the two reference units the dimension checks
do not read. A dimension's completion is its earned points divided by its weight in WEIGHTS. The
(1 - conclusion_reversal_rate) discount on evidence, geometry and closure is a continuous factor and is folded
into P03-P05. The geometry-internal rules (sheet-setup credit withdrawn without controlling geometry) stay
inside P04's completion. The damage items are D01 locked criteria PDFs missing or hash-mismatched, D02
terminal-elevation conflict settled on one value instead of held, D03 east normal-CHAPI controlling surface
left unsettled, and D04 mirrored west normal-CHAPI clearance surface drawn; when D01 fires the completions are
computed anyway. A missing ground_truth.json returns a ledger with every completion 0. Alongside the strict
score a binary lenient lens is reported: it re-reads the same ledger and asks only whether every item in
``LENIENT_REQUIRED_ITEMS`` holds on its own result.
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


WEIGHTS = {
    "applicability_and_control": 0.24,
    "professional_findings": 0.36,
    "evidence_traceability": 0.15,
    "repaired_geometry": 0.20,
    "cross_deliverable_closure": 0.05,
}
TOLERANCE_M = 0.08

# The thirteen professional findings are grouped by the three disposition classes
# Golden's own ``findings[].status`` uses.  Each check keeps its own verdict and each
# class carries its own share of the findings weight.
FINDING_GROUPS = {
    "P02": ("pad_retained", "primary_retained", "clear_length_retained", "apz_length_retained"),
    "P06": ("clear_width_repaired", "apz_width_repaired", "east_chapi_surface_repaired"),
    "P07": ("west_chapi_design_hold", "terminal_elevation_conflict", "per_end_geometry_disposition",
            "apz_ii_excluded", "transitional_surface_scope_hold", "plan_limits_unresolved"),
}

# ---------------------------------------------------------------------------
# The lenient lens: what this issue-for-coordination package cannot be released without.
# Not a cut on the weighted total - each item is read on its own ledger result.
#   P02  the four findings the record supports retaining (pad size, primary surface, clear-zone
#        length, APZ I length).  instruction.md: "document every material compliance conclusion";
#        a revision that does not state what stays as built cannot be coordinated against.
#   P06  the three nonconforming findings repaired (clear-zone flare, APZ I flare, east CHAPI
#        surface).  instruction.md: "Inspect the legacy plan against current_airfield_criteria.pdf,
#        determine the controlling criteria for each approach end" - these are the revision.
#   P09  the land-use limitation carried open.  instruction.md: "Base every finding on evidence in
#        the supplied /workspace project record; do not import a rule, dimension, or site fact that
#        those files do not contain" - closing it positively invents a site fact.
#   D03  the east normal-CHAPI controlling surface actually settled.  It is the one approach end
#        the supplied record fully dimensions; leaving it unsettled fails the instruction's
#        "determine the controlling criteria for each approach end".
#   D04  no mirrored west normal-CHAPI surface.  instruction.md: "Carry any dimension that the
#        supplied record cannot support as a visible design hold rather than a completed repair."
# Deliberately not required: P01/P03/P05/P07 (applicability breadth, citation coverage, memo
# closure) - they grade how thoroughly the package is argued, not whether it is usable.
LENIENT_REQUIRED_ITEMS = ["P02", "P06", "P09", "D03", "D04"]
LENIENT_COMPLETION_FLOOR = 1.0 - 1e-9  # a required finding class counts only when all of it lands


def lenient_lens(completion: dict[str, float], instances: list[dict]) -> tuple[float, dict]:
    """Binary reading of the same ledger: 1.0 only when every required item stands on its own
    result - a positive item at full completion, a deduction item never charged."""
    charged = {item for instance in instances for item in instance["item_ids"]}
    per_item = {item: (item not in charged) if item.startswith("D")
                else float(completion.get(item, 0.0)) >= LENIENT_COMPLETION_FLOOR
                for item in LENIENT_REQUIRED_ITEMS}
    return (1.0 if all(per_item.values()) else 0.0), per_item


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=True, sort_keys=True)
    value = value.lower().replace("–", "-").replace("—", "-")
    value = re.sub(r"navy\s*/?\s*marine", "navy and marine", value)
    value = re.sub(r"\bn\s*/\s*mc\b", "navy and marine corps", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def values_only(value: Any) -> str:
    """Serialise the values of a record without its key names.

    Field naming is not fixed by the task statement, so a submission may legitimately
    rename keys.  Scoring on keys also lets a key called ``requirement`` satisfy a
    decision pattern such as ``require`` without the submission ever stating a
    decision, so keys are dropped before any pattern is applied.
    """
    if isinstance(value, dict):
        return " ".join(values_only(child) for child in value.values())
    if isinstance(value, list):
        return " ".join(values_only(child) for child in value)
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, (int, float)):
        return repr(value)
    return str(value)


def records(value: Any, depth: int = 0) -> list[tuple[str, str]]:
    """Return ``(full, stated)`` pairs for every candidate conclusion record.

    ``full`` keeps key names so that structural context (``origin``, ``axis``,
    ``east``, ``west``) still counts as topic context.  ``stated`` is the values
    only, and every decision / direction test runs against ``stated`` so a schema
    key cannot supply a conclusion the submission never wrote.
    """
    result: list[tuple[str, str]] = []
    if isinstance(value, dict):
        direct_scalars = [child for child in value.values() if isinstance(child, (str, int, float, bool))]
        if depth and direct_scalars:
            result.append((canonical(value), canonical(values_only(value))))
        for child in value.values():
            result.extend(records(child, depth + 1))
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, str) and len(child) >= 80:
                result.append((canonical(child), canonical(child)))
            result.extend(records(child, depth + 1))
    return result


def has_any(text: str, alternatives: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in alternatives)


# A decision cue that is negated ("no clarification is needed", "not required",
# "no conflict exists") states the opposite conclusion and must not earn the
# credit reserved for asserting it.
NEGATORS = r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bnone\b|\brather than\b|\binstead of\b|\bneed not\b|\bdoes not\b|\bdo not\b)"


def asserted(text: str, alternatives: tuple[str, ...]) -> bool:
    """True when at least one alternative occurs without a nearby negator."""
    for pattern in alternatives:
        for match in re.finditer(pattern, text):
            window = text[max(0, match.start() - 45):match.start()]
            window = re.sub(r"\bdo not (?:infer|mirror|draw|add|choose|certify)\b", " ", window)
            if not re.search(NEGATORS, window):
                return True
    return False


RETAIN_CUES = (r"retain", r"preserve", r"preserved", r"no change", r"unchanged", r"\bkeep", r"\bkept\b", r"carry[^.;]{0,30}forward", r"conforms")
REPAIR_CUES = (r"repair", r"nonconform", r"non-conform", r"replace", r"revis", r"correct", r"deficien", r"supersed", r"substitut")


def polarity(text: str) -> str:
    """Classify the disposition direction a record actually states."""
    # Evaluate cues in context so phrases such as "do not retain" or
    # "repair is not required" do not turn a record into a false mixed
    # direction.  This is the deterministic fallback after semantic judge
    # resolves equivalent professional wording.
    retain = asserted(text, RETAIN_CUES)
    repair = asserted(text, REPAIR_CUES)
    if retain and repair:
        return "mixed"
    if retain:
        return "retain"
    if repair:
        return "repair"
    return "none"


def numbers(text: str) -> list[float]:
    return [float(item) for item in re.findall(r"(?<![a-z0-9])\d+(?:\.\d+)?", text)]


def has_number(text: str, expected: float, tolerance: float = TOLERANCE_M) -> bool:
    return any(abs(value - expected) <= tolerance for value in numbers(text))


def record_matches(
    record: tuple[str, str],
    topic_groups: tuple[tuple[str, ...], ...],
    required_numbers: tuple[float, ...] = (),
    decisions: tuple[str, ...] = (),
    extra_groups: tuple[tuple[str, ...], ...] = (),
    direction: str = "",
    sourced: bool = False,
) -> bool:
    text, stated = record
    return (
        all(has_any(text, group) for group in topic_groups)
        and all(has_number(text, value) for value in required_numbers)
        and (not decisions or asserted(stated, decisions))
        and all(has_any(text, group) for group in extra_groups)
        and (not direction or polarity(stated) == direction)
        and (not sourced or bool(re.search(r"airfield_criteria\.pdf", text)))
    )


def subtree_records(value: Any, depth: int = 0) -> list[tuple[str, str]]:
    """Like ``records`` but each dict node carries its whole subtree.

    ``records`` emits a node's *direct* scalars only, so a report that nests its
    dimensions one level below the origin/axis/units line splits a single stated
    basis across two records and can satisfy neither.  Golden happens to keep all
    of it on one level, which is a layout choice the contract never required.
    These pairs let a check that needs a whole section read it as one, without
    loosening any check that legitimately wants a single record.
    """
    result: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if depth:
            result.append((canonical(value), canonical(values_only(value))))
        for child in value.values():
            result.extend(subtree_records(child, depth + 1))
    elif isinstance(value, list):
        for child in value:
            result.extend(subtree_records(child, depth + 1))
    return result


def find_record(
    source_records: list[tuple[str, str]],
    topic_groups: tuple[tuple[str, ...], ...],
    required_numbers: tuple[float, ...] = (),
    decisions: tuple[str, ...] = (),
    extra_groups: tuple[tuple[str, ...], ...] = (),
    direction: str = "",
    sourced: bool = False,
) -> str:
    for record in source_records:
        if record_matches(record, topic_groups, required_numbers, decisions, extra_groups, direction, sourced):
            return record[0]
    return ""


def claim_record(
    source_records: list[tuple[str, str]],
    used: set[int],
    topic_groups: tuple[tuple[str, ...], ...],
    required_numbers: tuple[float, ...] = (),
    decisions: tuple[str, ...] = (),
    extra_groups: tuple[tuple[str, ...], ...] = (),
    direction: str = "",
    sourced: bool = False,
) -> str:
    """Claim one distinct conclusion record so one omnibus blob cannot earn repeated credit."""
    for index, record in enumerate(source_records):
        if index in used:
            continue
        if record_matches(record, topic_groups, required_numbers, decisions, extra_groups, direction, sourced):
            used.add(index)
            return record[0]
    return ""


def claim_compound_record(
    source_records: list[tuple[str, str]],
    used: set[int],
    topic_groups: tuple[tuple[str, ...], ...],
    required_numbers: tuple[float, ...] = (),
    decisions: tuple[str, ...] = (),
    extra_groups: tuple[tuple[str, ...], ...] = (),
    direction: str = "",
    sourced: bool = False,
) -> str:
    """Claim a source-bound conclusion spread over related records.

    The applicability skill asks agents to keep attributes such as slope,
    length, terminal width, and basis as separate topics.  Requiring all of
    those values in one JSON object would make a valid skill-following report
    fail merely because it is decomposed.  This helper joins distinct records
    that share the same object/topic and checks the required meaning over their
    combined evidence.  The records remain distinct for anti-duplication: once
    consumed by one finding they cannot be reused by another.
    """
    candidates = [
        (index, record)
        for index, record in enumerate(source_records)
        if index not in used and all(has_any(record[0], group) for group in topic_groups)
    ]
    if not candidates:
        return ""
    # Keep the smallest prefix that covers all numbers and extra evidence.  A
    # report may put one attribute per record, while an omnibus report still
    # works because the first record already covers the complete set.
    # Evidence for a neighbouring finding often repeats the same nouns.  Prefer
    # the record whose explicit topic field carries the requested object; this
    # prevents an APZ finding's citations from consuming a clear-zone finding.
    def topic_score(record: tuple[str, str]) -> int:
        match = re.search(r'"topic"\s*:\s*"([^"]+)"', record[0])
        topic = match.group(1) if match else ""
        return sum(has_any(topic, group) for group in topic_groups)

    candidates.sort(key=lambda item: topic_score(item[1]), reverse=True)
    selected: list[tuple[int, tuple[str, str]]] = []
    covered: set[float] = set()
    for index, record in candidates:
        selected.append((index, record))
        covered.update(value for value in required_numbers if has_number(record[0], value))
        joined = " ".join(item[1][0] for item in selected)
        if all(value in covered for value in required_numbers) and all(has_any(joined, group) for group in extra_groups):
            stated = " ".join(item[1][1] for item in selected)
            if (not decisions or asserted(stated, decisions)) and (not direction or polarity(stated) == direction):
                if not sourced or bool(re.search(r"airfield_criteria\.pdf", joined)):
                    for item_index, _ in selected:
                        used.add(item_index)
                    return joined
    return ""


# A decision record is evidence-bound only when it names the file *and* a resolvable
# location inside it.  Naming the file alone is a bibliography, and a bibliography cannot
# close an individual criteria decision: the next reviewer cannot re-derive the call.
LOCATORS = (r"(?:pages?|pp?\.)\s*\d", r"tables?\s*\d", r"figures?\s*\d", r"notes?\s*\d",
            r"sections?\s*\d", r"items?\s*\d", r"appendix", r"paragraphs?\s*\d", r"\bfig\.?\s*\d")


def evidence_located(text: str) -> bool:
    """True when a record cites a supplied criteria file and a location within it."""
    return bool(text) and bool(re.search(r"airfield_criteria\.pdf", text)) and has_any(text, LOCATORS)


def source_bound(text: str, file_pattern: str, location_patterns: tuple[str, ...]) -> bool:
    return bool(text) and bool(re.search(file_pattern, text)) and has_any(text, location_patterns)


# ---------------------------------------------------------------------------
# Conclusion reversal
#
# Three of the five dimensions hold no directional content: the drawing is scored
# on parsed coordinates, the traceability checks only ask whether a record cites
# the right file and page, and the closure checks only ask whether the same nouns
# reappear in the memo.  A submission that keeps the golden numbers and citations
# but states the opposite call on every item therefore keeps those dimensions at
# full credit.  The detector below measures how systematically the submission
# asserts the *exact opposite* of the required conclusion and withdraws that
# undirected credit in proportion.
#
# It only fires on an affirmative statement of the opposite call.  A submission
# that is merely wrong, incomplete, or written against its own field names
# asserts nothing here and is not touched.
REVERSAL_NEGATORS = (
    r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bnone\b|\bnothing\b|\brather than\b"
    r"|\binstead of\b|\bneed not\b|\bcannot\b|\bunless\b|\bonly when\b|\bonly where\b|\bonly if\b)"
)
MIN_REVERSAL_SLOTS = 3
REVERSAL_IMMUNE_DIMENSIONS = ("repaired_geometry", "evidence_traceability", "cross_deliverable_closure")


def stated_directly(text: str, patterns: tuple[str, ...]) -> bool:
    """True when a pattern occurs affirmatively (no negator in the preceding window).

    Unlike :func:`asserted` this does not forgive a leading ``do not ...`` phrase:
    here the question is whether the submission actually makes the opposite claim,
    and ``do not mirror`` is the correct claim, not the opposite one.
    """
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if not re.search(REVERSAL_NEGATORS, text[max(0, match.start() - 45):match.start()]):
                return True
    return False


# (name, topic groups, affirmative statements of the opposite call)
OPPOSITE_CLAIMS: tuple[tuple[str, tuple[tuple[str, ...], ...], tuple[str, ...]], ...] = (
    (
        "west_surface_dimensioned",
        ((r"west",), (r"chapi",)),
        (
            r"mirror[a-z]* (?:the )?east[^.;]{0,60}(?:onto|to) the west",
            r"mirror[a-z]* west[^.;]{0,40}(?:polygon|surface|boundary)",
            r"mirrored west[^.;]{0,40}(?:polygon|surface|boundary)",
            r"west[^.;]{0,60}(?:polygon|surface|boundary)[^.;]{0,40}(?:is|are|may be) (?:mirrored|dimensioned|drawn|resolved|closed)",
            r"west[^.;]{0,40}(?:is|are) (?:fully )?dimensioned",
        ),
    ),
    (
        "terminal_elevation_closed",
        ((r"terminal.elevation",),),
        (
            r"(?:are|is) consistent",
            r"\bagrees? (?:with|at)\b",
            r"terminal elevation may be chosen",
            r"adopt \d",
            r"(?:choose|chose|chosen|select|adopt) (?:one |a |the )?(?:metric )?(?:value|elevation)",
            r"conflict[^.;]{0,30}(?:is|are) (?:closed|resolved|withdrawn)",
        ),
    ),
    (
        "apz_ii_included",
        ((r"apz ii",),),
        (
            r"add apz ii",
            r"apz ii[^.;]{0,30}(?:is |are |must be |has been )(?:required|applicable|added)",
            r"apz ii (?:applies|is required|is applicable)",
        ),
    ),
    (
        "plan_limits_certified",
        ((r"grade",), (r"elevation",)),
        (
            r"certif[a-z]*[^.;]{0,60}compliant",
            r"(?:are|is) verified compliant",
            r"plan (?:geometry|view)[^.;]{0,40}establishes",
        ),
    ),
    (
        "per_end_conditions_matched",
        ((r"east",), (r"west",), (r"chapi",)),
        (
            r"conditions?[^.;]{0,30}(?:match\b|agree\b|are identical|are the same)",
            r"(?:identical|same) chapi",
            r"one identical",
            r"mirrored at both ends",
        ),
    ),
    (
        "document_control_swapped",
        ((r"legacy_airfield_criteria\.pdf",), (r"current_airfield_criteria\.pdf",)),
        (
            r"legacy_airfield_criteria\.pdf[^.;]{0,60}(?:controls|governs|is the controlling|is the governing)",
            r"current_airfield_criteria\.pdf[^.;]{0,90}(?:under inspection|is superseded|does not control|is only)",
        ),
    ),
)

# (name, topic groups, number keys, extra groups, the disposition direction the
# record's own numbers support).  The locators are the ones the per-item finding
# checks already use, minus the direction and decision requirements, so a slot is
# filled only by a record that would otherwise have earned that finding.  A
# submission that dispositions some neighbouring row, uses its own field names, or
# never assembles the item at all fills no slot.
DIRECTED_ITEMS: tuple[tuple[str, tuple[tuple[str, ...], ...], tuple[str, ...], tuple[tuple[str, ...], ...], str], ...] = (
    ("pad", ((r"helipad", r"pad size"),), ("pad_size",), ((r"square", r"\bx\b"),), "retain"),
    ("primary", ((r"primary surface",),), ("primary_size",), ((r"center",),), "retain"),
    ("clear_zone_length", ((r"clear.zone",), (r"length",)), ("clear_zone_length",),
     ((r"primary.surface edge", r"primary edge"), (r"each", r"both", r"reciprocal")), "retain"),
    ("apz_length", ((r"apz i",), (r"length", r"continu")), ("apz_length",), ((r"clear.zone",),), "retain"),
    ("clear_zone_width", ((r"clear.zone",), (r"width", r"envelope", r"flare")),
     ("legacy_clear_zone_width", "clear_zone_start_width", "clear_zone_end_width"),
     ((r"constant", r"uniform"), (r"flare", r"widen", r"start.*end")), "repair"),
    ("apz_width", ((r"apz i",), (r"width", r"envelope", r"flare")),
     ("legacy_apz_width", "apz_start_width", "apz_end_width"),
     ((r"constant", r"uniform"), (r"flare", r"widen", r"start.*end")), "repair"),
    ("east_chapi_surface", ((r"east",), (r"chapi",), (r"clearance surface", r"adcs", r"approach.departure")),
     ("legacy_adcs_slope", "legacy_adcs_length", "legacy_adcs_end_width",
      "normal_chapi_slope", "normal_chapi_length", "normal_chapi_end_width"),
     ((r"normal",), (r"positive.x", r"east")), "repair"),
)


def conclusion_reversal(
    source_records: list[tuple[str, str]], values: dict[str, float]
) -> tuple[float, dict[str, Any]]:
    """Fraction of the submission's conclusions stated as the exact opposite.

    The two families are rated separately and the larger rate wins: a submission
    that flips every categorical call has reversed its conclusions even if the
    retain/repair wording is untouched, and pooling the families would let the
    larger one dilute the smaller one away.
    """
    claim_slots: list[bool] = []
    claim_detail: dict[str, bool] = {}
    for name, topic_groups, opposite in OPPOSITE_CLAIMS:
        scoped = [
            record for record in source_records
            if all(has_any(record[0], group) for group in topic_groups)
        ]
        if not scoped:
            continue
        verdict = any(stated_directly(record[1], opposite) for record in scoped)
        claim_slots.append(verdict)
        claim_detail[name] = verdict

    direction_slots: list[bool] = []
    direction_detail: dict[str, str] = {}
    for name, topic_groups, number_keys, extra_groups, expected in DIRECTED_ITEMS:
        wanted = tuple(values[key] for key in number_keys)
        for text, stated in source_records:
            if not all(has_any(text, group) for group in topic_groups):
                continue
            if not all(has_number(text, value) for value in wanted):
                continue
            if not all(has_any(text, group) for group in extra_groups):
                continue
            if not re.search(r"airfield_criteria\.pdf", text):
                continue
            direction = polarity(stated)
            # "mixed" and "none" state no single direction, so they are not a
            # reversal; only a clean statement of the other call counts, and it
            # has to be asserted the way the finding check would require it -
            # a cue that appears under a negator ("must not be substituted") is
            # a scoping remark, not a disposition.
            cues = {"retain": RETAIN_CUES, "repair": REPAIR_CUES}.get(direction)
            if cues and asserted(stated, cues):
                direction_slots.append(direction != expected)
                direction_detail[name] = direction
                break

    def family_rate(slots: list[bool]) -> float:
        if len(slots) < MIN_REVERSAL_SLOTS:
            return 0.0
        return sum(1 for slot in slots if slot) / len(slots)

    rate = max(family_rate(claim_slots), family_rate(direction_slots))
    return rate, {
        "opposite_claims": claim_detail,
        "opposite_claim_rate": round(family_rate(claim_slots), 6),
        "stated_directions": direction_detail,
        "reversed_direction_rate": round(family_rate(direction_slots), 6),
    }


def expected_polygons(values: dict[str, float]) -> dict[str, list[list[list[float]]]]:
    primary_edge = values["primary_size"] / 2.0

    def rect(size: float) -> list[list[float]]:
        half = size / 2.0
        return [[-half, -half], [half, -half], [half, half], [-half, half]]

    def end_poly(start: float, length: float, w0: float, w1: float, direction: int) -> list[list[float]]:
        s0, s1 = direction * start, direction * (start + length)
        return [[s0, -w0 / 2], [s1, -w1 / 2], [s1, w1 / 2], [s0, w0 / 2]]

    return {
        "pad": [rect(values["pad_size"])],
        "primary": [rect(values["primary_size"])],
        "clear_zone": [
            end_poly(primary_edge, values["clear_zone_length"], values["clear_zone_start_width"], values["clear_zone_end_width"], direction)
            for direction in (1, -1)
        ],
        "apz_i": [
            end_poly(primary_edge + values["clear_zone_length"], values["apz_length"], values["apz_start_width"], values["apz_end_width"], direction)
            for direction in (1, -1)
        ],
        "east_chapi_adcs": [
            end_poly(primary_edge, values["normal_chapi_length"], values["primary_size"], values["normal_chapi_end_width"], 1)
        ],
    }


def entity_points(entity: Any) -> list[tuple[float, float]]:
    if entity.dxftype() == "LWPOLYLINE":
        return [(float(point[0]), float(point[1])) for point in entity.get_points("xy")]
    if entity.dxftype() == "POLYLINE":
        return [(float(vertex.dxf.location.x), float(vertex.dxf.location.y)) for vertex in entity.vertices]
    return []


def closed_entity(entity: Any) -> bool:
    if entity.dxftype() == "LWPOLYLINE":
        return bool(entity.closed)
    if entity.dxftype() == "POLYLINE":
        return bool(entity.is_closed)
    return False


def point_distance(a: tuple[float, float] | list[float], b: tuple[float, float] | list[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def polygon_matches(actual: list[tuple[float, float]], expected: list[list[float]]) -> bool:
    if len(actual) < 4 or any(not math.isfinite(value) for point in actual for value in point):
        return False
    # A matching bounding box and vertices is insufficient: a bow-tie or other
    # self-intersecting boundary is not a valid protection polygon.
    points = list(actual)
    if points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        return False

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def intersects(a, b, c, d):
        eps = 1e-9
        o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
        return ((o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and
                (o3 > eps and o4 < -eps or o3 < -eps and o4 > eps))

    edges = [(points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j in {i - 1, i + 1} or (i == 0 and j == len(edges) - 1):
                continue
            if intersects(a, b, edges[j][0], edges[j][1]):
                return False
    ax = [point[0] for point in actual]
    ay = [point[1] for point in actual]
    ex = [point[0] for point in expected]
    ey = [point[1] for point in expected]
    if any(abs(a - b) > TOLERANCE_M for a, b in zip((min(ax), max(ax), min(ay), max(ay)), (min(ex), max(ex), min(ey), max(ey)))):
        return False
    return all(any(point_distance(want, got) <= TOLERANCE_M for got in actual) for want in expected)


def dxf_score(path: Path, values: dict[str, float]) -> tuple[float, dict[str, Any]]:
    checks: dict[str, Any] = {}
    if not path.is_file() or path.stat().st_size == 0:
        return 0.0, {"readable": False, "error": "missing or empty repaired_plan.dxf"}
    try:
        doc = dxfreader.readfile(path)
    except Exception as exc:
        return 0.0, {"readable": False, "error": str(exc)}

    msp = doc.modelspace()
    polygons = [entity_points(entity) for entity in msp if entity.dxftype() in {"LWPOLYLINE", "POLYLINE"} and closed_entity(entity)]
    texts = []
    lines = []
    for entity in msp:
        if entity.dxftype() == "TEXT":
            texts.append(str(entity.dxf.text))
        elif entity.dxftype() == "MTEXT":
            texts.append(str(entity.text))
        elif entity.dxftype() == "LINE":
            lines.append(entity)
    labels = canonical(" ".join(texts))
    version_number = int(doc.dxfversion[2:]) if doc.dxfversion.startswith("AC") and doc.dxfversion[2:].isdigit() else 0
    # The centerline has to be the axis of the geometry that is actually drawn, so its
    # extent is read from the controlling stations rather than from a fixed number.
    west_station = values["primary_size"] / 2.0 + values["clear_zone_length"] + values["apz_length"]
    east_station = values["primary_size"] / 2.0 + values["normal_chapi_length"]
    centerline = any(
        abs(float(line.dxf.start.y)) <= TOLERANCE_M
        and abs(float(line.dxf.end.y)) <= TOLERANCE_M
        and min(float(line.dxf.start.x), float(line.dxf.end.x)) <= -west_station + TOLERANCE_M
        and max(float(line.dxf.start.x), float(line.dxf.end.x)) >= east_station - TOLERANCE_M
        for line in lines
    )
    # Each controlling surface and each approach end has to be named on the sheet, and
    # the sheet has to carry a metric unit and the design hold. The task statement asks
    # for "metric units" and "visibly annotated" geometry and publishes no label
    # vocabulary, so any metric unit token counts and `$INSUNITS` carries the unit.
    metric_unit = has_any(labels, (r"\bm\b", r"\bmeters?\b", r"\bmetres?\b"))
    checks.update({
        "readable": True,
        "meters_insunits": int(doc.header.get("$INSUNITS", 0)) == 6,
        "r2010_or_later": version_number >= 1024,
        "x_axis_centerline": centerline,
        "usable_annotations": metric_unit and all(
            term in labels
            for term in ("helipad", "primary", "clear zone", "apz i", "chapi", "east", "west", "hold")
        ),
    })
    structural = (
        0.005
        + (0.004 if checks["meters_insunits"] else 0.0)
        + (0.002 if checks["r2010_or_later"] else 0.0)
        + (0.003 if checks["x_axis_centerline"] else 0.0)
        + (0.006 if checks["usable_annotations"] else 0.0)
    )
    expected = expected_polygons(values)
    geometry_weights = {"pad": 0.015, "primary": 0.015, "clear_zone": 0.035, "apz_i": 0.035, "east_chapi_adcs": 0.05}
    score = structural
    for name, wanted_polygons in expected.items():
        used: set[int] = set()
        hits = 0
        for wanted in wanted_polygons:
            match_index = next(
                (index for index, actual in enumerate(polygons) if index not in used and polygon_matches(actual, wanted)),
                None,
            )
            if match_index is not None:
                used.add(match_index)
                hits += 1
        checks[name] = {"matched": hits, "required": len(wanted_polygons)}
        score += geometry_weights[name] * hits / len(wanted_polygons)
    west_normal = expected_polygons(values)["east_chapi_adcs"][0]
    west_normal = [[-float(x), float(y)] for x, y in west_normal]
    checks["west_normal_chapi_absent"] = not any(polygon_matches(actual, west_normal) for actual in polygons)
    checks["west_design_hold_annotation"] = (
        "west" in labels
        and "chapi" in labels
        and has_any(labels, (r"design hold", r"unresolved", r"pending"))
        and has_any(labels, (r"no controlling", r"not supplied", r"missing", r"conflict"))
    )
    # Correctly omitting the west surface, annotating the hold, and the sheet-setup
    # credits only mean something on a drawing that actually carries the controlling
    # geometry.  An empty or wrongly dimensioned sheet omits the west surface for free.
    controlling_hits = sum(checks[name]["matched"] for name in expected)
    controlling_required = sum(len(group) for group in expected.values())
    checks["controlling_geometry_present"] = controlling_hits >= controlling_required - 2
    if checks["controlling_geometry_present"]:
        score += 0.015 if checks["west_normal_chapi_absent"] else 0.0
        score += 0.015 if checks["west_design_hold_annotation"] else 0.0
    else:
        score -= structural
    # Hard constraint: the west end has no record-supported dimensions.  A drawing that
    # asserts a mirrored normal-CHAPI clearance surface there has imported geometry the
    # supplied record cannot support, which voids the repaired-geometry dimension.
    earned = round(min(max(score, 0.0), WEIGHTS["repaired_geometry"]), 6)
    # The ledger charges the void as the deduction item D04, so it needs the points the
    # drawing earned before the void; the reported dimension score keeps the voided value.
    checks["geometry_points_before_mirror_void"] = earned
    if not checks["west_normal_chapi_absent"]:
        return 0.0, checks
    return earned, checks


def empty_result(error: str) -> dict[str, Any]:
    return {
        "dimension_scores": {name: 0.0 for name in WEIGHTS},
        "details": {"error": error},
    }


# ---------------------------------------------------------------------------
# Two further reference units Golden states, and two affirmative errors against
# Golden's own explicit dispositions.  Each predicate is bound to a single
# statement in the rollout's own report - one JSON string field, split into
# sentences - or to measured DXF geometry, because "the value appears somewhere
# in the deliverable" is a different question and scores the wrong runs.

STATEMENT_SENTENCE = re.compile(r"(?<=[.])\s+|\n")


def stmt_norm(value: Any) -> str:
    """Lower-case, flatten separators, and keep document references addressable."""
    text = str(value).lower()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = text.replace("°", " degree ")
    text = re.sub(r"\b4\s*-\s*9\s*a\b", "fig49a", text)
    text = re.sub(r"\b4\s*-\s*9\s*b\b", "fig49b", text)
    text = re.sub(r"\btable\s*4\s*-\s*(\d+)", r"table4x\1", text)
    text = re.sub(r"[_/\-]", " ", text)
    return re.sub(r"\s+", " ", text)


def stmt_fields(node: Any, path: tuple = ()) -> list[tuple[str, str]]:
    """Every string-valued leaf with its key path: the report's own statements."""
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            out.extend(stmt_fields(value, path + (str(key),)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            out.extend(stmt_fields(value, path + (str(index),)))
    elif isinstance(node, str) and node.strip():
        out.append((stmt_norm(" ".join(path)), stmt_norm(node)))
    return out


def stmt_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def stmt_sentence_hit(fields: list[tuple[str, str]], groups: tuple[tuple[str, ...], ...],
                    not_patterns: tuple[str, ...] = ()) -> bool:
    """One sentence of one field carries at least one pattern from every group."""
    for _, text in fields:
        for sentence in STATEMENT_SENTENCE.split(text):
            if all(stmt_any(sentence, group) for group in groups) and not stmt_any(sentence, not_patterns):
                return True
    return False


def stmt_number_in(text: str, target: float, tolerance: float = 0.011) -> bool:
    for match in re.finditer(r"-?\d+(?:\.\d+)?", text):
        try:
            if abs(float(match.group()) - target) <= tolerance:
                return True
        except ValueError:
            continue
    return False


# Golden review_basis.branch_decision: "Use the service-specific standard VFR branch
# in Figure 4-9a; exclude the Army and Air Force limited-use branch split into Figure
# 4-9b."  The `nearby_conditional_branch_excluded` check scores the Table 4-7 CHAPI
# parenthetical, which is a different exclusion; no other check reads the figure split.
BRANCH_EXCLUDED = (
    (r"fig49b|limited use",),
    (r"army|a af|air force|fig49b",),
    (r"exclud|not applicab|does not apply|do not apply|not apply|outside|out of scope|"
     r"must not|inapplicab|do not use|not used|not governing|separate (controlling )?figure|"
     r"for that class|scope mismatch|branch does not|not .{0,20}(this facility|an? n mc)|"
     r"is not .{0,25}(applicable|governing|controlling)|do(es)? not match",),
)

# Golden unresolved_or_out_of_scope[1]: "Obstacle penetrations and property or land-use
# control cannot be verified without site records."  Source-bound in the record at
# current_airfield_criteria.pdf Table 4-2 footnote **.  No other check reads land use,
# property control, ownership, zoning or a parcel.
LAND_USE_OPEN = (
    (r"land.?use|land control|property control|property record|property or land|"
     r"property/land|ownership of|cadastral|zoning|\bparcel\b|easement|aicuz|compatible use|"
     r"property interest|property and land|property, land",),
    (r"cannot be verif|cannot be establish|cannot .{0,25}(verif|establish|confirm)|not verif|"
     r"unverif|unresolved|out of scope|outside|\bobtain\b|\brequires?\b|\brequired\b|"
     r"pending|not supplied|no .{0,25}record|\bcannot\b",),
)
LAND_USE_CLOSED = (r"closes|positively rather than",)

# Golden findings[8].disposition: "Raise a criteria clarification; do not choose one
# metric value or convert the reference value silently."  Charged when the report
# settles the 42.72 / 45.72 conflict on one value instead of holding it.
ELEVATION_REFUSAL = (r"(do not|don't|does not|must not|shall not|may not|never|is not|are not|not to|"
              r"without|rather than|neither|no)\s+[^.]{0,35}"
              r"(choose|chosen|choosing|select|selecting|selected|adopt|adopted|overwrit|"
              r"convert|converted|converting|silently|silent)")
ELEVATION_SETTLED = (r"\badopt(s|ed|ing)?\b|\bresolves?\b|is resolved|\bcorrect(ed|s)? to\b|"
              r"\btake[sn]?\b .{0,20}(42\.72|45\.72)|\buse\b .{0,20}(42\.72|45\.72) as|\bsupersed")
ELEVATION_REFERRED_OUT = (r"authority|\bsme\b|coordinat|clarif|criteria owner|\brfi\b|\buntil\b|\bbefore\b|"
                   r"request|would produce|if adopted|must be resolved|to be resolved|shall be resolved")
ELEVATION_HELD = r"hold|unresolved|pending|clarif|do not|must not|cannot|conflict remains|not resolved|neither"


def terminal_elevation_settled(report: dict) -> bool:
    for _, text in stmt_fields(report):
        for sentence in STATEMENT_SENTENCE.split(text):
            if not (stmt_number_in(sentence, 42.72) or re.search(r"terminal .{0,12}(elevation|height)", sentence)):
                continue
            if not re.search(ELEVATION_SETTLED, sentence):
                continue
            if re.search(ELEVATION_REFUSAL, sentence) or re.search(ELEVATION_HELD, sentence):
                continue
            if re.search(ELEVATION_REFERRED_OUT, sentence):
                continue
            return True
    return False


# Golden review_basis.conditional_decision: "The east normal case is fully dimensioned."
# Charged when the east controlling surface is instead held for an authority decision,
# drawn at the other facility class's 265.18 m terminal width, or drawn twice with no
# selection.  Not covered by P04, which matches only the expected polygon and ignores
# rival ones, and not by conclusion_reversal_rate, which has no east-surface family.
EAST_SUBJECT = (r"chapi|adcs|approach.departure|clearance surface|fig49a|table4x7",)
EAST_WEST_ONLY = (r"\bwest\b|non standard|8 degree|lowest on course|signal angle",)
EAST_AUTHORITY = (r"\bdha\b|defense health|hospital|criteria authority|criteria owner|"
                     r"design authority|service sme|"
                     r"authority (concurrence|adjudicat|interpretation|determination)",)
EAST_HOLD = (r"\bhold\b|\bconfirm|verif|subject to|pending|before issue|"
                r"adjudicat|concurrence|interpretation|determination",)
EAST_OBJECT = (r"applicab|status|width|dimension|geometry|before issue|final|"
                  r"selection|envelope|\buse\b|using|value",)
EAST_CLEAN_EXCLUSION = (r"does not (apply|match)|not applicable|exclud",)


def east_offered_polygons(dxf_path: Path) -> list[float]:
    """Terminal half-widths of the closed polygons the drawing offers as the east ADCS."""
    try:
        doc = dxfreader.readfile(dxf_path)
    except Exception:
        return []
    offered = []
    for entity in doc.modelspace():
        if entity.dxftype() not in {"LWPOLYLINE", "POLYLINE"} or not closed_entity(entity):
            continue
        points = entity_points(entity)
        if len(points) < 3:
            continue
        xs = [point[0] for point in points]
        ys = [abs(point[1]) for point in points]
        if not (max(xs) > 700.0 and min(xs) > -50.0):
            continue
        layer = stmt_norm(entity.dxf.layer)
        if not stmt_any(layer, (r"adcs|approach|chapi|app dep|clearance|\beast\b|\be\b$",)):
            continue
        if stmt_any(layer, (r"transition|titleblock|title|border|frame|grid|sheet|annot|text|note|dim",)):
            continue
        offered.append(round(max(ys), 2))
    return offered


def east_unsettled(report: dict, dxf_path: Path, expected_half_width: float, semantic=None) -> bool:
    offered = sorted(set(east_offered_polygons(dxf_path)))
    if len(offered) > 1:
        return True
    if offered and abs(offered[0] - expected_half_width) > 0.6:
        return True
    if semantic is not None: return bool(semantic)
    for _, text in stmt_fields(report):
        for sentence in STATEMENT_SENTENCE.split(text):
            if not stmt_any(sentence, EAST_SUBJECT):
                continue
            if stmt_any(sentence, EAST_WEST_ONLY) and not re.search(r"\beast\b", sentence):
                continue
            if not stmt_any(sentence, EAST_AUTHORITY):
                continue
            if not stmt_any(sentence, EAST_HOLD):
                continue
            if not stmt_any(sentence, EAST_OBJECT):
                continue
            if stmt_any(sentence, EAST_CLEAN_EXCLUSION):
                continue
            return True
    return False


def statement_bound_items(report: dict, dxf_path: Path, values: dict[str, float]) -> tuple[dict[str, float], list[tuple[str, list[str]]]]:
    """The statement-bound items: (completions for P08/P09, damage instances for D02/D03)."""
    from semantic_judge import adjudicate
    source=json.loads(Path(__file__).with_name("semantic_source.json").read_text())
    semantic=adjudicate(json.dumps(report,ensure_ascii=False,indent=2),source)["items"]
    fields = stmt_fields(report)
    completion = {
        "P08": 1.0 if stmt_sentence_hit(fields, BRANCH_EXCLUDED) else 0.0,
        "P09": float(semantic["P09"]["fraction"]),
    }
    damage: list[tuple[str, list[str]]] = []
    if terminal_elevation_settled(report):
        damage.append(("terminal-elevation conflict settled on one value instead of held", ["D02"]))
    if east_unsettled(report, dxf_path, values["normal_chapi_end_width"] / 2.0, semantic["EAST_HOLD"]["fraction"]):
        damage.append(("east normal-CHAPI controlling surface left unsettled", ["D03"]))
    return completion, damage



def score(output_dir: Path, _skip_integrity_gate: bool = False) -> dict[str, Any]:
    ground_truth_path = Path(__file__).with_name("ground_truth.json")
    if not ground_truth_path.is_file():
        return empty_result("missing ground_truth.json")
    truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    values = {key: float(value) for key, value in truth["expected_values"].items()}
    # The harness invokes this file from different mount points (for example
    # `/tests/validator.py` in the rollout container and the package tree
    # during local scoring).  Resolve locked inputs from the submission's
    # workspace first, then from package-relative fallbacks without assuming
    # that a fixed number of parent directories exists.
    validator_path = Path(__file__).resolve()
    workspace_candidates: list[Path] = [output_dir.parent]
    for candidate in (
        output_dir.parent / "task/environment/workspace",
        output_dir.parent / "environment/workspace",
        validator_path.parent.parent / "environment/workspace",
        Path("/workspace"),
    ):
        if candidate not in workspace_candidates:
            workspace_candidates.append(candidate)
    source_errors = []
    for name, expected_hash in truth["locked_inputs"].items():
        source = next((root / name for root in workspace_candidates if (root / name).is_file()), workspace_candidates[0] / name)
        if not source.is_file() or sha256(source) != expected_hash:
            source_errors.append(name)
    if source_errors and not _skip_integrity_gate:
        return empty_result("source integrity failure: " + ", ".join(source_errors))

    report_path = output_dir / "inspection_report.json"
    memo_path = output_dir / "repair_memo.md"
    dxf_path = output_dir / "repaired_plan.dxf"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("top-level JSON must be an object")
    except Exception as exc:
        report = {}
        report_error = str(exc)
    else:
        report_error = None
    try:
        memo = memo_path.read_text(encoding="utf-8")
    except Exception:
        memo = ""

    report_records = records(report)
    report_text = canonical(report)
    memo_text = canonical(memo)

    applicability_checks = {
        # The classification must carry the per-end visual-aid condition, not just the
        # service and facility names, because the per-end condition is what selects the
        # controlling clearance surface later.
        "service_facility_branch": bool(find_record(
            report_records,
            ((r"navy and marine corps",), (r"standard vfr", r"standard visual flight"),
             (r"chapi",), (r"normal",), (r"non.standard",)),
            (values["east_chapi_guide_angle"], values["west_chapi_guide_angle"]),
        )),
        "nearby_conditional_branch_excluded": evidence_located(find_record(
            report_records,
            ((r"table 4-7",), (r"hospital", r"defense health", r"different facility", r"another facility")),
            decisions=(r"exclude", r"not appl", r"does not displace", r"not import", r"scoped"),
        )),
        # Naming both files is not a conclusion; the submission must pin the status
        # decision to the revision evidence that establishes it.
        "document_status_resolved": evidence_located(find_record(
            report_records,
            ((r"legacy_airfield_criteria\.pdf",), (r"current_airfield_criteria\.pdf",),
             (r"change summary", r"change 2", r"physical (?:pages?|pp?\.?)\s*8")),
            decisions=(r"baseline", r"under inspection", r"control", r"govern", r"supersed", r"repair"),
        )),
        "per_end_condition_separated": evidence_located(find_record(
            report_records,
            ((r"east",), (r"west",), (r"chapi",), (r"normal",), (r"non.standard",)),
            decisions=(r"differ", r"per.end", r"asymmetr", r"not mirror", r"separate"),
        )),
        # The east end must be dispositioned as a repair onto the figure values; a
        # record that says the legacy surface still governs states the opposite
        # conclusion from the same numbers and must not score here.
        "east_normal_condition_resolved": evidence_located(find_record(
            report_records,
            ((r"east",), (r"normal",), (r"chapi",), (r"4-9a", r"service.specific figure")),
            (values["east_chapi_guide_angle"], values["normal_chapi_slope"], values["normal_chapi_length"], values["normal_chapi_end_width"]),
            decisions=(r"control", r"govern", r"repair", r"replace", r"draw"),
            direction="repair",
        )),
        "west_adjustment_required": evidence_located(find_record(
            report_records,
            ((r"west",), (r"non.standard",), (r"chapi",), (r"adjust", r"lowest on.course")),
            (values["west_chapi_guide_angle"],),
            decisions=(r"required?\b", r"\bhold\b", r"unresolved", r"obtain", r"must be"),
            extra_groups=((r"not state", r"not supplied", r"missing", r"obtain", r"unresolved", r"design hold"),),
        )),
        "west_hold_decision": (
            all(term in report_text for term in ("west", "chapi", "lowest on-course"))
            and has_number(report_text, values["figure_adjustment_terminal_m"])
            and has_number(report_text, values["table_terminal_elevation_m"])
            and has_any(report_text, (r"design hold", r"unresolved"))
            and has_any(report_text, (r"do not (?:infer|mirror|draw)", r"no controlling polygon", r"criteria clarification"))
        ),
    }
    applicability_points = 0.24 * sum(applicability_checks.values()) / len(applicability_checks)

    retained = RETAIN_CUES
    repaired = REPAIR_CUES
    claimed: set[int] = set()
    # Every per-item finding must be a source-bound record that states the correct
    # disposition direction.  Without ``direction`` a record that reverses the call
    # keeps the credit, and without ``sourced`` the dimensional-basis block - which
    # lists every value at once and cites nothing - satisfies the per-item searches.
    finding_records = {
        "pad_retained": claim_compound_record(report_records, claimed, ((r"helipad", r"pad size"),), (values["pad_size"],), retained, ((r"square", r"\bx\b"),), direction="retain", sourced=True),
        "primary_retained": claim_compound_record(report_records, claimed, ((r"primary surface",),), (values["primary_size"],), retained, ((r"center",),), direction="retain", sourced=True),
        "clear_length_retained": claim_compound_record(report_records, claimed, ((r"clear.zone",), (r"length",)), (values["clear_zone_length"],), retained, ((r"primary.surface edge", r"primary edge"), (r"each", r"both", r"reciprocal")), direction="retain", sourced=True),
        "apz_length_retained": claim_compound_record(report_records, claimed, ((r"apz i",), (r"length", r"continu")), (values["apz_length"],), retained, ((r"clear.zone",),), direction="retain", sourced=True),
        "apz_width_repaired": claim_compound_record(report_records, claimed, ((r"apz i",), (r"width", r"envelope", r"flare")), (values["legacy_apz_width"], values["apz_start_width"], values["apz_end_width"]), repaired, ((r"constant", r"uniform"), (r"flare", r"widen", r"start.*end")), direction="repair", sourced=True),
        "clear_width_repaired": claim_compound_record(report_records, claimed, ((r"clear.zone",), (r"width", r"envelope", r"flare")), (values["legacy_clear_zone_width"], values["clear_zone_start_width"], values["clear_zone_end_width"]), repaired, ((r"constant", r"uniform"), (r"flare", r"widen", r"start.*end")), direction="repair", sourced=True),
        # The skill may emit separate slope, length, and terminal-width topics;
        # the final group therefore accepts the attribute noun as well as the
        # combined clearance-surface label.
        "east_chapi_surface_repaired": claim_compound_record(report_records, claimed, ((r"east",), (r"chapi",), (r"clearance surface", r"adcs", r"approach.departure", r"slope", r"length", r"width", r"terminal")), (values["legacy_adcs_slope"], values["legacy_adcs_length"], values["legacy_adcs_end_width"], values["normal_chapi_slope"], values["normal_chapi_length"], values["normal_chapi_end_width"]), repaired, ((r"normal",), (r"positive.x", r"east")), direction="repair", sourced=True),
        "west_chapi_design_hold": claim_record(report_records, claimed, ((r"west",), (r"non.standard",), (r"chapi",), (r"lowest on.course",)), (values["west_chapi_guide_angle"],), (r"design hold", r"unresolved", r"do not infer", r"do not mirror", r"may be (?:inferred|mirrored)", r"be obtained"), ((r"not state", r"not supplied", r"missing", r"obtain", r"never stated"),), sourced=True),
        "terminal_elevation_conflict": claim_record(
            report_records,
            claimed,
            ((r"terminal.elevation",), (r"conflict", r"discrep", r"inconsisten", r"clarification")),
            (values["figure_adjustment_terminal_m"], values["table_terminal_elevation_m"], 150.0),
            (r"\bhold\b", r"unresolved", r"clarif", r"do not choose", r"may (?:not )?be chosen"),
            ((r"clarif", r"do not choose", r"coordinate", r"may not be chosen"),),
            sourced=True,
        ),
        "per_end_geometry_disposition": claim_record(report_records, claimed, ((r"east",), (r"west",), (r"clear.zone",), (r"apz i",), (r"chapi",)), decisions=(r"draw", r"plot", r"repair", r"partial", r"\bhold\b"), extra_groups=((r"reciprocal",), (r"not mirror", r"no .{0,20}mirror", r"non.controlling", r"\bhold\b"), (r"design.hold", r"non.controlling", r"in place of mirrored", r"instead of mirrored")), sourced=True),
        # Exclusion is only a conclusion when it names the basis for excluding.
        "apz_ii_excluded": claim_record(report_records, claimed, ((r"apz ii",), (r"rotary.wing", r"helicopter", r"vertical.lift")), decisions=(r"exclude", r"not applic", r"does not apply", r"do not add", r"must not be added"), sourced=True),
        "transitional_surface_scope_hold": claim_record(
            report_records,
            claimed,
            ((r"transitional surface", r"surface h"),),
            (2.0, 1.0),
            decisions=(r"scope hold", r"unresolved", r"do not draw", r"no .*polygon", r"pending"),
            extra_groups=((r"profile", r"elevation", r"section data"),
                          (r"plan.view", r"polygon", r"boundary")),
            sourced=True,
        ),
        # Scored on one distinct source-bound record rather than on the union of every
        # record that happens to contain a hedging word.
        "plan_limits_unresolved": claim_record(
            report_records,
            claimed,
            ((r"grade",), (r"elevation",), (r"obstacle", r"penetration"), (r"survey", r"profile", r"plan view")),
            decisions=(r"unresolved", r"cannot", r"pending", r"not certif", r"not determin", r"until survey"),
            sourced=True,
        ),
    }
    finding_checks = {name: bool(text) for name, text in finding_records.items()}
    findings_points = 0.36 * sum(finding_checks.values()) / len(finding_checks)

    evidence_checks = {
        # Scored on one record that carries both documents, the status call and its
        # location, not on the union of the whole report: a filename in one place and a
        # page number in another is a shared bibliography, not a traced decision.
        "control_and_scope": bool(find_record(
            report_records,
            ((r"legacy_airfield_criteria\.pdf",), (r"current_airfield_criteria\.pdf",),
             (r"physical (?:pages?|pp?\.?)\s*8", r"change summary", r"figure 4-9a")),
            decisions=(r"control", r"govern", r"baseline", r"under inspection"),
        )),
        "clear_zone_change": source_bound(finding_records["clear_width_repaired"], r"legacy_airfield_criteria\.pdf", (r"(?:pages?|pp?\.?)\s*90", r"figure 4-9")) and source_bound(finding_records["clear_width_repaired"], r"current_airfield_criteria\.pdf", (r"(?:pages?|pp?\.?)\s*96", r"figure 4-9a", r"table 4-2")),
        "apz_change": source_bound(finding_records["apz_width_repaired"], r"legacy_airfield_criteria\.pdf", (r"(?:pages?|pp?\.?)\s*90", r"figure 4-9")) and source_bound(finding_records["apz_width_repaired"], r"current_airfield_criteria\.pdf", (r"(?:pages?|pp?\.?)\s*96", r"figure 4-9a", r"table 4-2")),
        "east_chapi_change": source_bound(finding_records["east_chapi_surface_repaired"], r"legacy_airfield_criteria\.pdf", (r"(?:pages?|pp?\.?)\s*112", r"table 4-7")) and source_bound(finding_records["east_chapi_surface_repaired"], r"current_airfield_criteria\.pdf", (r"figure 4-9a", r"(?:page|p\.?)\s*106")),
        "west_adjustment_hold": source_bound(finding_records["west_chapi_design_hold"], r"current_airfield_criteria\.pdf", (r"figure 4-9a", r"(?:page|p\.?)\s*106", r"notes?\s*(?:3|6)")),
        "terminal_conflict": source_bound(finding_records["terminal_elevation_conflict"], r"current_airfield_criteria\.pdf", (r"figure 4-9a", r"(?:page|p\.?)\s*106")) and has_any(finding_records["terminal_elevation_conflict"], (r"table 4-7", r"item 11", r"(?:page|p\.?)\s*123")),
        "unresolved_boundary": source_bound(finding_records["plan_limits_unresolved"], r"current_airfield_criteria\.pdf", (r"table 4-2", r"figure 4-9a", r"(?:pages?|pp?\.?)\s*96", r"(?:page|p\.?)\s*106")),
    }
    evidence_points = 0.15 * sum(evidence_checks.values()) / len(evidence_checks)

    geometry_points, geometry_checks = dxf_score(dxf_path, values)
    checks_geometry = geometry_checks

    # The basis is a section, not a sentence: read it from whole subtrees as well,
    # so nesting the dimensions below the origin/axis/units line is not a failure.
    basis = find_record(
        report_records + subtree_records(report),
        # Field names are an interchange detail. Accept ordinary equivalents
        # while still requiring the three meanings and the dimensional values.
        ((r"origin", r"coordinate(?:s)?", r"reference point"),
         (r"axis(?:es)?", r"direction", r"orientation"),
         (r"units?", r"unit system", r"metric", r"metres?", r"meters?")),
        tuple(values[key] for key in (
            "pad_size", "primary_size", "clear_zone_length", "clear_zone_start_width", "clear_zone_end_width",
            "apz_length", "apz_start_width", "apz_end_width", "normal_chapi_slope", "normal_chapi_length", "normal_chapi_end_width",
        )),
        extra_groups=((r"east",), (r"west",), (r"design hold", r"unresolved")),
    )
    memo_numbers = all(
        has_number(memo_text, values[key])
        for key in (
            "pad_size", "primary_size", "clear_zone_length", "clear_zone_start_width", "clear_zone_end_width",
            "apz_length", "apz_start_width", "apz_end_width", "normal_chapi_slope", "normal_chapi_length", "normal_chapi_end_width",
        )
    )
    memo_conflict = (
        has_number(memo_text, values["figure_adjustment_terminal_m"])
        and has_number(memo_text, values["table_terminal_elevation_m"])
        and has_number(memo_text, 150.0)
    )
    closure_checks = {
        "report_basis_matches_repaired_geometry": bool(basis) and geometry_checks.get("east_chapi_adcs", {}).get("matched") == 1 and geometry_checks.get("west_normal_chapi_absent") and geometry_checks.get("west_design_hold_annotation"),
        # Both directions are read from the same cue lists the findings dimension uses,
        # so "unchanged", "kept" and "conforms" count on the retain side exactly as the
        # repair synonyms count on the other.
        "memo_distinguishes_retained_and_repaired": memo_numbers and has_any(memo_text, retained) and has_any(memo_text, repaired) and "reciprocal" in memo_text and "east" in memo_text,
        "west_hold_carried_to_memo": all(term in memo_text for term in ("west", "chapi", "design hold", "lowest on-course")) and memo_conflict and has_any(memo_text, (r"no mirrored", r"no .*polygon", r"not completed")),
        # The memo side accepts the same terms the per-finding check for this limit
        # reads, plus `obstruction`, which is the term the supplied criteria use.
        "open_limits_carried_to_memo": all(term in memo_text for term in ("grade", "elevation")) and has_any(memo_text, (r"obstacle", r"penetrat", r"obstruct")) and has_any(memo_text, (r"unresolved", r"cannot", r"require")),
    }
    closure_points = 0.02 * closure_checks["report_basis_matches_repaired_geometry"] + 0.01 * closure_checks["memo_distinguishes_retained_and_repaired"] + 0.01 * closure_checks["west_hold_carried_to_memo"] + 0.01 * closure_checks["open_limits_carried_to_memo"]

    point_scores = {
        "applicability_and_control": round(applicability_points, 6),
        "professional_findings": round(findings_points, 6),
        "evidence_traceability": round(evidence_points, 6),
        "repaired_geometry": round(geometry_points, 6),
        "cross_deliverable_closure": round(closure_points, 6),
    }
    # Geometry, traceability and closure carry no directional content, so a
    # submission that reverses every call keeps them whole.  Withdraw that
    # undirected credit in proportion to how systematic the reversal is.
    reversal_rate, reversal_detail = conclusion_reversal(report_records, values)
    for name in REVERSAL_IMMUNE_DIMENSIONS:
        point_scores[name] = round(point_scores[name] * (1.0 - reversal_rate), 6)
    # The pd-ledger settlement reads:
    #  - the twelve findings split into Golden's own three status classes (retain
    #    compliant / repair nonconforming / hold, exclude or leave unresolved): each
    #    class keeps its own checks and its share of the weight;
    #  - P08 and P09, the two reference units the dimension checks do not read;
    #  - D02 and D03, the two evidenced errors, and D04, the mirrored-west void.
    statement_completion, statement_damage = statement_bound_items(report, dxf_path, values)
    reversal_factor = 1.0 - reversal_rate
    finding_completion = {
        item: (sum(bool(finding_checks[name]) for name in group) / len(group))
        for item, group in FINDING_GROUPS.items()
    }
    geometry_completion = (checks_geometry.get("geometry_points_before_mirror_void", 0.0)
                           * reversal_factor / WEIGHTS["repaired_geometry"])
    ledger_completion = {
        "P01": point_scores["applicability_and_control"] / WEIGHTS["applicability_and_control"],
        "P03": point_scores["evidence_traceability"] / WEIGHTS["evidence_traceability"],
        "P04": geometry_completion,
        "P05": point_scores["cross_deliverable_closure"] / WEIGHTS["cross_deliverable_closure"],
    }
    ledger_completion.update(finding_completion)
    ledger_completion.update(statement_completion)
    ledger_damage = ([("source integrity failure: " + ", ".join(source_errors), ["D01"])] if source_errors else [])
    ledger_damage += statement_damage
    if not checks_geometry.get("west_normal_chapi_absent", True):
        ledger_damage.append(("mirrored west normal-CHAPI clearance surface drawn", ["D04"]))
    return {
        "_parts": {"completion": ledger_completion, "damage": ledger_damage},
        "dimension_scores": {
            name: round(point_scores[name] / WEIGHTS[name], 6)
            for name in WEIGHTS
        },
        "details": {
            "score_contributions": point_scores,
            "statement_bound_items": {"completion": statement_completion,
                                "damage": [key for key, _ in statement_damage]},
            "conclusion_reversal_rate": round(reversal_rate, 6),
            "conclusion_reversal_detail": reversal_detail,
            "report_error": report_error,
            "checks": {
                "applicability_and_control": applicability_checks,
                "professional_findings": finding_checks,
                "evidence_traceability": evidence_checks,
                "repaired_geometry": geometry_checks,
                "cross_deliverable_closure": closure_checks,
            },
            "source_integrity": True,
            "verification_level": "deterministic source-bound decision, evidence, and parsed DXF geometry scoring",
        },
    }


# ---------------------------------------------------------------------------
# pd-ledger-v1 settlement.
PARAMS = Path(os.environ.get("SCORING_PARAMS", Path(__file__).resolve().parent / "scoring_params.json"))
ZERO_PARTS = {"completion": {}, "damage": []}
DELIVERABLES = ("inspection_report.json", "repair_memo.md", "repaired_plan.dxf")


def deliverable(arg: str) -> Path:
    """The output directory: the container passes it; the contract passes rollout artifacts/ or task golden/."""
    p = Path(arg)
    if p.is_file():
        return p.parent
    if not p.is_dir() or any((p / name).is_file() for name in DELIVERABLES):
        return p
    for name in DELIVERABLES:
        found = sorted(p.glob("**/" + name))
        if found:
            return found[0].parent
    return p


def graded(output_dir: Path) -> dict[str, Any]:
    """The scored result; when the integrity gate zeroes it, the completions are still computed (same code)."""
    result = score(output_dir)
    if str(result.get("details", {}).get("error", "")).startswith("source integrity failure"):
        result["_parts"] = score(output_dir, _skip_integrity_gate=True)["_parts"]
    # Required-deliverable gate. The brief names three deliverables, and the drawing's own items carry
    # little weight, so without this gate a submission that shipped no repaired_plan.dxf could still
    # score high. A missing or empty required deliverable is not a partial answer.
    missing = [name for name in DELIVERABLES
               if not (output_dir / name).is_file() or (output_dir / name).stat().st_size == 0]
    if missing:
        parts = result.get("_parts") or {"completion": {}, "damage": []}
        result["_parts"] = {"completion": {k: 0.0 for k in parts.get("completion", {})},
                            "damage": list(parts.get("damage", []))}
        result.setdefault("details", {})["deliverable_gate"] = {"missing": missing, "effect": "all positive completion set to 0"}
    return result


def settle(result: dict[str, Any]) -> dict[str, Any]:
    """Settle the scored result as pd-ledger-v1."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    parts = result.pop("_parts", ZERO_PARTS)
    completion = {k: round(min(1.0, max(0.0, float(parts["completion"].get(k, 0.0)))), 10) for k in weights}
    instances = [{"key": key, "item_ids": items} for key, items in parts["damage"]]
    earned = sum(weights[k] * completion[k] for k in weights)
    retention = math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances)
    final = earned * retention
    lenient, lenient_required = lenient_lens(completion, instances)
    result["reward"] = final
    result["rewards"] = {"strict": final, "lenient": lenient}
    result["lenient_required"] = lenient_required
    result["reward_formulas"] = {
        "lenient": "1.0 if every item in LENIENT_REQUIRED_ITEMS holds on its own ledger result "
                   "(positive item at full completion, deduction item never charged) else 0.0",
        "strict": "positive_earned * retention (pd-ledger-v1); positive_earned = sum(w_i * completion_i) over "
                  "P01-P09; retention = product over damage instances (D01 locked criteria source integrity, "
                  "D02 terminal-elevation conflict settled instead of held, D03 east normal-CHAPI surface left "
                  "unsettled, D04 mirrored west normal-CHAPI surface drawn) of the item coefficient; weights "
                  "and coefficients from scoring_params.json"}
    result["scoring_ledger"] = {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                                "damage_instances": instances, "positive_earned": earned,
                                "retention": retention, "final_score": final}
    return result


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validator.py OUTPUT_DIRECTORY", file=sys.stderr)
        return 2
    target = deliverable(sys.argv[1])
    print(json.dumps(settle(graded(target)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

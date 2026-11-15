#!/usr/bin/env python3
"""Condition-blind deterministic scorer for the claim-version chart (pd-ledger-v1).

Usage: validator.py <answer>
  <answer> is claim_chart.json, or a directory holding it (rollout artifacts/ or task golden/);
  default /workspace/claim_chart.json.

The strict score is settled in the standard form
  final = positive_earned * retention
  positive_earned = sum(weight[P] * completion[P])      (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

P01-P08 are the eight group cores of the chart: published chart, same-number claim mapping, evidence
bridges, claim construction, sensitivity, dependency audit, family correspondence and issued-claim
comparisons. Completion is the group core times the continuous multiplier M = inversion_factor * product
of the twelve coverage fractions * (0.55 + 0.45 * terminal_call_accuracy * analysis_completeness); these
scale the whole sum and are folded in, not deductions. D01 is the no_dump gate (PASS or FAIL declared on
>= 90% of comparisons); it fires as one damage instance at grid coefficient 0.1, and the completions are
still computed, so 0.1 acts on real earned credit. D02-D09 charge affirmative determinations the record
does not support. An unreadable deliverable returns a ledger with every completion 0. rewards.lenient is
a separate binary lens over the same results: every item in LENIENT_REQUIRED_ITEMS has to clear on the
value the strict scorer already computed for it.
"""
from __future__ import annotations
import re

import json
import math
import os
import sys
from pathlib import Path

# --- disowned-unit guard ---------------------------------------------------------------------------
# A unit the submission itself withdraws is not an assertion. The withdrawal must GOVERN THE WHOLE
# UNIT, so the cue is anchored at the start of the unit (after any bullet, quote or table marker) or
# is a quote-and-reject wrapper around it. An unanchored match would charge correct work: a sentence
# such as "it is expressly not asserted as structuring on the present record" is a careful, correct
# finding about a different allegation, not a withdrawal of the whole value. Domain words such as "rejected",
# "withdrawn", "superseded" or "hypothetical" are never cues: they describe the subject matter.
_DISOWN_LEAD = r"^[\s>|*\-–—•·\d.、)）\]】\"'“”‘’]{0,12}"
_DISOWN_RE = re.compile(
    _DISOWN_LEAD + r"(?:"
    r"the following is not asserted(?: here)?|not asserted here\b|"
    r"tentative,?\s*not adopted|not adopted\s*[:：]|unadopted\s*[:：]|"
    r"the draft (?:asserted|stated)\b|"
    r"candidate only\s*[:：]|filed as (?:a )?candidate\b|for discussion only\s*[:：]|"
    r"以下(?:内容)?(?:并非|不是)本方(?:主张|结论)|以下并非|以下不主张|"
    r"疑似(?=[^\n]{0,80}(?:尚未采纳|待核))|"
    r"原稿(?:主张|记载|曾称)|"
    r"并非(?=\S)|"
    r"暂定[，,：:]|候选[，,：:]|未采纳[，,：:]"
    r")", re.I)


def _guard_deliverable_json(node):
    """Blank every string the submission disowns; structure, numbers and identifiers are untouched."""
    if isinstance(node, dict):
        return {k: _guard_deliverable_json(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_guard_deliverable_json(v) for v in node]
    if isinstance(node, str) and (_DISOWN_RE.search(node) or node.lstrip().startswith("并非")):
        return ""   # a value that is the negation of a label ("并非X") is not that label
    return node


HERE = Path(__file__).resolve().parent
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# Lenient lens: the four things this claim chart cannot be handed to counsel without.
#
# The brief says the deliverable "must conform to /workspace/analysis_contract.json and
# cover its designated published and issued comparisons, ... construction dependencies,
# and sensitivity cases", and must "Support substantive judgments with supplied-document
# locators and concise reasons, and include a short assumptions_and_scope collection";
# it also says to treat the result as triage. So:
#   contract_row_coverage  - every designated row/comparison/mapping the contract names is
#                            actually delivered (the eleven row-coverage fractions, plus
#                            each same-number mapping row carrying its three columns)
#   analysis_completeness  - the locators, reasons and assumptions_and_scope the brief names
#   terminal_call_accuracy - every comparison's bottom line matches the record; a chart whose
#                            infringement calls are wrong is the one thing counsel cannot use
#   D01                    - not a blanket call; one definite verdict stamped on everything
#                            is not triage, whichever verdict it is
# Deliberately NOT required: evidence_binding == 1 (per-finding sourcing quality is a depth
# quota, not a usability gate) and the register cores (they are continuous depth scores).
# Each item is read from the value the strict scorer already computed for it; the strict
# ledger is untouched.
LENIENT_REQUIRED_ITEMS = [
    "contract_row_coverage",
    "analysis_completeness",
    "terminal_call_accuracy",
    "D01",
]


def load_answer(path: Path) -> dict:
    if path.is_dir():
        path = path / "claim_chart.json"
    value = _guard_deliverable_json(json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(value, dict):
        raise ValueError("the deliverable root must be a JSON object")
    return value


def rows_from(raw: object) -> list[dict]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if not isinstance(raw, dict):
        return []
    rows = []
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        row = dict(value)
        parts = str(key).replace("/", "::").split("::")
        if len(parts) == 2:
            row.setdefault("target_id", parts[0])
            row.setdefault("claim_id", parts[1])
        else:
            row.setdefault("claim_id", str(key))
        rows.append(row)
    return rows


def index_comparisons(raw: object) -> dict[tuple[str, str], dict]:
    out = {}
    for row in rows_from(raw):
        target = str(row.get("target_id", row.get("target", ""))).strip()
        claim = str(row.get("claim_id", row.get("claim", ""))).strip()
        if target and claim and (target, claim) not in out:
            out[(target, claim)] = row
    return out


def index_claim_rows(raw: object) -> dict[str, dict]:
    out = {}
    for row in rows_from(raw):
        claim = str(row.get("claim_id", row.get("claim", ""))).strip()
        if claim and claim not in out:
            out[claim] = row
    return out


def index_id_rows(raw: object, id_field: str, *aliases: str) -> dict[str, dict]:
    if isinstance(raw, list):
        rows = [row for row in raw if isinstance(row, dict)]
    elif isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault(id_field, str(key))
                rows.append(row)
    else:
        rows = []
    out = {}
    for row in rows:
        value = next((row[key] for key in (id_field,) + aliases if key in row), "")
        identifier = str(value).strip()
        if identifier and identifier not in out:
            out[identifier] = row
    return out


def finding_index(row: dict, issued: bool = False) -> dict[str, dict]:
    keys = ("feature_findings", "findings", "elements", "limitations") if issued else (
        "findings", "elements", "limitations"
    )
    raw = next((row[key] for key in keys if key in row), [])
    # Finding identifiers are resolved by identity, like every other row lookup in
    # this file (index_comparisons, index_claim_rows, index_id_rows and list_value
    # all strip). Surrounding whitespace is not part of an identifier, and a blank
    # identifier is not an identifier at all, so it registers nothing.
    if isinstance(raw, dict):
        return {
            str(key).strip(): value
            for key, value in raw.items()
            if isinstance(value, dict) and str(key).strip()
        }
    out = {}
    for finding in raw if isinstance(raw, list) else []:
        if not isinstance(finding, dict):
            continue
        key = finding.get("feature_ref" if issued else "element_id")
        if key is None:
            key = finding.get("element_id", finding.get("feature_ref", finding.get("row_id")))
        if key is not None and str(key).strip():
            out.setdefault(str(key).strip(), finding)
    return out


def list_value(row: dict, *keys: str) -> list[str]:
    value = next((row[key] for key in keys if key in row), [])
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def call_value(row: dict) -> str:
    return str(row.get("terminal_call", row.get("overall", row.get("verdict", "")))).strip().upper()


def class_value(row: dict) -> str:
    return str(row.get("evidence_class", row.get("status", row.get("classification", "")))).strip().upper()


def nonempty(row: dict, key: str) -> bool:
    return isinstance(row.get(key), str) and bool(row[key].strip())


def normalize_claim_ref(value: object) -> str:
    text = str(value).strip().upper().replace("/", ":").replace("-", ":")
    parts = [part for part in text.split(":") if part]
    if len(parts) != 2:
        return text
    version, claim = parts
    if version in ("PUB", "PUBLICATION", "APPLICATION"):
        version = "PUBLISHED"
    elif version in ("ISS", "PATENT", "GRANTED"):
        version = "ISSUED"
    return f"{version}:{claim}"


def jaccard(observed: list[str], expected: list[str]) -> float:
    obs, exp = set(observed), set(expected)
    if not obs and not exp:
        return 1.0
    return len(obs & exp) / len(obs | exp) if obs | exp else 0.0


def row_jaccard(row: dict, observed: list[str], expected: list[str]) -> float:
    """Only an explicitly submitted row may earn credit for an empty expected set."""
    return jaccard(observed, expected) if row else 0.0


def version_root(answer: dict) -> dict:
    for key in ("version_impact", "claim_version_impact", "version_analysis"):
        if isinstance(answer.get(key), dict):
            return answer[key]
    return {}


def sources_bound(row: dict, target: str, version: str) -> bool:
    observed = set(list_value(row, "source_ids", "evidence_ids", "sources"))
    expected = set(GROUND["target_sources"][target][version])
    candidates = set(GROUND["target_sources"][target]["candidate"])
    claim_source = "PAT_APP" if version == "published" else "PAT_ISSUED"
    allowed = expected | candidates | {claim_source}
    if version == "issued": allowed.add("PAT_APP")  # descriptive disclosure remains usable; controlling issued-claim mapping is checked separately
    composite_ok = class_value(row) != "COMPOSITE" or bool(observed & candidates)
    extras = observed - allowed
    reason = str(row.get("reason", "")).lower()
    contextual_extras = (
        class_value(row) == "NOT_SHOWN"
        and extras <= set(GROUND["source_ids"])
        and any(cue in reason for cue in ("background", "context", "背景", "上下文"))
    )
    return (bool(observed) and expected <= observed and composite_ok
            and (not extras or contextual_extras))


# --------------------------------------------------------------------------- #
# Systematic conclusion inversion
#
# Every determination in this chart is a small closed vocabulary, and most of the
# dispositive ones are two-valued. For a two-valued field "the opposite value" and
# "the wrong value" are the same string, so a single row carries no information
# about whether the analyst inverted the question or simply got it wrong: an honest
# but mistaken chart lands on the opposite value about half the time it is wrong.
# What does carry information is a systematic excess of inversions inside one family
# of determinations. The factor below measures, per family, the share of
# inversion-capable rows that came out exactly opposite, takes the largest family
# rate, and only begins to bite above the 50% a wrong-but-honest chart would produce
# on its own.
#
# A chart that writes an unrecognised value, leaves a row out, or answers a
# three-valued field with the third value is not inversion-capable on that row and
# is excluded from both numerator and denominator.
# --------------------------------------------------------------------------- #

OPPOSITE_VALUES = {
    "call": {"PASS": "FAIL", "FAIL": "PASS"},
    "evidence_class": {"DIRECT": "NOT_SHOWN", "NOT_SHOWN": "DIRECT"},
    "link_status": {"ESTABLISHED": "NOT_ESTABLISHED", "NOT_ESTABLISHED": "ESTABLISHED"},
    "proposition_status": {"SUPPORTED": "UNRESOLVED", "UNRESOLVED": "SUPPORTED"},
    "controlling_effect": {"SUPPORTS_FEATURE": "NON_DISPOSITIVE",
                           "NON_DISPOSITIVE": "SUPPORTS_FEATURE"},
    "disposition": {"CONSTRUCTION_REQUIRED": "TEXT_RESOLVES_NO",
                    "TEXT_RESOLVES_NO": "CONSTRUCTION_REQUIRED"},
    "result_effect": {"NO_CHANGE": "CHANGES_RESULT", "CHANGES_RESULT": "NO_CHANGE"},
    "dependency_status": {"FACIALLY_INCONSISTENT": "VALID", "VALID": "FACIALLY_INCONSISTENT"},
    "expansion_policy": {"DO_NOT_REPAIR": "EXPAND", "EXPAND": "DO_NOT_REPAIR"},
    "dependency_effect": {"PRINTED_EDGE_BLOCKS_CONTROLLING_COMPARISON": "NONE",
                          "NONE": "PRINTED_EDGE_BLOCKS_CONTROLLING_COMPARISON"},
    "correspondence_status": {"ABSORBED_INTO_INDEPENDENT": "BASE_RETAINED_WITH_ADDED_LIMITATIONS",
                              "BASE_RETAINED_WITH_ADDED_LIMITATIONS": "ABSORBED_INTO_INDEPENDENT"},
}

# The families of determinations, each measured against its own denominator and
# each kept apart from the others.
INVERSION_FAMILIES = (
    "chart_calls",
    "element_classes",
    "bridges",
    "construction",
    "sensitivity",
    "dependency",
    "family",
)

INVERSION_FLOOR = 0.50
INVERSION_MIN_ROWS = 10


# --------------------------------------------------------------------------- #
# Presence-only credit
#
# Five sub-terms inside the group cores, plus analysis_completeness, ask only
# whether a row was filled in at all: a source identifier was cited, a locator
# string is non-empty, a reason sentence exists, the narrative fields are not
# blank. None of them looks at whether the adjudication written next to them is
# right, so a tidy chart with the wrong bottom line collects every one of them.
#
# They are preconditions for trusting a call, not substitutes for one, so they
# are credited in proportion to terminal-call accuracy - the chart-level result
# the deliverable exists to produce, and a quantity this scorer already
# measures. A chart that calls every comparison the way the record supports
# keeps them in full; the scaling only bites once the bottom line is wrong.
# --------------------------------------------------------------------------- #

PRESENCE_ONLY_TERMS = (
    "published_evidence_binding_present",
    "issued_evidence_binding_present",
    "bridge_support_present",
    "sensitivity_reason_present",
    "dependency_locator_and_reason_present",
    "family_locators_and_reason_present",
    "analysis_completeness",
)


# --------------------------------------------------------------------------- #
# Determinations that restate one another
#
# Several registers in this chart carry more than one column for a single
# determination: the extra columns are a table lookup away from the driving one,
# so a chart that reaches the driving judgment writes the rest without deciding
# anything further. Measured on this package's ground truth:
#
#   bridges        proposition_status and controlling_effect are each a function
#                  of link_status on all ten rows (ESTABLISHED -> SUPPORTED /
#                  SUPPORTS_FEATURE, LIMITED and NOT_ESTABLISHED -> UNRESOLVED /
#                  NON_DISPOSITIVE), which is the register's stated semantics.
#   sensitivity    baseline_call is REVIEW on all ten rows and equals the chart's
#                  own terminal call for the same pair; result_effect is
#                  CHANGES_RESULT exactly when baseline_call and hypothetical_call
#                  differ, on 10/10 rows of the ground truth.
#   dependency     expansion_policy and candidate_basis are each a function of
#                  dependency_status on all fifteen rows.
#   family         dependency_effect is a function of correspondence_status on all
#                  seven rows.
#
# Averaging such columns hands out partial credit for restating a judgment the
# chart has already been paid for, and lets a chart that got the driving column
# wrong keep two thirds of the block by writing the lookups that follow from its
# own wrong answer. Each of these blocks is therefore scored as one
# determination: the row counts when every column in the block matches the
# record, and not otherwise.
#
# Two set-valued terms are dependent in the same way and are credited in
# proportion to the determination they hang off, rather than separately:
#
#   family_correspondence.issued_expanded_feature_refs is the destination claim's
#   inherited later-version feature set - a property of the destination, not an
#   independent finding. It is the verbatim contents of the chart's own
#   version_impact mapping row for that destination on 6/7 rows of the reference.
#   It is credited in proportion to how well the row identified the destination.
#
#   granted_comparisons.decisive_feature_refs is exactly the set of features the
#   same row marks NOT_SHOWN or CONTRADICTED. A separately declared contextual
#   feature may accompany that set when its finding is correct; it never replaces
#   a missing open feature or earns independent credit. The ON claim 5 reference
#   includes the directly drawn conductor count (5.1) as such context, not a gap.
#   the skill states the same rule ("every open terminal result has a decisive
#   open feature"). It is credited in proportion to the row's own feature
#   classification accuracy.
# --------------------------------------------------------------------------- #


def inversion_tally(acc: dict, family: str, field: str, observed: str, expected: str) -> None:
    table = OPPOSITE_VALUES[field]
    if expected not in table:
        return
    opposite = table[expected]
    if observed not in (expected, opposite):
        return
    entry = acc.setdefault(family, [0, 0])
    entry[1] += 1
    if observed == opposite:
        entry[0] += 1


def inversion_rate(acc: dict) -> tuple[float, dict]:
    """Largest inversion rate over the families of determinations, each family
    measured against its own denominator. Families are kept apart so that a
    fully inverted register is not diluted by the larger registers around it,
    and a family needs enough inversion-capable rows for its ratio to mean
    anything."""
    detail = {}
    worst = 0.0
    for family in INVERSION_FAMILIES:
        inverted, capable = acc.get(family, [0, 0])
        if capable < INVERSION_MIN_ROWS:
            detail[family] = {"inverted": inverted, "inversion_capable": capable, "rate": None}
            continue
        rate = inverted / capable
        detail[family] = {"inverted": inverted, "inversion_capable": capable, "rate": round(rate, 6)}
        worst = max(worst, rate)
    return worst, detail


def coverage_gate_continuous(*coverages: float) -> float:
    """The product of the twelve coverage fractions, without the no_dump gate."""
    return math.prod(coverages)


# --------------------------------------------------------------------------- #
# Bound row/field resolution for the deduction predicates.
#
# Each register is indexed by the row identifier Golden uses, through the same
# alias tables the group cores accept, and each field is read through the alias
# list the contract admits for it. A predicate fires only on the value written at
# the matching key path; nothing is matched by scanning the document.
# --------------------------------------------------------------------------- #

FIELD_ALIASES = {
    "terminal_call": ("terminal_call", "overall", "verdict"),
    "evidence_class": ("evidence_class", "status", "classification"),
    "link_status": ("link_status", "bridge_status"),
    "proposition_status": ("proposition_status", "claim_status"),
    "controlling_effect": ("controlling_effect", "effect"),
    "disposition": ("disposition", "status"),
    "baseline_call": ("baseline_call",),
    "hypothetical_call": ("hypothetical_call", "scenario_call"),
    "result_effect": ("result_effect", "effect"),
    "dependency_status": ("dependency_status", "status"),
    "expansion_policy": ("expansion_policy", "policy"),
    "candidate_basis": ("candidate_basis", "basis"),
    "correspondence_status": ("correspondence_status", "status"),
    "dependency_effect": ("dependency_effect", "effect"),
    "same_number_scope_relation": ("same_number_scope_relation", "scope_relation"),
    "declared_parent_claim_id": ("declared_parent_claim_id",),
    "candidate_coherent_parent_claim_id": ("candidate_coherent_parent_claim_id",),
    "source_ids": ("source_ids", "evidence_ids", "sources"),
    "affected_feature_refs": ("affected_feature_refs", "feature_refs", "affected_features"),
    "affected_claim_refs": ("affected_claim_refs", "claim_refs", "affected_claims"),
    "decisive_feature_refs": ("decisive_feature_refs", "blocking_feature_refs", "decisive_features"),
    "granted_required_feature_refs": ("granted_required_feature_refs", "required_feature_refs", "issued_features"),
    "source_published_claim_ids": ("source_published_claim_ids", "published_claim_sources",
                                   "same_number_lineage", "lineage"),
    "candidate_issued_claim_ids": ("candidate_issued_claim_ids", "issued_claim_ids", "destination_claim_ids"),
    "issued_expanded_feature_refs": ("issued_expanded_feature_refs", "expanded_feature_refs", "issued_features"),
}


def field_value(row: dict, field: str):
    for key in FIELD_ALIASES.get(field, (field,)):
        if key in row:
            return row[key]
    return None


def token_of(value: object) -> str:
    return str(value if value is not None else "").strip().upper()


def id_set(value: object) -> frozenset:
    if isinstance(value, str):
        return frozenset([value.strip()]) if value.strip() else frozenset()
    if isinstance(value, list):
        return frozenset(str(item).strip() for item in value if str(item).strip())
    return frozenset()


def raw_id(value: object) -> str:
    return str(value if value is not None else "").strip()


def _published_rows(answer: dict) -> dict:
    return index_comparisons(answer.get("comparisons", answer.get("published_comparisons", [])))


def _issued_rows(answer: dict) -> dict:
    root = version_root(answer)
    return index_comparisons(root.get("granted_comparisons", root.get("issued_comparisons", [])))


def _mapping_rows(answer: dict) -> dict:
    root = version_root(answer)
    return index_claim_rows(root.get("same_number_claims",
                                     root.get("claim_deltas", root.get("claim_mappings", []))))


def _bridge_rows(answer: dict) -> dict:
    return index_id_rows(answer.get("evidence_bridges", answer.get("bridge_assessments", [])), "bridge_id")


def _construction_rows(answer: dict) -> dict:
    return index_id_rows(answer.get("construction_dependencies",
                                    answer.get("claim_construction_issues", [])), "issue_id")


def _sensitivity_rows(answer: dict) -> dict:
    return index_id_rows(answer.get("sensitivity_matrix", answer.get("outcome_sensitivity", [])), "scenario_id")


def _dependency_rows(answer: dict) -> dict:
    raw = index_id_rows(answer.get("dependency_audit", answer.get("claim_dependency_audit", [])), "claim_ref")
    return {normalize_claim_ref(key): row for key, row in raw.items()}


def _family_rows(answer: dict) -> dict:
    return index_id_rows(answer.get("family_correspondence",
                                    answer.get("claim_family_correspondence", [])), "published_claim_id")



# --------------------------------------------------------------------------- #
# Deduction predicates.
#
# Each charges an affirmative determination the chart writes that the record does
# not support - not an omission, and not a blank. D05 and D09 charge the same
# class of error in both directions. One damage instance per Golden row
# affirmatively misdecided, except where Golden itself replicates one decision
# across rows (D05).
# --------------------------------------------------------------------------- #

SENSITIVITY_CHANGES_RESULT = tuple(
    scenario for scenario, expected in GROUND["sensitivity_expected"].items()
    if expected["result_effect"] == "CHANGES_RESULT")
BRIDGES_ESTABLISHED = tuple(
    bridge for bridge, expected in GROUND["bridge_expected"].items()
    if expected["link_status"] == "ESTABLISHED")
# D06 charges a LIMITED bridge written as ESTABLISHED or NOT_ESTABLISHED.
# B_REGIONAL_GENERALIZATION is outside its scope.
BRIDGES_LIMITED = tuple(
    bridge for bridge, expected in GROUND["bridge_expected"].items()
    if expected["link_status"] == "LIMITED" and bridge != "B_REGIONAL_GENERALIZATION")
OPPOSITE_DISPOSITION = {"CONSTRUCTION_REQUIRED": "TEXT_RESOLVES_NO",
                        "TEXT_RESOLVES_NO": "CONSTRUCTION_REQUIRED"}
SPEC_EMBODIMENT_TARGET = "PI_SPEC_EMBODIMENT"
DEMOTED_CLASSES = ("NOT_SHOWN", "COMPOSITE", "CONTRADICTED")
DEPENDENCY_SEMANTIC = tuple(
    claim_ref for claim_ref, expected in GROUND["dependency_expected"].items()
    if expected["candidate_basis"] == "SEMANTIC_DEPENDENCY")
PUBLISHED_DIRECT_ANCHOR = tuple(
    (target, claim) for target, claim in (tuple(pair) for pair in GROUND["published_pairs"])
    if GROUND["expected"][target][claim]["statuses"].get("1.0") == "DIRECT"
    and target in ("ON_NCP4371", "TI_QC2_REFERENCE"))


def deduction_damage(answer: dict) -> list:
    damage = []
    sensitivity = _sensitivity_rows(answer)
    for scenario in SENSITIVITY_CHANGES_RESULT:
        row = sensitivity.get(scenario)
        if row is not None and token_of(field_value(row, "result_effect")) == "NO_CHANGE":
            damage.append(["sensitivity:%s:hypothesis_refused" % scenario, ["D02"]])
    bridges = _bridge_rows(answer)
    for bridge in BRIDGES_ESTABLISHED:
        row = bridges.get(bridge)
        if row is None:
            continue
        if (token_of(field_value(row, "link_status")) in ("LIMITED", "NOT_ESTABLISHED")
                or token_of(field_value(row, "controlling_effect")) in ("NON_DISPOSITIVE", "BLOCKS_FEATURE")):
            damage.append(["bridge:%s:established_link_denied" % bridge, ["D03"]])
    construction = _construction_rows(answer)
    for issue, expected in GROUND["construction_expected"].items():
        row = construction.get(issue)
        if row is not None and token_of(field_value(row, "disposition")) == \
                OPPOSITE_DISPOSITION.get(expected["disposition"]):
            damage.append(["construction:%s:disposition_inverted" % issue, ["D04"]])
    issued = _issued_rows(answer)
    demoted = False
    for target, claim in (tuple(pair) for pair in GROUND["issued_pairs"]):
        if target != SPEC_EMBODIMENT_TARGET:
            continue
        row = issued.get((target, claim))
        if row is None:
            continue
        findings = finding_index(row, issued=True)
        for feature in GROUND["version_mapping"][claim]["required_feature_refs"]:
            if feature in findings and token_of(field_value(findings[feature], "evidence_class")) in DEMOTED_CLASSES:
                demoted = True
    if demoted:
        # Golden carries the same spec-embodiment features into every issued claim of the
        # family, so the demotion is one decision about one record however many rows repeat it.
        damage.append(["issued:%s:spec_embodiment_demoted" % SPEC_EMBODIMENT_TARGET, ["D05"]])
    for bridge in BRIDGES_LIMITED:
        row = bridges.get(bridge)
        if row is not None and token_of(field_value(row, "link_status")) in ("ESTABLISHED", "NOT_ESTABLISHED"):
            damage.append(["bridge:%s:limited_link_polarised" % bridge, ["D06"]])
    published = _published_rows(answer)
    for target, claim in PUBLISHED_DIRECT_ANCHOR:
        row = published.get((target, claim))
        if row is None:
            continue
        finding = finding_index(row).get("1.0")
        if finding is not None and token_of(field_value(finding, "evidence_class")) in DEMOTED_CLASSES:
            damage.append(["published:%s|%s:1.0_direct_reclassified" % (target, claim), ["D07"]])
    dependency = _dependency_rows(answer)
    for claim_ref in DEPENDENCY_SEMANTIC:
        row = dependency.get(claim_ref)
        if row is not None and token_of(field_value(row, "candidate_basis")) == "PARALLEL_CLAIM_FAMILY":
            damage.append(["dependency:%s:candidate_basis_misattributed" % claim_ref, ["D08"]])
    for target, claim in (tuple(pair) for pair in GROUND["published_pairs"]):
        row = published.get((target, claim))
        if row is None:
            continue
        call = call_value(row)
        if call and call != GROUND["expected"][target][claim]["overall"] and call in ("PASS", "REVIEW", "FAIL"):
            damage.append(["comparisons:%s|%s:terminal_call_contradicts_record" % (target, claim), ["D09"]])
    for target, claim in (tuple(pair) for pair in GROUND["issued_pairs"]):
        row = issued.get((target, claim))
        if row is None:
            continue
        call = call_value(row)
        if call and call != GROUND["granted_expected"][target][claim]["overall"] and call in ("PASS", "REVIEW", "FAIL"):
            damage.append(["granted:%s|%s:terminal_call_contradicts_record" % (target, claim), ["D09"]])
    return damage


def required_reference_reviews():
    refs=[g["overall"] for data in (GROUND["expected"],GROUND["granted_expected"]) for claims in data.values() for g in claims.values()]
    return math.ceil(sum(x=="REVIEW" for x in refs)/2)
def recognized_reference_reviews(answer):
    count=0
    for rows,truth in ((_published_rows(answer),GROUND["expected"]),(_issued_rows(answer),GROUND["granted_expected"])):
        for (target,claim),row in rows.items():
            if truth.get(target,{}).get(claim,{}).get("overall")=="REVIEW" and call_value(row)=="REVIEW":count+=1
    return count


def score(answer: dict) -> dict:
    inversions: dict[str, list[int]] = {}
    scope_notes = answer.get("assumptions_and_scope", [])
    scope_complete = (
        isinstance(scope_notes, list)
        and bool(scope_notes)
        and all(isinstance(item, str) and item.strip() for item in scope_notes)
    )
    published_pairs = [tuple(pair) for pair in GROUND["published_pairs"]]
    issued_pairs = [tuple(pair) for pair in GROUND["issued_pairs"]]
    comparisons = index_comparisons(answer.get("comparisons", answer.get("published_comparisons", [])))

    published_calls_ok = published_status_ok = published_status_total = 0
    published_binding_ok = published_analysis_ok = published_features_present = 0
    published_details = []
    pass_declared = review_declared = fail_declared = 0

    for target, claim in published_pairs:
        row = comparisons.get((target, claim), {})
        expected = GROUND["expected"][target][claim]
        call = call_value(row)
        published_calls_ok += call == expected["overall"]
        inversion_tally(inversions, "chart_calls", "call", call, expected["overall"])
        pass_declared += call == "PASS"
        review_declared += call == "REVIEW"
        fail_declared += call == "FAIL"
        findings = finding_index(row)
        required = GROUND["element_ids"][claim]
        published_features_present += sum(feature in findings for feature in required)
        for feature in required:
            published_status_total += 1
            finding = findings.get(feature, {})
            published_status_ok += class_value(finding) == expected["statuses"][feature]
            inversion_tally(inversions, "element_classes", "evidence_class",
                            class_value(finding), expected["statuses"][feature])
            published_binding_ok += sources_bound(finding, target, "published") and nonempty(finding, "evidence_locator")
            published_analysis_ok += all(
                nonempty(finding, field)
                for field in ("actor_direction", "medium_or_pins", "sequence_test", "reason")
            )
        published_details.append({
            "target_id": target,
            "claim_id": claim,
            "call": call,
            "expected": expected["overall"],
            "finding_count": len(findings),
        })

    root = version_root(answer)
    claim_rows = index_claim_rows(root.get("same_number_claims", root.get("claim_deltas", root.get("claim_mappings", []))))
    issued_rows = index_comparisons(root.get("granted_comparisons", root.get("issued_comparisons", [])))

    map_feature = map_lineage = map_scope = 0.0
    mapping_structural = 0
    allowed_scope_relations = {item["scope_relation"] for item in GROUND["version_mapping"].values()}
    for claim in GROUND["mapping_claims"]:
        row = claim_rows.get(claim, {})
        expected = GROUND["version_mapping"][claim]
        features = list_value(row, "granted_required_feature_refs", "required_feature_refs", "issued_features")
        lineage = list_value(
            row,
            "source_published_claim_ids",
            "published_claim_sources",
            "same_number_lineage",
            "lineage",
        )
        scope = str(row.get("same_number_scope_relation", row.get("scope_relation", ""))).strip().upper()
        map_feature += row_jaccard(row, features, expected["required_feature_refs"])
        map_lineage += row_jaccard(row, lineage, expected["source_published_claim_ids"])
        map_scope += scope == expected["scope_relation"]
        mapping_structural += bool(features) and bool(lineage) and scope in allowed_scope_relations
    mapping_count = len(GROUND["mapping_claims"])
    map_feature /= mapping_count
    map_lineage /= mapping_count
    map_scope /= mapping_count

    issued_calls_ok = issued_status_ok = issued_status_total = 0
    issued_binding_ok = issued_binding_total = issued_analysis_ok = issued_features_present = 0
    decisive_score = 0.0
    issued_details = []
    correct_issued_reviews = 0

    for target, claim in issued_pairs:
        row = issued_rows.get((target, claim), {})
        expected = GROUND["granted_expected"][target][claim]
        call = call_value(row)
        issued_calls_ok += call == expected["overall"]
        inversion_tally(inversions, "chart_calls", "call", call, expected["overall"])
        correct_issued_reviews += call == "REVIEW" and expected["overall"] == "REVIEW"
        pass_declared += call == "PASS"
        review_declared += call == "REVIEW"
        fail_declared += call == "FAIL"
        findings = finding_index(row, issued=True)
        required = GROUND["version_mapping"][claim]["required_feature_refs"]
        issued_features_present += sum(feature in findings for feature in required)
        for feature in required:
            issued_status_total += 1
            finding = findings.get(feature, {})
            issued_status_ok += class_value(finding) == expected["statuses"][feature]
            inversion_tally(inversions, "element_classes", "evidence_class",
                            class_value(finding), expected["statuses"][feature])
            issued_binding_total += 1
            issued_binding_ok += sources_bound(finding, target, "issued") and nonempty(finding, "evidence_locator")
        issued_binding_total += 1
        issued_binding_ok += sources_bound(row, target, "issued")
        issued_analysis_ok += all(
            nonempty(row, field)
            for field in ("actor_attribution", "medium_boundary", "temporal_boundary")
        ) and all(nonempty(findings.get(feature, {}), "reason") for feature in required)
        decisive = list_value(row, "decisive_feature_refs", "blocking_feature_refs", "decisive_features")
        # The decisive set is the projection of this row's own feature statuses
        # (see the note above), so it is credited in proportion to this row's
        # feature classification accuracy. A row that classifies its features the
        # way the record does and then names the open ones keeps the term in full.
        row_status_accuracy = sum(
            class_value(findings.get(feature, {})) == expected["statuses"][feature]
            for feature in required
        ) / max(1, len(required))
        context = {
            feature for feature in expected.get("context_features", [])
            if feature in required
            and expected["statuses"][feature] in ("DIRECT", "COMPOSITE")
            and class_value(findings.get(feature, {})) == expected["statuses"][feature]
        }
        decisive_score += row_status_accuracy * row_jaccard(row,
            [feature for feature in decisive if feature not in context], expected["decisive"]
        )
        issued_details.append({
            "target_id": target,
            "claim_id": claim,
            "call": call,
            "expected": expected["overall"],
            "finding_count": len(findings),
        })

    # Share of the eighteen comparisons whose terminal call matches the record.
    # Used below to credit the presence-only sub-terms listed in
    # PRESENCE_ONLY_TERMS; see the note beside that tuple.
    terminal_call_accuracy = (published_calls_ok + issued_calls_ok) / (
        len(published_pairs) + len(issued_pairs)
    )

    bridge_rows = index_id_rows(answer.get("evidence_bridges", answer.get("bridge_assessments", [])), "bridge_id")
    bridge_category_ok = bridge_category_total = 0
    bridge_feature_score = 0.0
    bridge_analysis_ok = 0
    for bridge_id, expected in GROUND["bridge_expected"].items():
        row = bridge_rows.get(bridge_id, {})
        observed_values = (
            str(row.get("link_status", row.get("bridge_status", ""))).strip().upper(),
            str(row.get("proposition_status", row.get("claim_status", ""))).strip().upper(),
            str(row.get("controlling_effect", row.get("effect", ""))).strip().upper(),
        )
        expected_values = (
            expected["link_status"], expected["proposition_status"], expected["controlling_effect"]
        )
        # One determination per bridge: proposition_status and controlling_effect
        # are lookups from link_status (see the note above), so the block counts
        # only when the whole row matches the record.
        bridge_category_ok += all(observed == wanted for observed, wanted in zip(observed_values, expected_values))
        bridge_category_total += 1
        for field, observed, wanted in zip(
            ("link_status", "proposition_status", "controlling_effect"),
            observed_values, expected_values,
        ):
            inversion_tally(inversions, "bridges", field, observed, wanted)
        bridge_feature_score += row_jaccard(row,
            list_value(row, "affected_feature_refs", "feature_refs", "affected_features"),
            expected["affected_feature_refs"],
        )
        observed_sources = set(list_value(row, "source_ids", "evidence_ids", "sources"))
        expected_sources = set(expected["source_ids"])
        locators = list_value(row, "evidence_locators", "locators", "citations")
        bridge_analysis_ok += (
            bool(observed_sources)
            and expected_sources <= observed_sources
            and observed_sources <= set(GROUND["source_ids"])
            and bool(locators)
            and nonempty(row, "reason")
        )
    bridge_count = len(GROUND["bridge_expected"])
    bridge_core = (
        0.65 * (bridge_category_ok / bridge_category_total)
        + 0.20 * (bridge_feature_score / bridge_count)
        + 0.15 * (bridge_analysis_ok / bridge_count)
    )

    construction_rows = index_id_rows(
        answer.get("construction_dependencies", answer.get("claim_construction_issues", [])),
        "issue_id",
    )
    construction_disposition_ok = 0
    construction_claim_score = construction_feature_score = 0.0
    construction_analysis_ok = 0
    for issue_id, expected in GROUND["construction_expected"].items():
        row = construction_rows.get(issue_id, {})
        disposition = str(row.get("disposition", row.get("status", ""))).strip().upper()
        construction_disposition_ok += disposition == expected["disposition"]
        inversion_tally(inversions, "construction", "disposition", disposition, expected["disposition"])
        # Claim references are compared after the same version-prefix normalization
        # the dependency audit already uses. `analysis_contract.json` - the only
        # claim-ref notation an analyst ever sees - writes `PUBLISHED:12` / `ISSUED:10`,
        # and `normalize_claim_ref` already declares `PUB`/`ISS` equivalent to those.
        # Both sides are normalized, so the comparison stays symmetric.
        construction_claim_score += row_jaccard(row,
            [normalize_claim_ref(ref)
             for ref in list_value(row, "affected_claim_refs", "claim_refs", "affected_claims")],
            [normalize_claim_ref(ref) for ref in expected["affected_claim_refs"]],
        )
        construction_feature_score += row_jaccard(row,
            list_value(row, "affected_feature_refs", "feature_refs", "affected_features"),
            expected["affected_feature_refs"],
        )
        construction_analysis_ok += (
            bool(list_value(row, "claim_locators", "locators", "citations")) and nonempty(row, "reason")
        )
    construction_count = len(GROUND["construction_expected"])
    construction_core = (
        0.60 * (construction_disposition_ok / construction_count)
        + 0.20 * (construction_claim_score / construction_count)
        + 0.20 * (construction_feature_score / construction_count)
    )

    sensitivity_rows = index_id_rows(
        answer.get("sensitivity_matrix", answer.get("outcome_sensitivity", [])),
        "scenario_id",
    )
    sensitivity_category_ok = sensitivity_category_total = 0
    sensitivity_decisive_score = 0.0
    sensitivity_analysis_ok = 0
    for scenario_id, expected in GROUND["sensitivity_expected"].items():
        row = sensitivity_rows.get(scenario_id, {})
        observed_values = (
            str(row.get("baseline_call", "")).strip().upper(),
            str(row.get("hypothetical_call", row.get("scenario_call", ""))).strip().upper(),
            str(row.get("result_effect", row.get("effect", ""))).strip().upper(),
        )
        expected_values = (
            expected["baseline_call"], expected["hypothetical_call"], expected["result_effect"]
        )
        # One determination per scenario: baseline_call restates the chart's own
        # terminal call for the pair and result_effect is the arithmetic of the
        # other two columns (see the note above), so the block counts only when
        # the whole row matches the record.
        sensitivity_category_ok += all(observed == wanted for observed, wanted in zip(observed_values, expected_values))
        sensitivity_category_total += 1
        for field, observed, wanted in zip(
            ("call", "call", "result_effect"), observed_values, expected_values,
        ):
            inversion_tally(inversions, "sensitivity", field, observed, wanted)
        sensitivity_decisive_score += row_jaccard(row,
            list_value(row, "decisive_feature_refs", "blocking_feature_refs", "decisive_features"),
            expected["decisive_feature_refs"],
        )
        sensitivity_analysis_ok += nonempty(row, "reason")
    sensitivity_count = len(GROUND["sensitivity_expected"])
    sensitivity_core = (
        0.65 * (sensitivity_category_ok / sensitivity_category_total)
        + 0.25 * (sensitivity_decisive_score / sensitivity_count)
        + 0.10 * (sensitivity_analysis_ok / sensitivity_count)
    )

    dependency_rows_raw = index_id_rows(
        answer.get("dependency_audit", answer.get("claim_dependency_audit", [])),
        "claim_ref",
    )
    dependency_rows = {
        normalize_claim_ref(claim_ref): row
        for claim_ref, row in dependency_rows_raw.items()
    }
    dependency_parent_ok = dependency_status_ok = dependency_policy_ok = 0
    dependency_candidate_ok = dependency_basis_ok = dependency_analysis_ok = 0
    for claim_ref, expected in GROUND["dependency_expected"].items():
        row = dependency_rows.get(claim_ref, {})
        observed_parent = str(row.get("declared_parent_claim_id") or "").strip()
        expected_parent = str(expected["declared_parent_claim_id"] or "").strip()
        observed_candidate = str(row.get("candidate_coherent_parent_claim_id") or "").strip()
        expected_candidate = str(expected["candidate_coherent_parent_claim_id"] or "").strip()
        observed_status = str(row.get("dependency_status", row.get("status", ""))).strip().upper()
        observed_policy = str(row.get("expansion_policy", row.get("policy", ""))).strip().upper()
        observed_basis = str(row.get("candidate_basis", row.get("basis", ""))).strip().upper()
        # One determination per claim row: expansion_policy and candidate_basis
        # are lookups from dependency_status (see the note above). The three
        # columns keep their combined 0.60 of the register but are credited
        # together, so a chart cannot bank the lookups off a wrong status.
        dependency_determination_ok = (
            observed_status == expected["dependency_status"]
            and observed_policy == expected["expansion_policy"]
            and observed_basis == expected["candidate_basis"]
        )
        row_present = claim_ref in dependency_rows
        dependency_parent_ok += row_present and observed_parent == expected_parent
        dependency_status_ok += dependency_determination_ok
        dependency_policy_ok += dependency_determination_ok
        inversion_tally(inversions, "dependency", "dependency_status",
                        observed_status, expected["dependency_status"])
        inversion_tally(inversions, "dependency", "expansion_policy",
                        observed_policy, expected["expansion_policy"])
        dependency_candidate_ok += row_present and observed_candidate == expected_candidate
        dependency_basis_ok += dependency_determination_ok
        dependency_analysis_ok += nonempty(row, "claim_locator") and nonempty(row, "reason")
    dependency_count = len(GROUND["dependency_expected"])
    dependency_core = (
        0.10 * (dependency_parent_ok / dependency_count)
        + 0.30 * (dependency_status_ok / dependency_count)
        + 0.20 * (dependency_policy_ok / dependency_count)
        + 0.25 * (dependency_candidate_ok / dependency_count)
        + 0.10 * (dependency_basis_ok / dependency_count)
        + 0.05 * (dependency_analysis_ok / dependency_count)
    )

    family_rows = index_id_rows(
        answer.get("family_correspondence", answer.get("claim_family_correspondence", [])),
        "published_claim_id",
    )
    family_destination_score = family_feature_score = 0.0
    family_status_ok = family_effect_ok = family_analysis_ok = 0
    for published_claim, expected in GROUND["family_correspondence_expected"].items():
        row = family_rows.get(published_claim, {})
        destination_similarity = row_jaccard(row,
            list_value(row, "candidate_issued_claim_ids", "issued_claim_ids", "destination_claim_ids"),
            expected["candidate_issued_claim_ids"],
        )
        feature_similarity = row_jaccard(row,
            list_value(row, "issued_expanded_feature_refs", "expanded_feature_refs", "issued_features"),
            expected["issued_expanded_feature_refs"],
        )
        family_destination_score += destination_similarity
        # The inherited later-version feature set belongs to the destination, so
        # it is credited in proportion to how well the destination was identified
        # (see the note above). A row that names the right destination and
        # expands it correctly keeps the term in full.
        family_feature_score += destination_similarity * feature_similarity
        observed_family_status = str(row.get("correspondence_status", row.get("status", ""))).strip().upper()
        observed_family_effect = str(row.get("dependency_effect", row.get("effect", ""))).strip().upper()
        # One determination per row: dependency_effect is a lookup from
        # correspondence_status (see the note above).
        family_determination_ok = (
            observed_family_status == expected["correspondence_status"]
            and observed_family_effect == expected["dependency_effect"]
        )
        family_status_ok += family_determination_ok
        family_effect_ok += family_determination_ok
        inversion_tally(inversions, "family", "correspondence_status",
                        observed_family_status, expected["correspondence_status"])
        inversion_tally(inversions, "family", "dependency_effect",
                        observed_family_effect, expected["dependency_effect"])
        family_analysis_ok += all(
            nonempty(row, field)
            for field in ("published_claim_locator", "issued_claim_locator", "reason")
        )
    family_count = len(GROUND["family_correspondence_expected"])
    family_core = (
        0.25 * (family_destination_score / family_count)
        + 0.30 * (family_feature_score / family_count)
        + 0.25 * (family_status_ok / family_count)
        + 0.15 * (family_effect_ok / family_count)
        + 0.05 * (family_analysis_ok / family_count)
    )

    pair_total = len(published_pairs)
    issued_pair_total = len(issued_pairs)
    target_coverage = sum(
        any(pair[0] == target and pair in comparisons for pair in published_pairs)
        for target in GROUND["targets"]
    ) / len(GROUND["targets"])
    published_coverage = sum(pair in comparisons for pair in published_pairs) / pair_total
    published_feature_coverage = published_features_present / published_status_total
    mapping_coverage = sum(claim in claim_rows for claim in GROUND["mapping_claims"]) / mapping_count
    issued_pair_coverage = sum(pair in issued_rows for pair in issued_pairs) / issued_pair_total
    issued_feature_coverage = issued_features_present / issued_status_total
    bridge_coverage = sum(key in bridge_rows for key in GROUND["bridge_expected"]) / bridge_count
    construction_coverage = sum(key in construction_rows for key in GROUND["construction_expected"]) / construction_count
    sensitivity_coverage = sum(key in sensitivity_rows for key in GROUND["sensitivity_expected"]) / sensitivity_count
    dependency_coverage = sum(key in dependency_rows for key in GROUND["dependency_expected"]) / dependency_count
    family_coverage = sum(key in family_rows for key in GROUND["family_correspondence_expected"]) / family_count
    binding_ok = published_binding_ok + issued_binding_ok
    binding_total = published_status_total + issued_binding_total
    evidence_binding = binding_ok / binding_total if binding_total else 0.0
    analysis_ok = (
        published_analysis_ok + issued_analysis_ok + bridge_analysis_ok
        + construction_analysis_ok + sensitivity_analysis_ok + dependency_analysis_ok
        + family_analysis_ok + int(scope_complete)
    )
    analysis_total = (
        published_status_total + issued_pair_total + bridge_count
        + construction_count + sensitivity_count + dependency_count + family_count + 1
    )
    analysis_completeness = analysis_ok / analysis_total if analysis_total else 0.0

    # Anti-dumping runs in both directions. A chart that answers every pair with
    # the same definite call has not triaged anything, and a blanket
    # non-infringement call is the same failure as a blanket infringement call.
    #
    # The test is for a blanket call and nothing narrower: it fires only when the same
    # terminal call is declared on at least 90% of the comparisons. Calling FAIL where the
    # reference calls REVIEW is a wrong call - NOT_SHOWN is an evidence gap, not a
    # contradiction - and terminal-call accuracy already charges for it in
    # `published_core` and `issued_core`.
    total_calls = pair_total + issued_pair_total
    blanket_calls = 0.9 * total_calls
    no_dump = pass_declared < blanket_calls and fail_declared < blanket_calls
    coverage_gate = (
        target_coverage * published_coverage * published_feature_coverage * mapping_coverage
        * issued_pair_coverage * issued_feature_coverage * evidence_binding
        * bridge_coverage * construction_coverage * sensitivity_coverage
        * dependency_coverage * family_coverage
        * (1.0 if no_dump else 0.0)
    )

    published_call_accuracy = published_calls_ok / pair_total
    published_status_accuracy = published_status_ok / published_status_total
    published_binding = published_binding_ok / published_status_total
    published_core = (
        0.45 * published_call_accuracy
        + 0.40 * published_status_accuracy
        + 0.15 * published_binding
    )
    mapping_core = 0.45 * map_feature + 0.25 * map_lineage + 0.30 * map_scope
    issued_binding = issued_binding_ok / issued_binding_total
    issued_core = (
        0.25 * (issued_calls_ok / issued_pair_total)
        + 0.45 * (issued_status_ok / issued_status_total)
        + 0.15 * (decisive_score / issued_pair_total)
        # The issued target-source binding term asks the same presence-only
        # question as the published one - is a permitted source cited and is a
        # locator non-empty - so it is credited the same way, in proportion to
        # terminal-call accuracy.
        + 0.15 * issued_binding
    )
    version_core = 0.45 * mapping_core + 0.55 * issued_core
    conclusion_inversion_rate, inversion_detail = inversion_rate(inversions)
    inversion_factor = 1.0 - max(
        0.0, (conclusion_inversion_rate - INVERSION_FLOOR) / (1.0 - INVERSION_FLOOR)
    )
    presence_raw = {
        "published_evidence_binding_present": published_binding,
        "issued_evidence_binding_present": issued_binding,
        "bridge_support_present": bridge_analysis_ok / bridge_count,
        "sensitivity_reason_present": sensitivity_analysis_ok / sensitivity_count,
        "dependency_locator_and_reason_present": dependency_analysis_ok / dependency_count,
        "family_locators_and_reason_present": family_analysis_ok / family_count,
        "analysis_completeness": analysis_completeness,
    }
    presence_report = {
        name: {
            "reported": round(presence_raw[name], 6),
            "credited": round(presence_raw[name], 6),
        }
        for name in PRESENCE_ONLY_TERMS
    }

    correct_published_reviews = sum(
        call_value(comparisons.get((target, claim), {})) == "REVIEW"
        and GROUND["expected"][target][claim]["overall"] == "REVIEW"
        for target, claim in published_pairs
    )
    reference_reviews = sum(
        GROUND["expected"][target][claim]["overall"] == "REVIEW"
        for target, claim in published_pairs
    ) + sum(
        GROUND["granted_expected"][target][claim]["overall"] == "REVIEW"
        for target, claim in issued_pairs
    )
    whole_contract = (
        target_coverage == published_coverage == published_feature_coverage == mapping_coverage
        == issued_pair_coverage == issued_feature_coverage == evidence_binding == 1.0
        and bridge_coverage == construction_coverage == sensitivity_coverage == dependency_coverage == family_coverage == 1.0
        and mapping_structural == mapping_count
        and analysis_completeness == 1.0
        and scope_complete
        and no_dump
    )
    # ---- lenient lens: LENIENT_REQUIRED_ITEMS, each read from its own strict-side result ----
    lenient_checks = {
        # every designated row the contract names is delivered, and each same-number
        # mapping row carries its feature set, lineage and scope relation
        "contract_row_coverage": bool(
            target_coverage == published_coverage == published_feature_coverage
            == mapping_coverage == issued_pair_coverage == issued_feature_coverage == 1.0
            and bridge_coverage == construction_coverage == sensitivity_coverage
            == dependency_coverage == family_coverage == evidence_binding == 1.0
            and mapping_structural == mapping_count
        ),
        # locators, reasons and a non-empty assumptions_and_scope collection
        "analysis_completeness": bool(analysis_completeness == 1.0 and scope_complete),
        # retain both outcomes and at least half of reference REVIEW comparisons
        "terminal_call_accuracy": bool(terminal_call_accuracy == 1.0),
        # D01: the chart is triage, not one definite verdict stamped on everything
        "D01": bool(no_dump),
    }
    lenient = 1.0 if all(lenient_checks[item] for item in LENIENT_REQUIRED_ITEMS) else 0.0

    # pd-ledger-v1 parts, settled by settle().
    # Only a systematic inversion can scale unrelated dimensions. Ordinary
    # row omissions and errors already lower their own dimension's completion.
    continuous_multiplier = inversion_factor
    # P02 and P08 are the two sections of the version-impact register - same-number claim
    # mapping and issued-claim comparisons - carried as separate positive items, and
    # local errors reduce their corresponding register, without a second global charge.
    ledger_parts = {
        "completion": {
            "P01": published_core * continuous_multiplier,
            "P02": mapping_core * continuous_multiplier,
            "P03": bridge_core * continuous_multiplier,
            "P04": construction_core * continuous_multiplier,
            "P05": sensitivity_core * continuous_multiplier,
            "P06": dependency_core * continuous_multiplier,
            "P07": family_core * continuous_multiplier,
            "P08": issued_core * continuous_multiplier,
        },
        "damage": ([] if no_dump else [[
            "blanket terminal call: pass_declared=%d fail_declared=%d of %d comparisons (>= 90%%)"
            % (pass_declared, fail_declared, total_calls), ["D01"]]]),
    }

    return {
        "_parts": ledger_parts,
        "lenient": lenient,
        "group_points": {
            "published_chart": round(published_core, 6),
            "version_impact": round(version_core, 6),
            "evidence_bridges": round(bridge_core, 6),
            "construction_dependencies": round(construction_core, 6),
            "sensitivity_matrix": round(sensitivity_core, 6),
            "dependency_audit": round(dependency_core, 6),
            "family_correspondence": round(family_core, 6),
        },
        "detail": {
            "lenient_required": LENIENT_REQUIRED_ITEMS,
            "lenient_detail": lenient_checks,
            "published_calls_correct": published_calls_ok,
            "published_calls_total": pair_total,
            "published_elements_correct": published_status_ok,
            "published_elements_total": published_status_total,
            "mapping_feature_score": round(map_feature, 6),
            "lineage_score": round(map_lineage, 6),
            "scope_relation_score": round(map_scope, 6),
            "issued_calls_correct": issued_calls_ok,
            "issued_calls_total": issued_pair_total,
            "issued_features_correct": issued_status_ok,
            "issued_features_total": issued_status_total,
            "decisive_feature_score": round(decisive_score / issued_pair_total, 6),
            "bridge_categories_correct": bridge_category_ok,
            "bridge_categories_total": bridge_category_total,
            "bridge_feature_score": round(bridge_feature_score / bridge_count, 6),
            "construction_dispositions_correct": construction_disposition_ok,
            "construction_dispositions_total": construction_count,
            "construction_claim_score": round(construction_claim_score / construction_count, 6),
            "construction_feature_score": round(construction_feature_score / construction_count, 6),
            "sensitivity_categories_correct": sensitivity_category_ok,
            "sensitivity_categories_total": sensitivity_category_total,
            "sensitivity_decisive_score": round(sensitivity_decisive_score / sensitivity_count, 6),
            "dependency_declared_parents_correct": dependency_parent_ok,
            "dependency_statuses_correct": dependency_status_ok,
            "dependency_policies_correct": dependency_policy_ok,
            "dependency_candidates_correct": dependency_candidate_ok,
            "dependency_bases_correct": dependency_basis_ok,
            "dependency_rows_total": dependency_count,
            "family_destination_score": round(family_destination_score / family_count, 6),
            "family_feature_score": round(family_feature_score / family_count, 6),
            "family_statuses_correct": family_status_ok,
            "family_effects_correct": family_effect_ok,
            "family_rows_total": family_count,
            "evidence_binding": round(evidence_binding, 6),
            "analysis_completeness": round(analysis_completeness, 6),
            "target_coverage": round(target_coverage, 6),
            "published_claim_coverage": round(published_coverage, 6),
            "published_feature_coverage": round(published_feature_coverage, 6),
            "version_mapping_coverage": round(mapping_coverage, 6),
            "issued_pair_coverage": round(issued_pair_coverage, 6),
            "issued_feature_coverage": round(issued_feature_coverage, 6),
            "bridge_coverage": round(bridge_coverage, 6),
            "construction_coverage": round(construction_coverage, 6),
            "sensitivity_coverage": round(sensitivity_coverage, 6),
            "dependency_coverage": round(dependency_coverage, 6),
            "family_coverage": round(family_coverage, 6),
            "coverage_gate": round(coverage_gate, 6),
            "no_dump": no_dump,
            "terminal_call_accuracy": round(terminal_call_accuracy, 6),
            "presence_only_terms": presence_report,
            "conclusion_inversion_rate": round(conclusion_inversion_rate, 6),
            "conclusion_inversion_factor": round(inversion_factor, 6),
            "conclusion_inversion": inversion_detail,
            "pass_declared": pass_declared,
            "review_declared": review_declared,
            "fail_declared": fail_declared,
            "reference_reviews": reference_reviews,
            "correct_reviews": correct_published_reviews + correct_issued_reviews,
            "contract_whole": whole_contract,
            "assumptions_and_scope_complete": scope_complete,
            "published_comparisons": published_details,
            "issued_comparisons": issued_details,
        },
    }


# --------------------------------------------------------------------------- #
# pd-ledger-v1 settlement.
# --------------------------------------------------------------------------- #

PARAMS = Path(os.environ.get("SCORING_PARAMS", HERE / "scoring_params.json"))
ZERO_PARTS = {"completion": {}, "damage": []}


def deliverable(arg: str) -> Path:
    """The contract passes a directory (rollout artifacts/ or task golden/); the container passes the file."""
    p = Path(arg)
    if not p.is_dir():
        return p
    named = p / "claim_chart.json"
    if named.is_file():
        return named
    found = sorted(p.glob("**/claim_chart.json"))
    return found[0] if found else named


def settle(result: dict) -> dict:
    """Settle the ledger parts into the pd-ledger-v1 score."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    parts = result.pop("_parts", ZERO_PARTS)
    lenient = float(result.pop("lenient", 0.0))
    completion = {k: round(min(1.0, max(0.0, float(parts["completion"].get(k, 0.0)))), 10) for k in weights}
    instances = [{"key": key, "item_ids": items} for key, items in parts["damage"]]
    earned = sum(weights[k] * completion[k] for k in weights)
    retention = math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances)
    final = earned * retention
    settled = {
        "reward": final,
        "rewards": {"strict": final, "lenient": lenient},
        "reward_formulas": {
            "strict": "positive_earned * retention (pd-ledger-v1; weights and coefficients from scoring_params.json)",
            "lenient": "1 iff every item in LENIENT_REQUIRED_ITEMS ("
                       + ", ".join(LENIENT_REQUIRED_ITEMS)
                       + ") clears on its own strict-side result, else 0",
        },
        "scoring_ledger": {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                           "damage_instances": instances, "positive_earned": earned,
                           "retention": retention, "final_score": final},
    }
    settled.update(result)
    return settled


def main() -> int:
    path = deliverable(sys.argv[1] if len(sys.argv) > 1 else "/workspace/claim_chart.json")
    try:
        result = score(load_answer(path))
    except Exception as exc:
        result = {
            "lenient": 0.0,
            "group_points": {
                "published_chart": 0.0,
                "version_impact": 0.0,
                "evidence_bridges": 0.0,
                "construction_dependencies": 0.0,
                "sensitivity_matrix": 0.0,
                "dependency_audit": 0.0,
                "family_correspondence": 0.0,
            },
            "detail": {"error": str(exc)},
        }
    print(json.dumps(settle(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

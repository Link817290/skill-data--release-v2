#!/usr/bin/env python3
"""Condition-blind deterministic scorer for the citation-reconciliation report (pd-ledger-v1).

Usage: validator.py <report> [<workspace>]
  <report> is citation_reconciliation.md, or a directory holding the artifact or Golden.
  <workspace> holds materials/hydrology_manuscript.pdf; default /workspace, falling back to the task's
  environment/workspace when the PDF is not there.

The strict score is settled in the standard form
  final = positive_earned * retention
  positive_earned = sum(weight[Q] * completion[Q])      (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

The positive items Q02, Q03, Q05-Q11 and Q14-Q16 are in tests/rebuilt_units.json: each is a group of reference values read off
Golden's own deliverable, scored as the fraction of bound leaves whose value (or an equivalent) appears on a line that also
carries the row's identity; Q11 is the share of end records whose credited-author cardinality the report
states correctly. Q17 is the share of the confirmed repairs the patch register executes, and Q18 the share
of the supplied near matches the report files as cleared.
Deductions (each fires as one damage instance):
  D01 gate: report unreadable or not a citation report
  D02 gate: manuscript PDF missing or its hash differs
  D03 decision: the reference list is declared ready for release
  D04 decision: no release/hold decision is stated
  D05 coherence: release asserted while the report's own registers still carry open holds
  D06 one instance per false repair claimed on a cleared record
  D07 a locator given as a PDF sheet number with no printed folio
  D08 a manuscript location cited at a printed folio the manuscript does not have
  D09 a bibliographic record supplied for a work the reference list does not contain
  D10 repeated occurrences collapsed into a single patch row
  D11 a credited-author cardinality that contradicts the supplied record
  D12 gate: one instance per required give-away unit the report does not carry
  D13 gate: the report was scored from a file not named citation_reconciliation.md
An unreadable report returns a ledger with every completion 0.
rewards.lenient is the must-have lens: 1.0 only when every item in LENIENT_REQUIRED_ITEMS is met, read
off the same per-item results the strict ledger settles (positive completion == 1, deduction not fired).

`dimensions` and the factors reported beside it are the scorer's diagnostic profile of the report; the
reward itself is the ledger settlement above.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# --- disowned-unit guard (2026-09-22 audit repair, narrowed 2026-09-23) --------------------------
# A unit the submission itself withdraws is not an assertion. The withdrawal must GOVERN THE WHOLE
# UNIT, so the cue is anchored at the start of the unit (after any bullet, quote or table marker) or
# is a quote-and-reject wrapper around it. An unanchored match charges correct work: one AML review
# wrote "it is expressly not asserted as structuring on the present record" — a careful, correct
# finding about a different allegation — and an unanchored guard blanked the whole value, costing
# prior candidate reports real points. Domain words such as "rejected",
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
_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)[^\n]*\n.*?^[ \t]*(?:```|~~~)[ \t]*$", re.S | re.M)


def _guard_deliverable_text(raw: str) -> str:
    """Drop fenced blocks and every line (paragraph line or table row) the text disowns."""
    raw = _FENCE_RE.sub("", raw)
    return "\n".join(line for line in raw.split("\n") if not _DISOWN_RE.search(line))



EXPECTED_PDF_SHA256 = "55eb299c521ddcba76991e3de46ad205cb8a08be8f1b5f8c4a48ff6d01e74ed7"

# ---------------------------------------------------------------------------
# The lenient lens: the handful of things this editorial handoff cannot be
# called finished without. Binary — 1.0 only when every one of them is met.
# They are read off the SAME per-item results the strict ledger settles
# (positive completion, damage instances); nothing is re-parsed and the strict
# computation is untouched.
#
# Why these six, from instruction.md and RUBRIC.md:
#   Q02  instruction.md: "Cite every manuscript location by the page number
#        printed on the manuscript page itself (the journal folio running from
#        4589), not by the PDF sheet number". Q02 is the item that reads a
#        printed folio bound to the record it belongs to (end-reference head,
#        year/suffix, exact date-like text). An editor who cannot find the
#        callout cannot act on any row, so this is the locator floor.
#   Q05  instruction.md: the report "must contain a complete occurrence-level
#        body-citation ledger ... bidirectional mapping controls". Q05 is the
#        mapping status recorded for each body occurrence — the reconciliation
#        outcome itself, which is what the audit was commissioned to produce.
#   Q15  instruction.md: "Give every exclusion its page, exact source
#        expression, local context, and reason." Q15 is the exclusion row read
#        with its local context bound to the printed folio and the exact
#        date-like text; without it the date screen is not reviewable.
#   D09  the brief prohibits bibliographic facts absent from the supplied
#        material. An affirmative invented record in an operational finding or
#        patch can direct production to a source that was never evidenced, so a
#        handoff carrying one is not minimally usable even when its ledgers are
#        otherwise complete.
#   D12  the give-away unit gate: the end-reference records, the cited-only
#        works, their owners and the mapping controls every complete handoff
#        carries. A report missing any of them is not a finished handoff.
#   D03  RUBRIC.md D03: declaring the list ready for release is "the opposite
#        conclusion, and the first line an editor acts on". The direction of
#        the conclusion must be right.
#   D04  RUBRIC.md D04: no decision stated "leaves the decision it was
#        commissioned for unstated"; instruction.md makes the "overall
#        readiness decision" part of what completion means. D03/D04 are
#        mutually exclusive halves of the one decision requirement.
#
# Deliberately NOT required: Q06/Q10 (compact-callout detail and fully
# reconciled control totals refine a handoff that already has the required
# occurrence and exclusion coverage), and the
# per-occurrence/per-record attribute items (Q07, Q08, Q09, Q11, Q14, Q16),
# which refine the registers rather than decide whether the handoff exists and
# points the right way. D01 is implied: an unreadable report scores every
# positive item 0 and therefore already fails Q02/Q05/Q15.
LENIENT_REQUIRED_ITEMS = ["Q02", "Q05", "Q15", "D03", "D04", "D09", "D12"]
# Weight of each dimension in the reported profile, as a share of the report
# normalised to sum to 1. Four dimensions are scored in parts, each part
# carrying the share of its parent it accounts for:
#   closure_precision   = 0.35 readiness       + 0.65 clearances
#   ledger_completeness = 0.55 occurrence rows + 0.45 reference rows
#   mapping_control     = 0.65 reverse view    + 0.35 control totals
#   exclusion_audit     = the 35 exclusion rows, grouped by the reason the
#                         reference gives each one (study period or scenario
#                         range; table value or figure-caption period;
#                         publication metadata and editorial furniture), the
#                         three classes RUBRIC.md names for this register.
WEIGHTS = {
    "identity_resolution": 0.15 / 0.96,
    "disposition_quality": 0.12 / 0.96,
    "evidence_traceability": 0.06 / 0.96,
    "readiness_decision": 0.35 * 0.05 / 0.96,
    "cleared_near_matches": 0.65 * 0.05 / 0.96,
    "occurrence_ledger": 0.55 * 0.12 / 0.96,
    "reference_ledger": 0.45 * 0.12 / 0.96,
    "reverse_mapping": 0.65 * 0.07 / 0.96,
    "control_totals": 0.35 * 0.07 / 0.96,
    "patch_register": 0.12 / 0.96,
    # the three exclusion classes divide one share; split_exclusion_weights sets them
    "exclusion_period_range": 0.10 / 0.96,
    "exclusion_caption_table": 0.0,
    "exclusion_metadata": 0.0,
    "collision_control": 0.10 / 0.96,
    "action_ownership": 0.07 / 0.96,
}


def exclusion_class(row: dict) -> str:
    """The reason the reference gives this date-like expression, as RUBRIC.md groups them."""
    reason = str(row.get("reason", "")).casefold()
    if any(word in reason for word in ("metadata", "editorial", "publication")):
        return "exclusion_metadata"
    if any(word in reason for word in ("caption", "table", "figure")):
        return "exclusion_caption_table"
    return "exclusion_period_range"


def split_exclusion_weights(rows: list[dict]) -> None:
    """Share exclusion_audit's weight over the three classes in proportion to their rows."""
    total = len(rows) or 1
    counts = {name: 0 for name in ("exclusion_period_range", "exclusion_caption_table", "exclusion_metadata")}
    for row in rows:
        counts[exclusion_class(row)] += 1
    for name, count in counts.items():
        WEIGHTS[name] = (0.10 / 0.96) * count / total


@dataclass(frozen=True)
class IssueSpec:
    key: str
    markers: tuple[tuple[str, ...], ...]
    diagnosis: tuple[tuple[str, ...], ...]
    actions: tuple[tuple[str, ...], ...]
    locations: tuple[tuple[str, ...], ...]
    scope_item: bool = False


MISSING = (
    (r"missing", r"absent", r"no.{0,80}(?:reference|entry|record)", r"not.{0,40}(?:found|listed)"),
    (r"reference", r"entry", r"record", r"bibliograph"),
)
MISSING_ACTION = (
    (
        r"ask.{0,35}authors?",
        r"query.{0,35}authors?",
        r"request.{0,35}(?:from )?(?:the )?authors?",
        r"authors?.{0,35}confirm",
        r"author confirmation",
    ),
    (r"supply", r"provide", r"add", r"remove", r"replace", r"full reference"),
)
FORM = (
    (
        r"(?:callout|citation|author) form.{0,80}(?:wrong|incorrect|inconsistent|mismatch|defect)",
        r"(?:exactly|has|have|credits?|lists?) (?:only )?(?:one|two|three|four|six|\d+) authors?",
        r"et al.{0,80}(?:wrong|incorrect|inappropriate|omits?|invents?)",
        r"(?:omits?|suppresses?|invents?).{0,80}(?:author|coauthor)",
        r"(?:single|two|multi).author.{0,80}(?:form|record|entry|credit)",
        r"author cardinality",
    ),
)
CHANGE = (
    (
        # The editorial verb set is open: "change", "swap", "rewrite", "render" and
        # "emend" are the same instruction. What has to be present is an imperative
        # aimed at the callout, not one particular word for it.
        r"(?:change|replace|correct|revise|swap|rewrite|amend|emend|substitute|update|recast|render|reset|restyle)"
        r" (?:the |this |that )?(?:[^.\n]{0,40} )?"
        r"(?:callout|citation|narrative|author|form|item|component|entry|occurrence|text|group|string|reference)",
        r"render (?:this |the )?(?:component|citation|callout)",
        r"use (?:the )?(?:single.author|two.author|multi.author|[^.\n]{0,30} form)",
        r"\b(?:use|apply|adopt|render|set|write|give|print)\b[^.\n]{0,60}\b(?:and|&)\b",
        r"remove.{0,20}et al",
        r"recommended (?:form|citation|callout)",
        r"should (?:read|be|use)",
        r"(?:break|split|separate)[^.\n]{0,60}\b(?:apart|citation|callout|component|construction|group|item)\b",
    ),
)


ISSUES = (
    IssueSpec("F01", ((r"bergstr(?:o|ö)m",), (r"forsman",), (r"1973",)), MISSING, MISSING_ACTION, ((r"4592",), (r"4605", r"4606", r"4607", r"reference list")), True),
    IssueSpec("F02", ((r"hurk",), (r"2005",)), MISSING + ((r"2006", r"different year", r"distinct"),), MISSING_ACTION, ((r"4594",), (r"4606", r"reference.?list")), True),
    IssueSpec("F03", ((r"jacob",), (r"2007",)), MISSING + ((r"lorenz", r"2008", r"only listed"),), MISSING_ACTION, ((r"4603",), (r"4606", r"reference.?list")), True),
    IssueSpec("F04", ((r"leander",), (r"2005",)), MISSING + ((r"2007", r"2008", r"only listed"),), MISSING_ACTION, ((r"4604", r"4605"), (r"4606", r"reference.?list")), True),
    IssueSpec(
        "F05",
        ((r"smhi", r"swedish meteorological"), (r"2007",)),
        ((r"uncited", r"unused", r"listed.only", r"no formal.*(?:callout|citation)", r"no.*(?:callout|citation)"), (r"mention", r"early 70", r"without.*year", r"undated")),
        ((r"ask", r"query", r"confirm"), (r"insert", r"add.*citation", r"cite", r"remove", r"delete")),
        ((r"4607", r"reference list"), (r"4595", r"methods", r"body")),
        True,
    ),
    IssueSpec(
        "F06",
        ((r"stowa",), (r"smits",), (r"2004",)),
        ((r"author", r"credit", r"publisher", r"identity", r"authorship"),),
        ((r"ask", r"query", r"confirm"), (r"smits",), (r"change", r"replace", r"supply", r"add")),
        ((r"4591",), (r"4607", r"reference list")),
        True,
    ),
    IssueSpec("F07", ((r"bergstr(?:o|ö)m",), (r"1994",), (r"carlsson",)), FORM, CHANGE + ((r"bergstr(?:o|ö)m.{0,40}(?:and|&)\s+carlsson",),), ((r"4595",), (r"4606",))),
    IssueSpec("F08", ((r"warmerdam",), (r"2001",), (r"(?:de |wit de|de wit)",)), FORM, CHANGE + ((r"warmerdam.{0,50}(?:and|&)\s+(?:de )?wit",),), ((r"4593",), (r"4607",))),
    IssueSpec("F09", ((r"lorenz\s+et al",), (r"2008",), (r"jacob",)), FORM, CHANGE + ((r"lorenz.{0,35}(?:and|&)\s+jacob",),), ((r"4593",), (r"4606",))),
    IssueSpec("F10", ((r"leander",), (r"2007",), (r"buishand",)), FORM, CHANGE + ((r"leander.{0,45}(?:and|&)\s+buishand",),), ((r"4593", r"4595", r"4597", r"4598", r"4603"), (r"4606",))),
    IssueSpec(
        "F11",
        ((r"(?:wit de|de wit)",), (r"2001a",), (r"single.author", r"one author", r"credits? only", r"invent.*author", r"et al")),
        FORM,
        CHANGE + ((r"(?:de wit|wit de)(?!\s+et al).{0,20}2001a", r"remove.*et al", r"single.author form"),),
        ((r"4592", r"4604"), (r"4607",)),
    ),
    IssueSpec(
        "F12",
        ((r"de wit", r"wit de"), (r"2001a",), (r"2001(?![a-z0-9])", r"unsuffixed", r"suffix")),
        ((r"suffix", r"unsuffixed", r"year.*mismatch", r"no.*2001.*entry"),),
        CHANGE + ((r"de wit.{0,20}2001a", r"add.*suffix", r"use.*2001a"),),
        ((r"4592",), (r"4607",)),
    ),
    IssueSpec("F13", ((r"de wit",), (r"2007a",), (r"six author", r"multi.author", r"et al", r"coauthor")), FORM, CHANGE + ((r"de wit et al.{0,20}2007a",),), ((r"4592",), (r"4607",))),
    IssueSpec("F14", ((r"de wit",), (r"2007b",), (r"three author", r"multi.author", r"buiteveld", r"deursen")), FORM, CHANGE + ((r"de wit et al.{0,20}2007b",),), ((r"4604",), (r"4607",))),
    IssueSpec(
        "F15",
        ((r"de wit",), (r"2007(?![a-z0-9])",), (r"2007a",), (r"2007b",)),
        ((r"no.*unsuffixed", r"unsuffixed.*(?:missing|absent|not listed)", r"ambiguous"), (r"low.flow", r"context")),
        (MISSING_ACTION[0], (r"2007a",), (r"et al", r"intended work", r"correct identity")),
        ((r"4605",), (r"4607",)),
    ),
    IssueSpec(
        "F16",
        ((r"leander",), (r"2007",), (r"2008",), (r"buishand",)),
        ((r"compact", r"multi.year", r"split", r"two.author", r"different author"),),
        ((r"(?:split|separate).{0,60}(?:citation|callout|component|year|item|construction)",), (r"leander.{0,45}(?:and|&)\s+buishand.{0,25}2007",)),
        ((r"4598",), (r"4606",)),
    ),
    IssueSpec(
        "F17",
        ((r"leander",), (r"2007",), (r"2008",), (r"four author", r"van den hurk", r"de wit")),
        ((r"compact", r"multi.year", r"split", r"singular", r"different author"),),
        ((r"(?:split|separate).{0,60}(?:citation|callout|component|year|item|construction)",), (r"leander et al.{0,25}2008",)),
        ((r"4598",), (r"4606",)),
    ),
)


CLEARANCES = {
    "C01": ((r"ashagrie",), (r"2006",)),
    "C02": ((r"bakker",), (r"2008",)),
    "C03": ((r"bergstr(?:o|ö)m",), (r"2001",), (r"accent", r"diacritic", r"unicode")),
    "C04": ((r"hurk van den", r"van den hurk"), (r"2006",), (r"particle", r"inversion", r"capital")),
    "C05": ((r"schrojenstein",), (r"2004",), (r"capital", r"particle", r"same author")),
    "C06": ((r"booij",), (r"2002b",), (r"suffix",)),
    "C07": ((r"wit de", r"de wit"), (r"particle", r"inversion", r"capital")),
    "C08": ((r"leander",), (r"2008",), (r"four.author", r"et al")),
}

CLEAR_SEMANTICS = (
    r"\bclear(?:ed|ance)?\b",
    # The rubric states the report need not use the word "cleared" if it says
    # unambiguously that the identity matches and no change is needed, so the
    # no-change verb set is open in the same way the editorial verb set is.
    r"no (?:identity )?(?:repair|correction|change|edit|amendment|action) (?:is )?(?:needed|warranted|required)",
    r"(?:released|retained|left|kept|passed) (?:as printed|as written|unchanged|without (?:any )?(?:change|edit|repair))",
    r"(?:forms?|callout|citation|record|entry|author.year|suffix).{0,80}(?:are|is|refer to|denote|name).{0,20}the same (?:work|record|identity)",
    r"no (?:identity )?(?:repair|correction) (?:is )?(?:needed|warranted)",
    r"(?:forms?|callout|citation|record|entry|author.year|suffix).{0,80}(?:agree|match|compatible|same identity)",
    r"(?:agree|match|compatible).{0,80}(?:forms?|callout|citation|record|entry|identity|author.year|suffix)",
    r"not (?:an? )?(?:issue|error|discrepancy|unused record)",
    r"(?:do|must) not (?:change|correct|repair)",
    r"does not (?:create|indicate|show).{0,45}(?:different|mismatch|error)",
)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("\u00ad", "")
    value = value.replace("–", "-").replace("—", "-")
    value = re.sub(r"[^\S\n]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def matches_group(text: str, group: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in group)


def group_fraction(text: str, groups: tuple[tuple[str, ...], ...]) -> float:
    if not groups:
        return 1.0
    return sum(matches_group(text, group) for group in groups) / len(groups)


def row_context(text: str, key: str, radius: int = 2) -> str:
    """Return the bounded table/block context around a stable row identifier."""
    lines = text.splitlines()
    hits = [
        index
        for index, line in enumerate(lines)
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", line, flags=re.IGNORECASE)
    ]
    if not hits:
        return ""
    start = max(0, hits[0] - radius)
    end = min(len(lines), hits[0] + radius + 1)
    return "\n".join(lines[start:end])


def row_span(text: str, key: str, limit: int = 8) -> str:
    """Return only the text that belongs to one register row.

    `row_context` takes a fixed radius of neighbouring lines, so a per-row
    judgement (owner, state, status, explicitness) could be satisfied by the
    row above or below. In a register every row carries the same vocabulary,
    so that makes a flipped column invisible: A07 reads `confirmed` from A06.
    The span therefore starts at the row's own line and stops at the next line
    that opens another row of the same family, or at the next heading, which
    keeps wrapped rows intact without borrowing a neighbour's cells.
    """
    lines = text.splitlines()
    key_pattern = rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])"
    start = next(
        (index for index, line in enumerate(lines) if re.search(key_pattern, line, flags=re.IGNORECASE)),
        None,
    )
    if start is None:
        return ""
    prefix = re.match(r"([A-Za-z]+)", key)
    sibling = (
        re.compile(rf"(?<![A-Za-z0-9]){prefix.group(1)}\d+(?![A-Za-z0-9])", flags=re.IGNORECASE)
        if prefix
        else None
    )
    end = start + 1
    while end < len(lines) and end - start < limit:
        line = lines[end]
        if re.match(r"^#{1,6}\s", line):
            break
        if sibling is not None and sibling.search(line) and not re.search(key_pattern, line, flags=re.IGNORECASE):
            break
        end += 1
    return "\n".join(lines[start:end])


def section_context(text: str, heading_fragment: str) -> str:
    """Limit row lookup to the ledger section so IDs reused in mappings do not collide."""
    lines = text.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if re.search(r"^#{1,3}\s+", line) and heading_fragment.casefold() in line.casefold()
    ]
    if not starts:
        return ""
    start = starts[0]
    ends = [
        index
        for index in range(start + 1, len(lines))
        if re.match(r"^##\s+", lines[index])
    ]
    end = ends[0] if ends else len(lines)
    return "\n".join(lines[start:end])


def _top_sections(text: str) -> list[str]:
    """Split the report at its own `##` headings."""
    blocks = re.split(r"(?=^##\s)", text, flags=re.MULTILINE)
    return [block for block in blocks if block.strip()]


def keyed_section(text: str, prefix: str, require: str | None = None,
                  avoid: str | None = None) -> str:
    """Find a register by the shape of its rows instead of by its heading.

    The brief fixes no heading for any register and the rubric states that
    labels and Markdown structure do not affect scoring, so locating a ledger by
    a literal heading fragment kills a report that calls its occurrence ledger
    an "in-text callout inventory". A register is identified instead by the rows
    it carries: the section holding the most lines that open with this family's
    row identifier (optionally constrained by what the row must or must not also
    contain). This is still a bounded scope -- a scattered list of identifiers
    elsewhere cannot win against the actual register -- and it never falls back
    to the whole document, so a report that filed no such register still scores
    zero for it.
    """
    row = re.compile(rf"^\s*(?:#{{2,6}}\s+)?(?:[-*+]\s*)?\|?\s*(?:\*\*)?{prefix}\d+\b",
                     flags=re.IGNORECASE | re.MULTILINE)
    need = re.compile(require, re.IGNORECASE) if require else None
    skip = re.compile(avoid, re.IGNORECASE) if avoid else None
    best, best_count = "", 0
    for block in _top_sections(text):
        count = 0
        for line in block.splitlines():
            if not row.match(line):
                continue
            if need is not None and not need.search(line):
                continue
            if skip is not None and skip.search(line):
                continue
            count += 1
        if count > best_count:
            best, best_count = block, count
    return best


def register_scope(text: str, heading_fragment: str, prefix: str,
                   require: str | None = None, avoid: str | None = None,
                   anchors: list[list[str]] | None = None, kind: str = "") -> str:
    """Heading first (cheap and exact), then Golden's row prefix, then row content."""
    return (
        section_context(text, heading_fragment)
        or keyed_section(text, prefix, require, avoid)
        or (content_section(text, anchors, kind) if anchors else "")
    )


# ---------------------------------------------------------------------------
# Register rows located by what they record, not by Golden's own row ids.
#
# Every register in this rubric is keyed by an identifier Golden invented
# (O01-O50, R01-R28, E01-E35, P01-P19, K01-K10, A01-A17). The brief fixes no
# heading and no identifier for any register, and the rubric states that row
# labels may vary and that a register is located by the shape of its rows. A
# lookup that only accepts Golden's literal key therefore scores a complete,
# correct ledger at zero whenever the report numbered its own rows B001 or
# R010 or keyed its ownership matrix by the finding. The content anchor below
# is the fallback: Golden's key first (so a report that used it is unaffected),
# then the row the report wrote for that same record.
ROW_IDENTIFIER = re.compile(r"(?:^|\|)\s*(?:[-*+]\s*)?(?:\*\*)?([A-Za-z]{1,4})[-\u2013\s]?\d{1,3}\b")


def _anchor_of(*values: str) -> list[str]:
    """Identifying tokens of one expected record: its names, years and page."""
    tokens: list[str] = []
    for value in values:
        if not value:
            continue
        tokens.extend(_name_tokens(value))
        tokens.extend(_year_tokens(value))
    return sorted(set(tokens))


def _anchor_line(section: str, anchor: list[str]) -> int | None:
    if not anchor:
        return None
    for index, line in enumerate(section.splitlines()):
        lowered = line.casefold()
        if all(token in lowered for token in anchor):
            return index
    return None


def anchored_context(section: str, key: str, anchor: list[str], radius: int = 2) -> str:
    context = row_context(section, key, radius)
    if context:
        return context
    index = _anchor_line(section, anchor)
    if index is None:
        return ""
    lines = section.splitlines()
    return "\n".join(lines[max(0, index - radius): index + radius + 1])


def anchored_span(section: str, key: str, anchor: list[str], limit: int = 8) -> str:
    span = row_span(section, key, limit)
    if span:
        return span
    index = _anchor_line(section, anchor)
    if index is None:
        return ""
    lines = section.splitlines()
    end = index + 1
    while end < len(lines) and end - index < limit:
        if re.match(r"^#{1,6}\s", lines[end]) or ROW_IDENTIFIER.match(lines[end]):
            break
        end += 1
    return "\n".join(lines[index:end])


def row_identifier(context: str, key: str) -> float:
    """The register gave this record an addressable row of its own."""
    if key.casefold() in context.casefold():
        return 1.0
    first = context.splitlines()[0] if context else ""
    return 1.0 if ROW_IDENTIFIER.search(first) else 0.0


def content_section(text: str, anchors: list[list[str]], kind: str = "") -> str:
    """Locate a register by the records its rows carry, whatever they are keyed by.

    Counting anchor hits alone can land on a discrepancy-findings section, which
    discusses the same authors and years as the register does. The register's
    own subject word ("patch", "exclusion", "collision", "ownership") is
    therefore used to choose among the blocks that carry the records, not to
    find them: the brief fixes no heading, so a block still qualifies on its
    rows alone when no heading names the register.
    """
    scored: list[tuple[int, bool, str]] = []
    for block in _top_sections(text):
        lowered = [line.casefold() for line in block.splitlines()]
        count = 0
        for anchor in anchors:
            if anchor and any(all(token in line for token in anchor) for line in lowered):
                count += 1
        heading = lowered[0] if lowered else ""
        named = bool(kind) and bool(re.search(kind, heading, re.IGNORECASE))
        scored.append((count, named, block))
    if not scored:
        return ""
    best_count = max(item[0] for item in scored)
    if best_count < 2:
        return ""
    carrying = [item for item in scored if item[0] >= 2]
    named = [item for item in scored if item[1] and item[0] >= 1]
    pool = named or carrying
    return max(pool, key=lambda item: item[0])[2]



def _year_tokens(value: str) -> list[str]:
    return re.findall(r"(?:19|20)\d{2}[a-z]?", value.casefold())


def _name_tokens(value: str) -> list[str]:
    stop = {
        "and", "et", "al", "the", "of", "in", "on", "for", "with", "a", "an",
        "or", "component", "none", "used", "linked", "form", "defect", "candidate",
    }
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    tokens = re.findall(r"[A-Za-z]{3,}", value.casefold())
    return [token for token in tokens if token not in stop]


def _token_fraction(context: str, expected: str, *, minimum: int = 1) -> float:
    """Match author/year evidence without requiring a particular Markdown layout."""
    normalized_context = normalize(context)
    years = _year_tokens(expected)
    names = _name_tokens(expected)
    checks: list[bool] = []
    checks.extend(year in normalized_context for year in years)
    if names:
        # The first and last distinctive names are sufficient for a wrapped row;
        # requiring every initial would make equivalent abbreviated ledgers fail.
        selected = names if len(names) <= 2 else [names[0], names[-1]]
        checks.extend(name in normalized_context for name in selected)
    if not checks:
        return 0.0
    return sum(checks) / len(checks) if sum(checks) >= minimum else 0.0


def local_row_id(context: str, key: str) -> str:
    """The identifier the report itself gave this row, for cross-register checks."""
    if key.casefold() in context.casefold():
        return key
    first = context.splitlines()[0] if context else ""
    match = ROW_IDENTIFIER.search(first)
    return match.group(0).strip("| *") if match else key


def score_occurrence_ledger(text: str, rows: list[dict[str, str]],
                            aliases: dict[str, str] | None = None) -> tuple[float, dict[str, float]]:
    anchors = {row["key"]: _anchor_of(row["components"], row["printed_page"]) for row in rows}
    text = register_scope(text, "body-citation occurrence ledger", "O",
                          anchors=list(anchors.values()), kind=r"occurrence|body.?citation|body citation|in.?text|callout") or text
    values: dict[str, float] = {}
    for row in rows:
        context = anchored_context(text, row["key"], anchors[row["key"]])
        if not context:
            values[row["key"]] = 0.0
            continue
        if aliases is not None:
            aliases[row["key"]] = local_row_id(context, row["key"])
        expected_markers = " ".join((row["observed"], row["components"]))
        expected_mapping = row["mapping"].casefold()
        checks = [
            row_identifier(context, row["key"]),
            1.0 if row["printed_page"] in context else 0.0,
            _token_fraction(context, expected_markers),
            1.0 if all(token.casefold() in context.casefold() for token in re.findall(r"(?:O|R)\d+|none", expected_mapping)) else 0.0,
        ]
        values[row["key"]] = round(
            0.15 * checks[0] + 0.15 * checks[1] + 0.25 * checks[2] + 0.45 * checks[3],
            4,
        )
    return (sum(values.values()) / len(values) if values else 0.0), values


def score_reference_ledger(text: str, rows: list[dict[str, str]]) -> tuple[float, dict[str, float]]:
    # The end-reference ledger and the reverse mapping table are both keyed by
    # record identifiers. They are told apart by what the row carries: a ledger
    # row dates the record, a reverse-mapping row points at occurrence rows.
    anchors = {row["key"]: _anchor_of(row["head"], row["year"]) for row in rows}
    text = register_scope(text, "end-reference ledger", "R",
                          require=r"(?:19|20)\d{2}", avoid=r"(?<![A-Za-z0-9])O\d+",
                          anchors=list(anchors.values()), kind=r"reference|end.?list|bibliograph") or text
    values: dict[str, float] = {}
    for row in rows:
        context = anchored_context(text, row["key"], anchors[row["key"]])
        if not context:
            values[row["key"]] = 0.0
            continue
        title_words = _name_tokens(row["title"])
        title_hit = bool(title_words) and sum(word in context.casefold() for word in title_words[:3]) >= min(2, len(title_words))
        checks = [
            row_identifier(context, row["key"]),
            1.0 if row["printed_page"] in context else 0.0,
            1.0 if row["year"].casefold() in context.casefold() else 0.0,
            _token_fraction(context, row["head"]),
            1.0 if title_hit else 0.0,
            1.0 if row.get("cardinality", "").casefold() in context.casefold() else 0.0,
        ]
        values[row["key"]] = round(
            0.14 * checks[0] + 0.10 * checks[1] + 0.14 * checks[2] + 0.24 * checks[3] + 0.20 * checks[4] + 0.18 * checks[5],
            4,
        )
    return (sum(values.values()) / len(values) if values else 0.0), values


def score_mapping_control(
    text: str, reference_rows: list[dict[str, str]], occurrence_rows: list[dict[str, str]],
    aliases: dict[str, str] | None = None
) -> tuple[float, dict[str, float]]:
    """Check the reverse record-to-occurrence view, including explicit absences."""
    # The reverse view is located by the shape of its rows, not by a heading:
    # a report may head a section "bidirectional mapping controls" and carry the
    # record-to-occurrence links in its reference ledger instead. Both candidate
    # scopes are read and the one that actually holds the reverse rows is used.
    candidates: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.search(r"^#{1,3}\s+.*(?:bidirectional|reverse|mapping control)", line, flags=re.IGNORECASE):
            candidates.append("\n".join(lines[index : min(len(lines), index + len(reference_rows) * 2 + 12)]))
            break
    alias_pattern = "|".join(
        sorted({re.escape(value) for value in (aliases or {}).values()} | {r"(?<![A-Za-z0-9])O\d+"})
    )
    candidates.append(keyed_section(text, "R", require=rf"{alias_pattern}|\bnone\b"))
    best_values: dict[str, float] = {}
    best_total = -1.0
    for section in candidates:
        values = _mapping_values(section, reference_rows, occurrence_rows, aliases)
        total = sum(values.values())
        if total > best_total:
            best_values, best_total = values, total
    return (sum(best_values.values()) / len(best_values) if best_values else 0.0), best_values


def _mapping_values(section: str, reference_rows: list[dict[str, str]],
                    occurrence_rows: list[dict[str, str]],
                    aliases: dict[str, str] | None) -> dict[str, float]:
    values: dict[str, float] = {}
    for row in reference_rows:
        key = row["key"]
        anchor = _anchor_of(row["head"], row["year"])
        context = anchored_context(section, key, anchor) if section else ""
        if not context:
            values[key] = 0.0
            continue
        expected_occurrences = [
            item["key"]
            for item in occurrence_rows
            if key in item.get("mapping", "").split("; ")
        ]
        # The reverse table may use a different separator, but must retain all
        # linked row identifiers or say `none` for a listed-only record.
        # The reverse view points at the occurrence rows by whatever identifier
        # the report's own occurrence ledger gave them, so the link is checked
        # against that identifier, not against Golden's O-numbering.
        required = [(aliases or {}).get(item, item) for item in expected_occurrences] or ["none"]
        hit = sum(item.casefold() in context.casefold() for item in required) / len(required)
        values[key] = round((0.35 + 0.65 * hit) * row_identifier(context, key), 4)
    return values


# ---------------------------------------------------------------------------
# Contract deductions. Each one charges an affirmative error the
# instruction or the reference forbids in as many words. None of them fires on
# Golden. They are checked inside the report's own registers, never on free
# prose, and each carries a negation guard so a row that warns *against* the
# error is not charged for naming it.
ROW_OPENER = re.compile(r"^\s*(?:[-*+]\s*)?\|?\s*(?:\*\*)?[A-Za-z]{1,4}[-\u2013\s]?\d{1,3}\b")
SHEET_LOCATOR = re.compile(r"\b(?:sheet|physical\s+(?:p\.|pp\.|page)|pdf\s+(?:p\.|pp\.|page))\s*\d{1,2}\b", re.IGNORECASE)
PRINTED_FOLIO = re.compile(r"\b4(?:589|59\d|6[01]\d)\b")
# "p. 4620" / "folio 4620": a locator, not the sheet-to-folio arithmetic
# ("folio 4588 + n"), which is a correct statement of the mapping.
FOLIO_LOCATOR = re.compile(r"(?:\bpp?\.|\bpages?\b|\bfolios?\b)\s*(4\d{3})(?!\s*[-+\u2013]?\s*(?:\*?n\*?|sheet))", re.IGNORECASE)
RECORD_SHAPE = re.compile(r",\s*\d{1,3},\s*\d{1,4}\s*[-\u2013]\s*\d{1,4},\s*(?:19|20)\d{2}")
PLACEHOLDER = re.compile(r"<[^>]{1,30}>|\[(?:title|source|journal|to be|tbd)[^\]]{0,30}\]|\btbd\b|\bunknown\b|not supplied|\(absent\)", re.IGNORECASE)
COLLAPSED_PATCH = re.compile(r"\(\s*(?:x|\u00d7)?\s*([2-9]|\d\d)\s+occurrences?\s*\)|\b(?:all|every)\s+(?:\w+\s+){0,2}occurrences?\b|\bglobal(?:ly)?\s+(?:substitut|replac)", re.IGNORECASE)
COLLAPSE_GUARD = re.compile(r"\bnot\b|\bnever\b|\bno\b|separate|distinct|one row per|individually|deliberately", re.IGNORECASE)


def _register_rows(section: str) -> list[str]:
    return [line for line in section.splitlines() if ROW_OPENER.match(line)]


# The manuscript's own text, extracted once with `pdftotext -layout` from the
# frozen PDF (its digest is EXPECTED_PDF_SHA256). A "volume, pages" fragment is
# compared on its digits only, so layout, dashes and spacing do not matter.
MANUSCRIPT_TEXT = Path(__file__).resolve().parent / "manuscript_text.txt"
# "Hydrol., 19, 101-118": a volume and page range that follows a named source
# (a word or abbreviation, then a comma). A run of line numbers ("ll. 7-8, 15,
# 20-21") follows a number, not a name, and is not read as one. The manuscript
# side is read without that condition and across line breaks, so every range it
# prints is known.
VOLUME_PAGES = re.compile(r"(?<=[A-Za-z.)])\s*,\s*(\d{1,3}),\s*(\d{1,4})\s*-\s*(\d{1,4})\b")
ANY_VOLUME_PAGES = re.compile(r"\b(\d{1,3}),\s*(\d{1,4})\s*-\s*(\d{1,4})\b")


def _dashes(value: str) -> str:
    return value.replace("–", "-").replace("—", "-").replace("−", "-")


def scoring_error(message: str) -> None:
    """The scorer cannot evaluate this submission: exit non-zero without printing a reward."""
    sys.stderr.write(f"SCORING ERROR: {message}\n")
    sys.stderr.flush()
    os._exit(2)


def _digits_key(volume: str, first: str, last: str) -> str:
    return f"{int(volume)},{int(first)}-{int(last)}"


def manuscript_volume_pages() -> set[str]:
    try:
        source = MANUSCRIPT_TEXT.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        scoring_error(f"cannot read {MANUSCRIPT_TEXT}: {exc}")
    source = re.sub(r"\s+", " ", _dashes(source))
    return {_digits_key(*match) for match in ANY_VOLUME_PAGES.findall(source)}


def foreign_record_lines(section: str) -> list[str]:
    """Lines of a register that give a volume and page range the manuscript never prints."""
    known = manuscript_volume_pages()
    if not known:
        return []
    found = []
    for line in section.splitlines():
        if PLACEHOLDER.search(line) or not re.search(r"(?:19|20)\d{2}", line):
            continue
        if any(_digits_key(*match) not in known for match in VOLUME_PAGES.findall(_dashes(line))):
            found.append(line)
    return found


def contract_violations(text: str, sections: dict[str, str], unresolved: list[list[str]]) -> list[tuple[str, list[str]]]:
    """Errors the brief and the reference forbid outright, read in the registers."""
    damage: list[tuple[str, list[str]]] = []

    # D07 - the brief: cite by the printed folio, "the sheet number may be given
    # alongside it but does not replace it".
    for name in ("findings", "patches", "exclusions"):
        rows = _register_rows(sections.get(name, ""))
        bad = [row for row in rows if SHEET_LOCATOR.search(row) and not PRINTED_FOLIO.search(row)]
        if bad:
            damage.append((f"locator given as a PDF sheet number with no printed folio in the {name} register", ["D07"]))

    # D08 - RUBRIC: "a handoff that points at pages the manuscript does not
    # have ... is not usable". The manuscript's printed folios run 4589-4618.
    outside = {
        page for page in FOLIO_LOCATOR.findall(text)
        if not 4589 <= int(page) <= 4618
    }
    if outside:
        damage.append((f"manuscript location cited at printed folio(s) {sorted(outside)} the manuscript does not have", ["D08"]))

    # D09 - the brief: do not "rely on bibliographic facts not present in the
    # supplied material"; Golden F01: "do not infer the missing metadata".
    # Two readings, either one charges the register once:
    #   - a full record shape (", vol, pages, year") on a row that names a
    #     cited-only work the reference list does not contain;
    #   - a "volume, first-last page" fragment on any line of the register that
    #     the manuscript itself never prints, i.e. publication data the report
    #     brought in from outside the supplied material.
    for name in ("findings", "patches"):
        charged = False
        for row in _register_rows(sections.get(name, "")):
            lowered = row.casefold()
            if not RECORD_SHAPE.search(row) or PLACEHOLDER.search(row):
                continue
            if any(anchor and all(token in lowered for token in anchor) for anchor in unresolved):
                charged = True
                break
        if not charged:
            charged = bool(foreign_record_lines(sections.get(name, "")))
        if charged:
            damage.append((f"bibliographic record supplied for a work the reference list does not contain ({name} register)", ["D09"]))

    # D10 - the brief: "repeated occurrences must not be collapsed into one patch".
    for row in _register_rows(sections.get("patches", "")):
        if COLLAPSED_PATCH.search(row) and not COLLAPSE_GUARD.search(row):
            damage.append(("repeated occurrences collapsed into a single patch row", ["D10"]))
            break
    return damage


def _loose_pattern(value: str) -> str:
    """Literal match for a citation form, tolerant of whitespace and wrapping."""
    return re.sub(r"(?:\\\s)+", r"\\s*", re.escape(normalize(value)))


CURRENT_COLUMN = r"current|existing|as\s+printed|as\s+written|defective|observed|present\s+form|before"
PROPOSED_COLUMN = r"proposed|corrected|replacement|repaired|target\s+form|should\s+read|after|new\s+form"


def patch_column_order(text: str) -> int:
    """+1 if the register declares current before proposed, -1 if reversed, 0 if unknown.

    The direction check must read the report's own layout. A register that
    heads its columns `Proposed form | Current form` is legible to a copyeditor
    and must not be scored as inverted just because the literals appear in the
    other order.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.count("|") < 3:
            continue
        # Only a header row declares the column order. A data row can carry
        # "proposed R026" in one cell and "observed" in another and would
        # otherwise invert the whole register's direction reading.
        following = lines[index + 1] if index + 1 < len(lines) else ""
        if not re.match(r"^\s*\|?\s*:?-{2,}", following):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        current_index = next((i for i, cell in enumerate(cells) if re.search(CURRENT_COLUMN, cell, re.IGNORECASE)), None)
        proposed_index = next((i for i, cell in enumerate(cells) if re.search(PROPOSED_COLUMN, cell, re.IGNORECASE)), None)
        if current_index is None or proposed_index is None or current_index == proposed_index:
            continue
        return 1 if current_index < proposed_index else -1
    return 0


def _patch_direction(context: str, key: str, current: str, proposed: str, order: int = 1) -> float:
    """A patch must say which form is defective and which one replaces it.

    The two forms share nearly all of their tokens, so token presence cannot
    distinguish a repair from its inverse. The row is therefore read
    positionally, in the column order the register itself declares: the
    defective form has to be on the side the header says holds it.
    """
    # Read the row that carries the defective form. Selecting it by Golden's own
    # patch id reads several rows at once whenever the report numbered its
    # register differently, and a neighbouring row then supplies the other form.
    line = next(
        (item for item in context.splitlines()
         if re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", item, flags=re.IGNORECASE)),
        None,
    )
    if line is None:
        line = next(
            (item for item in context.splitlines()
             if re.search(_loose_pattern(current), normalize(item))),
            context,
        )
    haystack = normalize(line)
    current_match = re.search(_loose_pattern(current), haystack)
    proposed_match = re.search(_loose_pattern(proposed), haystack)
    if current_match is None or proposed_match is None:
        # Written some other way: neither confirmed nor demonstrably inverted.
        return 0.5
    expected_first = current_match.start() < proposed_match.start()
    return 1.0 if expected_first == (order >= 0) else 0.0


def score_patches(text: str, rows: list[dict[str, str]]) -> tuple[float, dict[str, float]]:
    anchors = {
        row["key"]: sorted(set(_anchor_of(row["current"])) | set(re.findall(r"\b4[56]\d\d\b", row["location"])))
        for row in rows
    }
    # A patch row carries both forms; an occurrence-ledger row carries only the
    # defective one, so the register is located on rows that show the repair.
    section_anchors = [
        sorted(set(_anchor_of(row["current"])) | set(_anchor_of(row["proposed"])))
        for row in rows
    ]
    text = register_scope(text, "confirmed repair patch register", "P",
                          anchors=section_anchors, kind=r"patch|repair") or text
    values: dict[str, float] = {}
    order = patch_column_order(text)
    directions: dict[str, float] = {}
    for row in rows:
        context = anchored_context(text, row["key"], anchors[row["key"]])
        if not context:
            values[row["key"]] = 0.0
            continue
        current_tokens = _year_tokens(row["current"]) + _name_tokens(row["current"])
        proposed_tokens = _year_tokens(row["proposed"]) + _name_tokens(row["proposed"])
        current_hit = sum(token in context.casefold() for token in set(current_tokens)) / max(1, len(set(current_tokens)))
        proposed_hit = sum(token in context.casefold() for token in set(proposed_tokens)) / max(1, len(set(proposed_tokens)))
        checks = [
            row_identifier(context, row["key"]),
            1.0
            if re.search(r"(?:physical|printed)\D*\d", row["location"], flags=re.IGNORECASE)
            and any(page in context for page in re.findall(r"\d+", row["location"]))
            else 0.0,
            current_hit,
            proposed_hit,
            1.0 if row["record"].casefold() in context.casefold() else 0.0,
            1.0 if re.search(r"evidence|record|author|year|matched|split|two.author|single.author", context, flags=re.IGNORECASE) else 0.0,
        ]
        direction = _patch_direction(context, row["key"], row["current"], row["proposed"], order)
        directions[row["key"]] = direction
        values[row["key"]] = round(
            direction
            * (
                0.15 * checks[0] + 0.15 * checks[1] + 0.20 * checks[2]
                + 0.30 * checks[3] + 0.10 * checks[4] + 0.10 * checks[5]
            ),
            4,
        )
    values["_column_order"] = float(order)
    decided = [value for value in directions.values() if value != 0.5]
    values["_direction_rate"] = (sum(decided) / len(decided)) if decided else 1.0
    scored = {key: value for key, value in values.items() if not key.startswith("_")}
    return (sum(scored.values()) / len(scored) if scored else 0.0), values


def _form_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z]+|\d{4}[a-z]?", normalize(value))


def _find_run(tokens: list[str], run: list[str], start: int = 0) -> int:
    for index in range(start, len(tokens) - len(run) + 1):
        if tokens[index:index + len(run)] == run:
            return index
    return -1


PATCH_ROW_ID = re.compile(r"\bp-?\d{1,3}\b", re.IGNORECASE)
DECLINED_PATCH = re.compile(r"withdrawn|would have|not a patch|rejected|declined|not applied|no change\b", re.IGNORECASE)


def score_patch_forms(text: str, rows: list[dict[str, str]]) -> float:
    """Q17: the share of the confirmed repairs the patch register executes.

    A repair is executed when one row of the report's patch register carries
    the defective form and its replacement, each as its own run of words and
    years, in the direction the register's header declares (current before
    proposed unless the header puts the proposed column first).
    """
    if not rows:
        return 0.0
    section_anchors = [sorted(set(_anchor_of(row["current"])) | set(_anchor_of(row["proposed"]))) for row in rows]
    section = register_scope(text, "confirmed repair patch register", "P",
                             anchors=section_anchors, kind=r"patch|repair")
    if not section:
        return 0.0
    order = patch_column_order(section)
    lines = []
    header = ""
    raw_lines = section.splitlines()
    for index, line in enumerate(raw_lines):
        following = raw_lines[index + 1] if index + 1 < len(raw_lines) else ""
        if re.match(r"^\s*\|?\s*:?-{2,}", following):
            header = line
            continue
        if not line.strip().startswith("|"):
            header = ""
        # A patch row names its patch; a table of withdrawn or rejected
        # candidates, or a row that declines the change, executes nothing.
        if not PATCH_ROW_ID.search(line) or DECLINED_PATCH.search(line) or DECLINED_PATCH.search(header):
            continue
        lines.append(_form_tokens(line))
    met = 0
    for row in rows:
        current, proposed = _form_tokens(row["current"]), _form_tokens(row["proposed"])
        for tokens in lines:
            first = _find_run(tokens, current)
            second = _find_run(tokens, proposed)
            if first < 0 or second < 0:
                continue
            if (first < second) == (order >= 0) or (first > second) == (order < 0):
                met += 1
                break
    return met / len(rows)


# Q18: the cleared near matches. Each supplied clearance is identified by its
# record tokens; it is met where one unit of the report (a table row, or a
# heading with the paragraph or list under it) names that record and states a
# no-change outcome for it.
CLEARED_RECORDS = {
    "C01": (r"ashagrie", r"2006"),
    "C02": (r"bakker", r"2008"),
    "C03": (r"bergstrom", r"2001"),
    "C04": (r"hurk", r"2006"),
    "C05": (r"schrojenstein",),
    "C06": (r"booij", r"2002b"),
    "C07": (r"wit de|de wit", r"particle|inversion|capitali|lower.?case|upper.?case"),
    "C08": (r"leander", r"2008"),
}
CLEARED_OUTCOME = re.compile(
    r"\bclear(?:ed|ance)?\b|\bno[- ](?:\w+ ){0,2}(?:change|repair|correction|edit|action|patch|swap|merge)\b"
    r"|not (?:a |an )?(?:defect|discrepancy|error|issue|duplicate|unused record)"
    r"|\b(?:do|must|should) not\b[^.|\n]{0,30}\b(?:change|merge|repair|alter|correct|strip|substitute|swap|expand|split)"
    r"|same (?:work|identity|author|person|record)|compatible|\bkeep (?:both|all|the)\b|leave[^.|\n]{0,30}\b(?:intact|unchanged)")


def report_units(text: str) -> list[str]:
    units: list[str] = []
    block: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            if block:
                units.append("\n".join(block))
                block = []
            units.append(stripped)
        elif re.match(r"^#{1,6}\s", stripped):
            if block:
                units.append("\n".join(block))
            block = [stripped]
        elif stripped:
            block.append(stripped)
    if block:
        units.append("\n".join(block))
    return units


def score_cleared(text: str, keys: set[str]) -> float:
    wanted = [key for key in CLEARED_RECORDS if key in keys]
    if not wanted:
        return 0.0
    units = [rebuilt_normalize(unit).replace("*", "").replace("`", "") for unit in report_units(text)]
    met = 0
    for key in wanted:
        patterns = CLEARED_RECORDS[key]
        if any(all(re.search(pattern, unit) for pattern in patterns) and CLEARED_OUTCOME.search(unit)
               for unit in units):
            met += 1
    return met / len(wanted)


def score_exclusions(text: str, rows: list[dict[str, str]]) -> tuple[float, dict[str, float]]:
    """Score page-local treatment of date-like strings that are not citations."""
    anchors = {
        row["key"]: sorted({normalize(row["token"]).casefold(), row["printed_page"]} - {""})
        for row in rows
    }
    text = register_scope(text, "non-citation date exclusion register", "E",
                          anchors=list(anchors.values()), kind=r"exclusion|date|non.?citation|screen") or text
    values: dict[str, float] = {}
    for row in rows:
        context = anchored_context(text, row["key"], anchors[row["key"]])
        if not context:
            values[row["key"]] = 0.0
            continue
        normalized_context = normalize(context).casefold()
        token = normalize(row["token"]).casefold()
        context_words = _name_tokens(row.get("context", ""))
        context_hit = sum(word in normalized_context for word in context_words[:4]) / max(1, min(4, len(context_words)))
        reason_hit = 1.0 if re.search(r"(?:not|rather than|without).{0,80}(?:citation|callout|period|metadata|table|figure|source)", context, flags=re.IGNORECASE) else 0.0
        checks = [
            row_identifier(context, row["key"]),
            1.0 if row["printed_page"] in normalized_context else 0.0,
            1.0 if token and token in normalized_context else _token_fraction(context, row["token"]),
            context_hit,
            reason_hit,
        ]
        values[row["key"]] = round(
            0.15 * checks[0] + 0.10 * checks[1] + 0.35 * checks[2] + 0.20 * checks[3] + 0.20 * checks[4],
            4,
        )
    return (sum(values.values()) / len(values) if values else 0.0), values


CONTROL_PATTERNS = {
    "body_occurrence_groups": ("body", "occurrence", "group"),
    "atomic_author_year_components": ("atomic", "component"),
    "distinct_source_form_author_year_suffix_identities": ("distinct", "source", "form", "identit"),
    "end_reference_records": ("end", "reference", "record"),
    "records_with_one_or_more_candidate_links": ("record", "candidate", "link"),
    "cited_only_atomic_components": ("cited", "only", "component"),
    "listed_only_records": ("listed", "only", "record"),
    "confirmed_patch_rows": ("confirmed", "patch"),
    "non_citation_date_exclusion_groups": ("non", "citation", "date", "exclusion"),
    "collision_register_rows": ("collision", "register", "row"),
    "action_ownership_rows": ("action", "ownership", "row"),
    "confirmed_copyeditor_actions": ("confirmed", "copyeditor", "action"),
    "author_or_editor_holds": ("author", "editor", "hold"),
}


def score_control_totals(text: str, controls: dict[str, int]) -> tuple[float, dict[str, float]]:
    values: dict[str, float] = {}
    for key, expected in controls.items():
        patterns = CONTROL_PATTERNS.get(key, tuple(key.split("_")))
        hit = 0.0
        for line in text.splitlines():
            lowered = line.casefold()
            if all(pattern in lowered for pattern in patterns) and re.search(rf"(?<!\d){expected}(?!\d)", line):
                hit = 1.0
                break
        values[key] = hit
    return (sum(values.values()) / len(values) if values else 0.0), values


def score_collision_register(text: str, rows: list[dict[str, str]]) -> tuple[float, dict[str, float]]:
    anchors = {row["key"]: _anchor_of(row["stem"]) for row in rows}
    section = register_scope(text, "collision and inheritance register", "K",
                             anchors=list(anchors.values()), kind=r"collision|inherit|suffix|ambiguity|candidate") or text
    values: dict[str, float] = {}
    for row in rows:
        context = anchored_context(section, row["key"], anchors[row["key"]])
        if not context:
            values[row["key"]] = 0.0
            continue
        stem_tokens = _name_tokens(row["stem"]) + _year_tokens(row["stem"])
        marker_hit = sum(token in context.casefold() for token in set(stem_tokens)) / max(1, len(set(stem_tokens)))
        records = re.findall(r"r\d+|none", row["candidate_records"].casefold())
        record_hit = sum(record in context.casefold() for record in records) / max(1, len(records))
        checks = [
            row_identifier(context, row["key"]),
            marker_hit,
            record_hit,
            1.0 if row["explicitness"].casefold() in context.casefold() else 0.0,
            1.0 if row["state"].casefold() in context.casefold() else 0.0,
            1.0 if re.search(r"evidence|suffix|year|record|author|distinct|separate|missing|compact|inherited", context, re.IGNORECASE) else 0.0,
        ]
        values[row["key"]] = round(
            0.12 * checks[0] + 0.28 * checks[1] + 0.20 * checks[2] + 0.14 * checks[3] + 0.16 * checks[4] + 0.10 * checks[5],
            4,
        )
    return (sum(values.values()) / len(values) if values else 0.0), values


def score_action_ownership(text: str, rows: list[dict[str, str]], findings: list[dict[str, str]] | None = None) -> tuple[float, dict[str, float]]:
    identity = {item["key"]: item for item in (findings or [])}
    anchors = {
        row["key"]: _anchor_of(identity.get(row["finding"], {}).get("observed_item", ""))
        for row in rows
    }
    section = register_scope(text, "action-ownership matrix", "A",
                             anchors=list(anchors.values()), kind=r"action|owner") or text
    values: dict[str, float] = {}
    for row in rows:
        context = anchored_span(section, row["key"], anchors[row["key"]])
        if not context:
            values[row["key"]] = 0.0
            continue
        finding_hit = row["finding"].casefold() in context.casefold() or bool(
            anchors[row["key"]]
        ) and all(token in context.casefold() for token in anchors[row["key"]])
        owner_hit = row["owner"].casefold() in context.casefold()
        state_hit = row["state"].casefold() in context.casefold()
        precondition_hit = bool(re.search(r"author|record|confirm|retain|matched|separat|patch|supply|identify|intended", context, re.IGNORECASE))
        # `hold` versus `confirmed` is the judgement the matrix exists to record:
        # a row that names the right owner but the opposite state tells the
        # copyeditor to execute something that is still waiting on the author.
        state_factor = 1.0 if state_hit else 0.3
        values[row["key"]] = round(
            state_factor
            * (
                0.18 * row_identifier(context, row["key"])
                + 0.22 * (1.0 if finding_hit else 0.0)
                + 0.25 * (1.0 if owner_hit else 0.0)
                + 0.20 * (1.0 if state_hit else 0.0)
                + 0.15 * (1.0 if precondition_hit else 0.0)
            ),
            4,
        )
    return (sum(values.values()) / len(values) if values else 0.0), values


def clearance_blocks(scope: str, key: str) -> list[str]:
    """The record block for one cleared item, without its section heading."""
    lines = scope.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if not re.match(r"^#{2,6}\s", line):
            continue
        if not re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", line, flags=re.IGNORECASE):
            continue
        end = next(
            (position for position in range(index + 1, len(lines)) if re.match(r"^#{1,6}\s", lines[position])),
            len(lines),
        )
        # Keep the record's own heading (it may carry the disposition) but never
        # the section heading, which would supply the vocabulary by itself.
        blocks.append("\n".join(lines[index:end]))
    if not blocks:
        # No heading of its own: the record's own row, never its neighbours.
        block = row_span(scope, key)
        if block:
            blocks.append("\n".join(item for item in block.splitlines() if not re.match(r"^##\s", item)))
    return blocks


# Language that asserts the compared forms are *not* the same identity. A record
# filed under "cleared" that says this is a false repair, not a clearance.
DEFECT_CLAIM = (
    r"do(?:es)?\s+not\s+(?:agree|match)",
    r"\bincorrect\b",
    r"\bmismatch",
    r"\bdiscrepanc",
    r"must\s+be\s+(?:replaced|changed|corrected|repaired)",
    r"must\s+(?:replace|change|correct|repair)\b",
    r"repair\s+(?:is\s+)?required",
    r"\bis\s+wrong\b",
)


def claims_defect(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in DEFECT_CLAIM)


NOT_READY = (
    # The hold may be qualified ("not reference-ready", "not release-ready",
    # "not yet submission-ready"); the qualifier is the report's own wording and
    # carries no direction of its own.
    r"not\s+(?:yet\s+)?(?:[a-z]+[-\s])?ready",
    r"not\s+(?:yet\s+)?(?:cleared|approved|signed[-\s]off)\s+for\s+(?:release|submission|publication)",
    r"should\s+not\s+be\s+released",
    r"must\s+not\s+be\s+released",
    r"cannot\s+be\s+released",
    r"release\s+(?:is\s+)?(?:blocked|gated|withheld)",
    # The same hold stated with the verb first rather than the noun first.
    r"(?:withheld|held\s+back|blocked|gated)\s+from\s+(?:release|submission|publication)",
    r"hold\s+(?:release|publication)",
    r"not\s+for\s+release",
    r"must\s+wait\s+until",
)
READY_ASSERT = (
    r"(?<!not )(?<!not-)(?<!yet )(?<!yet-)\breference[-\s]ready\b",
    r"\b(?:can|may)\s+be\s+released\b",
    # "reference-ready for submission" is a hold when it is negated, and the
    # bare suffix "ready for submission" sits inside it. Requiring a word
    # boundary that is not a hyphen or letter keeps this from firing on the
    # tail of "not reference-ready for submission".
    r"(?<![-\w])(?<!not )(?<!yet )(?<!never )ready\s+for\s+(?:release|submission|publication)",
    r"no\s+(?:unresolved|outstanding|open)\s+\w+",
    r"no\s+author\s+input\s+(?:is\s+)?required",
    r"no\s+independently\s+actionable\s+findings",
)

# The brief asks for an "overall readiness decision" but fixes no heading for
# it. Reports state it under their own wording ("Readiness decision",
# "Overall readiness decision", "Verification pass and readiness decision"),
# so the decision section is looked up by any of the equivalent headings and,
# failing all of them, read from the whole report rather than from the first
# 1500 characters, which is the executive summary of a long handoff.
DECISION_HEADINGS = (
    "editorial decision",
    "readiness decision",
    "release decision",
    "publication decision",
    "overall decision",
    "readiness statement",
    "readiness assessment",
    "release recommendation",
)


def decision_scope(text: str) -> str:
    for fragment in DECISION_HEADINGS:
        section = section_context(text, fragment)
        if section:
            return section
    return text


def readiness_direction(text: str) -> tuple[float, str]:
    """The release decision is a direction, not a vocabulary.

    "unresolved records require author input" and "no unresolved records require
    author input" contain the same words; only the first is a hold.
    """
    decision = decision_scope(text)
    holds = any(re.search(pattern, decision, flags=re.IGNORECASE) for pattern in NOT_READY)
    releases = any(re.search(pattern, decision, flags=re.IGNORECASE) for pattern in READY_ASSERT)
    if holds and not releases:
        return 1.0, "hold"
    if releases:
        return 0.0, "release_asserted"
    return 0.0, "no_decision"


HOLD_STATE = (
    r"\bhold\b", r"\bopen\b", r"\bpending\b", r"\bawait", r"\bwaiting\b",
    r"\bdeferred\b", r"\bblocked\b", r"\bquery\b", r"\bunresolved\b", r"\bnot ready\b",
)
CONFIRMED_STATE = (
    r"\bconfirmed\b", r"\bapprove", r"\bexecute", r"\bactionable\b", r"\bready to apply\b",
    r"\bapply now\b", r"\bcleared to apply\b", r"\bproceed\b",
)

HOLD_FINDING = (
    r"author decision", r"author query", r"author input", r"open query",
    r"ask (?:the )?authors?", r"ask whether", r"query (?:the )?authors?",
    r"request (?:the )?(?:full|complete)", r"author.confirmed", r"authors? (?:to )?confirm",
    r"await", r"requires? (?:an? )?author", r"editor and author decide",
)
REPAIR_FINDING = (
    r"confirmed discrepanc", r"confirmed repair", r"copyedit",
    r"^- (?:recommended )?disposition:\s*(?:replace|change|use|split|render|correct|swap|amend|substitute)",
)
NO_ACTION_FINDING = (
    r"no (?:action|repair|change|edit)s? (?:is |are )?(?:required|needed|warranted)",
    r"leave (?:it |the callout |the citation )?(?:unchanged|as is)",
    r"already agrees",
    r"no further action",
    r"nothing to (?:do|change|repair)",
    r"must be left unchanged",
)


def _classify_finding(block: str) -> str:
    """hold / repair / none / unknown, read from the finding's own write-up."""
    lowered = block
    # "no action required" only counts when it is the finding's own verdict --
    # its heading or its disposition line. A correct finding may say in passing
    # that some *other* callout needs no change ("do not change the correct 2008
    # forms"), and that must not be read as closing the finding.
    verdict_lines = "\n".join(
        line for line in block.splitlines()
        if re.match(r"^#{2,6}\s", line)
        or re.match(r"^[-*]?\s*(?:recommended\s+)?(?:disposition|action|resolution|handling)\b", line, flags=re.IGNORECASE)
    )
    if any(re.search(pattern, verdict_lines, flags=re.IGNORECASE | re.MULTILINE) for pattern in NO_ACTION_FINDING):
        return "none"
    if any(re.search(pattern, lowered, flags=re.IGNORECASE | re.MULTILINE) for pattern in HOLD_FINDING):
        return "hold"
    if any(re.search(pattern, lowered, flags=re.IGNORECASE | re.MULTILINE) for pattern in REPAIR_FINDING):
        return "repair"
    return "unknown"


def _classify_state(span: str) -> str:
    """Read the state cell of one action row: hold / confirmed / unknown.

    Only the state column is read. Preconditions legitimately contain the word
    "confirms" ("author confirms the 2005 source"), so scanning the whole row
    would report every hold as confirmed.
    """
    cell = ""
    for line in span.splitlines():
        if line.count("|") >= 3:
            cells = [item.strip() for item in line.split("|") if item.strip()]
            if cells:
                cell = cells[-1]
            break
        match = re.search(r"\bstate\b\s*[:=-]\s*([^|\n.;]+)", line, flags=re.IGNORECASE)
        if match:
            cell = match.group(1)
            break
    if not cell:
        return "unknown"
    holds = any(re.search(pattern, cell, flags=re.IGNORECASE) for pattern in HOLD_STATE)
    confirms = any(re.search(pattern, cell, flags=re.IGNORECASE) for pattern in CONFIRMED_STATE)
    if holds and not confirms:
        return "hold"
    if confirms and not holds:
        return "confirmed"
    return "unknown"


def _finding_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    blocks: dict[str, str] = {}
    for index, line in enumerate(lines):
        match = re.match(r"^#{2,6}\s+.*?(?<![A-Za-z0-9])(F\d\d)(?![A-Za-z0-9])", line, flags=re.IGNORECASE)
        if not match:
            continue
        end = next((position for position in range(index + 1, len(lines)) if re.match(r"^#{1,6}\s", lines[position])), len(lines))
        blocks[match.group(1).upper()] = "\n".join(lines[index:end])
    return blocks


# A finding write-up normally labels the two forms it is about: the one the
# manuscript prints and the one that should replace it. Those labels are the
# finding's own column headers, and they are read exactly the way
# `patch_column_order` reads the register's.
FINDING_DEFECT_LABEL = re.compile(
    r"^\s*[-*|]?\s*(?:\*\*)?(?:observed(?:\s+\w+)?|current(?:\s+form)?|callout\s+as\s+printed"
    r"|as\s+printed|as\s+written|defective(?:\s+form)?|printed\s+form|existing(?:\s+form)?)"
    r"\**\s*:\s*(.+)$",
    flags=re.IGNORECASE,
)
FINDING_TARGET_LABEL = re.compile(
    r"^\s*[-*|]?\s*(?:\*\*)?(?:proposed(?:\s+form)?|corrected(?:\s+form)?|should\s+read"
    r"|target\s+form|replacement(?:\s+form)?|new\s+form)"
    r"\**\s*:\s*(.+)$",
    flags=re.IGNORECASE,
)


def register_pairs(patch_section: str) -> dict[str, list[tuple[str, str]]]:
    """The (defective, corrected) cells of each patch row, keyed by finding.

    Read positionally from the register's own header, never from the ground
    truth, so this stays a statement the report makes about itself.
    """
    pairs: dict[str, list[tuple[str, str]]] = {}
    if not patch_section:
        return pairs
    current_index = proposed_index = finding_index = None
    for line in patch_section.splitlines():
        if line.count("|") < 3:
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if current_index is None:
            found_current = next((i for i, cell in enumerate(cells) if re.search(CURRENT_COLUMN, cell, re.IGNORECASE)), None)
            found_proposed = next((i for i, cell in enumerate(cells) if re.search(PROPOSED_COLUMN, cell, re.IGNORECASE)), None)
            if found_current is not None and found_proposed is not None and found_current != found_proposed:
                current_index, proposed_index = found_current, found_proposed
                finding_index = next(
                    (i for i, cell in enumerate(cells) if re.search(r"finding|issue|item|ref", cell, re.IGNORECASE)
                     and i not in {found_current, found_proposed}),
                    None,
                )
            continue
        if max(current_index, proposed_index) >= len(cells):
            continue
        if set(cells[current_index]) <= {"-", ":", " "}:
            continue
        scope = cells[finding_index] if finding_index is not None and finding_index < len(cells) else line
        for key in {item.upper() for item in re.findall(r"(?<![A-Za-z0-9])F\d\d(?![A-Za-z0-9])", scope, re.IGNORECASE)}:
            pairs.setdefault(key, []).append((cells[current_index], cells[proposed_index]))
    return pairs


def finding_form_direction(text: str, patch_section: str) -> tuple[float, list[str]]:
    """Does each finding call the same form defective that its register does?

    The handoff states one repair on two surfaces. The register says which form
    is defective by the column it puts it in; the finding says it by the field
    it labels "observed item" / "current form". A write-up that puts the
    register's replacement under its own "observed" label and the register's
    defective form under "proposed" is the exact inverse instruction, and a
    copyeditor reading the two surfaces gets opposite orders for the same edit.
    Only findings that label both surfaces readably are counted; a write-up that
    states the forms some other way is not evidence either way.
    """
    pairs = register_pairs(patch_section)
    if not pairs:
        return 1.0, []
    conflicts: list[str] = []
    decided = 0
    for key, block in _finding_blocks(text).items():
        rows = pairs.get(key)
        if not rows:
            continue
        declared_defect = [match.group(1) for line in block.splitlines()
                           if (match := FINDING_DEFECT_LABEL.match(line))]
        declared_target = [match.group(1) for line in block.splitlines()
                           if (match := FINDING_TARGET_LABEL.match(line))]
        agree = disagree = 0
        for current, proposed in rows:
            low, high = normalize(current).casefold(), normalize(proposed).casefold()
            if not low or not high or low == high or low in high or high in low:
                continue
            for value, expected_low in ([(item, True) for item in declared_defect]
                                        + [(item, False) for item in declared_target]):
                field = normalize(value).casefold()
                has_low, has_high = low in field, high in field
                if has_low == has_high:
                    continue
                if has_low == expected_low:
                    agree += 1
                else:
                    disagree += 1
        if agree or disagree:
            decided += 1
            if disagree > agree:
                conflicts.append(key)
    if not decided:
        return 1.0, []
    return 1.0 - len(conflicts) / decided, conflicts


def report_coherence(text: str, direction_rate: float) -> dict[str, object]:
    """Cross-surface agreement, computed from the report against itself.

    The same judgement is stated on four surfaces: the finding write-up, the
    patch register, the action-ownership matrix and the release decision. A
    handoff that inverts one of them contradicts the other three, and a
    copyeditor cannot execute it: the finding says replace a callout while the
    matrix says the row is still waiting on the author, or the decision line
    releases a list whose own matrix still carries open holds. Agreement is
    therefore a property of the document, not an extra scoring dimension --
    it is measured without reference to the ground truth, and a surface that
    cannot be read confidently is not counted against the report.
    """
    blocks = _finding_blocks(text)
    patch_section = register_scope(text, "confirmed repair patch register", "P")
    action_section = register_scope(text, "action-ownership matrix", "A")
    clearance_section = register_scope(text, "cleared near matches", "C")

    patched_findings: set[str] = set()
    if patch_section:
        for line in patch_section.splitlines():
            if re.match(r"^\s*\|?\s*P\d\d\b", line, flags=re.IGNORECASE):
                patched_findings.update(item.upper() for item in re.findall(r"(?<![A-Za-z0-9])F\d\d(?![A-Za-z0-9])", line, flags=re.IGNORECASE))

    states: dict[str, str] = {}
    if action_section:
        for key in sorted({item.upper() for item in re.findall(r"(?<![A-Za-z0-9])A\d\d(?![A-Za-z0-9])", action_section, flags=re.IGNORECASE)}):
            span = row_span(action_section, key)
            findings = [item.upper() for item in re.findall(r"(?<![A-Za-z0-9])F\d\d(?![A-Za-z0-9])", span, flags=re.IGNORECASE)]
            if len(findings) == 1:
                states[findings[0]] = _classify_state(span)

    conflicts: list[str] = []
    checked = 0
    for key in sorted(blocks):
        side = _classify_finding(blocks[key])
        state = states.get(key, "unknown")
        patched = key in patched_findings if patch_section else None
        if side == "unknown" and state == "unknown":
            continue
        checked += 1
        bad = False
        if patched is not None and state != "unknown":
            bad |= patched and state == "hold"
            bad |= (not patched) and state == "confirmed"
        if side != "unknown" and state != "unknown":
            bad |= side == "hold" and state == "confirmed"
            bad |= side == "repair" and state == "hold"
            bad |= side == "none" and state in {"confirmed", "hold"}
        if side != "unknown" and patched is not None:
            bad |= side == "repair" and not patched
            bad |= side in {"hold", "none"} and patched
        if bad:
            conflicts.append(key)
    finding_rate = 1.0 - len(conflicts) / checked if checked else 1.0

    clearance_conflicts: list[str] = []
    clearance_checked = 0
    if clearance_section:
        for key in sorted({item.upper() for item in re.findall(r"(?<![A-Za-z0-9])C\d\d(?![A-Za-z0-9])", clearance_section, flags=re.IGNORECASE)}):
            for block in clearance_blocks(clearance_section, key):
                clearance_checked += 1
                if claims_defect(block) or re.search(r"\bmust be (?:replaced|changed|corrected)\b", block, flags=re.IGNORECASE):
                    clearance_conflicts.append(key)
                break
    clearance_rate = 1.0 - len(clearance_conflicts) / clearance_checked if clearance_checked else 1.0

    _, verdict = readiness_direction(text)
    open_holds = sum(1 for value in states.values() if value == "hold")
    open_holds += sum(1 for key, block in blocks.items() if _classify_finding(block) == "hold")
    decision_conflict = verdict == "release_asserted" and open_holds > 0
    decision_rate = 0.0 if decision_conflict else 1.0

    form_rate, form_conflicts = finding_form_direction(text, patch_section)

    factor = 1.0
    for rate in (finding_rate, clearance_rate, decision_rate, direction_rate, form_rate):
        factor *= 0.35 + 0.65 * rate
    return {
        "finding_rate": round(finding_rate, 4),
        "finding_conflicts": conflicts,
        "clearance_rate": round(clearance_rate, 4),
        "clearance_conflicts": clearance_conflicts,
        "decision_rate": decision_rate,
        "open_holds": open_holds,
        "patch_direction_rate": round(direction_rate, 4),
        "finding_form_rate": round(form_rate, 4),
        "finding_form_conflicts": form_conflicts,
        "factor": round(factor, 6),
    }


def windows(text: str, first_group: tuple[str, ...]) -> list[str]:
    candidates: list[str] = []
    heading_starts = [
        match.start()
        for match in re.finditer(r"^#{1,6}\s+", text, flags=re.MULTILINE)
    ]
    for pattern in first_group:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            previous = [position for position in heading_starts if position <= match.start()]
            following = [position for position in heading_starts if position > match.start()]
            start = previous[-1] if previous else max(0, match.start() - 350)
            end = following[0] if following else min(len(text), match.end() + 1600)
            candidates.append(text[start:end])
    for block in re.split(r"(?=^#{1,6}\s)", text, flags=re.MULTILINE):
        if block.strip() and matches_group(block, first_group):
            candidates.append(block[:1800])
    return candidates or [""]


# Sections that are scored by their own dimension. A finding's diagnosis,
# disposition and location must be read from the finding's own write-up: a
# register row lists the same authors and years, so letting a ledger section
# serve as the window for a finding hands out identity/disposition/evidence
# credit for text that was never a finding at all -- and leaves the finding
# narrative free to say the opposite without cost.
NON_FINDING_SECTIONS = (
    r"collision and inheritance register",
    r"action-ownership matrix",
    r"(?:body-citation )?occurrence ledger",
    r"end-reference ledger",
    r"bidirectional mapping control",
    r"control totals",
    r"non-citation date exclusion register",
    r"confirmed repair patch register",
    r"cleared near matches",
)
NON_FINDING_HEADING = re.compile(
    r"^##\s+(?:" + "|".join(NON_FINDING_SECTIONS) + r")",
    flags=re.IGNORECASE | re.MULTILINE,
)


_REGISTER_ROW = re.compile(r"^\s*(?:[-*+]\s*)?\|?\s*(?:\*\*)?(?:O|R|E|K|P|A)\d+\b", flags=re.IGNORECASE | re.MULTILINE)


def _is_register_block(candidate: str) -> bool:
    """A register is recognised by its rows, not by the heading above them.

    `NON_FINDING_SECTIONS` lists the headings the reference solution happens to
    use. A report that calls the same table something else would otherwise have
    its ledger rows serve as the window for a finding, handing out identity and
    evidence credit for text that was never a finding.
    """
    return len(_REGISTER_ROW.findall(candidate)) >= 5


def best_window(text: str, spec: IssueSpec) -> tuple[str, float, float, float]:
    best = ("", 0.0, 0.0, 0.0)
    best_total = -1.0
    raw_candidates = windows(text, spec.markers[0])
    candidates = [
        candidate for candidate in raw_candidates
        if not NON_FINDING_HEADING.search(candidate) and not _is_register_block(candidate)
    ]
    for candidate in candidates:
        marker_score = group_fraction(candidate, spec.markers)
        diagnosis_score = group_fraction(candidate, spec.diagnosis)
        action_score = group_fraction(candidate, spec.actions)
        total = 2.0 * marker_score + diagnosis_score + action_score
        if total > best_total:
            best = (candidate, marker_score, diagnosis_score, action_score)
            best_total = total
    return best


def find_material(workspace: Path) -> Path | None:
    candidates = (
        workspace / "materials/hydrology_manuscript.pdf",
        workspace / "environment/workspace/materials/hydrology_manuscript.pdf",
        Path(__file__).resolve().parents[1] / "environment/workspace/materials/hydrology_manuscript.pdf",
    )
    return next((path for path in candidates if path.is_file()), None)


def ledger_control_reconciliation(raw,controls):
    """Recompute the report's own row counts and mappings; printed totals alone are insufficient."""
    specs={
      "occ":("body-citation occurrence ledger","O"),"ref":("end-reference ledger","R"),
      "patch":("confirmed repair patch register","P"),"excl":("non-citation date exclusion register","E"),
      "collision":("collision and inheritance register","K"),"action":("action-ownership matrix","A")}
    tables={}
    for name,(heading,prefix) in specs.items():
        scope=register_scope(raw,heading,prefix);headers=None;rows=[]
        for line in scope.splitlines():
            if "|" not in line:continue
            cells=[c.strip().strip("`*") for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?",c) for c in cells):continue
            if headers is None:headers=[normalize(c) for c in cells];continue
            if len(cells)==len(headers) and any(cells):rows.append(dict(zip(headers,cells)))
        if not rows:
            # A list is an equally valid register. Each addressable item begins
            # with its own identifier and may carry labelled fields in prose.
            starts=list(re.finditer(rf"(?im)^\s*(?:[-*+]\s*)?(?:\*\*)?({prefix}\d+)\b",scope))
            for index,match in enumerate(starts):
                end=starts[index+1].start() if index+1<len(starts) else len(scope)
                raw_item=scope[match.start():end].strip()
                if prefix == "P" and not re.search(r"(?i)(?:current|defective|observed).{0,120}(?:proposed|replacement|corrected)|(?:proposed|replacement|corrected).{0,120}(?:current|defective|observed)",raw_item,re.S):
                    continue
                rows.append({"_id":match.group(1),"_raw":raw_item})
        tables[name]=rows
    def col(row,*names):
        for n in names:
            if n in row:return row[n]
        source=row.get("_raw","")
        for n in names:
            hit=re.search(
                rf"(?is)(?<![A-Za-z]){re.escape(n)}\s*[:=]\s*(.*?)"
                rf"(?=(?:\s*[;|]\s*)?[A-Za-z][A-Za-z /()_-]{{2,32}}\s*[:=]|$)",
                source,
            )
            if hit:return hit.group(1).strip()
        return ""
    components=[];cited_only=0;linked=set();relations={}
    for row in tables["occ"]:
        atoms=[v.strip() for v in col(row,"atomic components","components").split(";") if v.strip()]
        links=[v.strip() for v in re.split(r"[;,]",col(row,"linked/candidate end record(s)","linked end record(s)","mapping","linked/candidate end record", "end-record link(s)")) if v.strip()]
        # Header may vary; identify the mapping column by its role.
        if not links:
            for k,v in row.items():
                if ("record" in k and ("link" in k or "candidate" in k or "mapping" in k)) or k=="counterpart":links=[x.strip() for x in re.split(r"[;,]",v) if x.strip()];break
        for i,atom in enumerate(atoms):
            identity=normalize(atom).strip("`* ");components.append(identity)
            target=links[i] if i<len(links) else ""
            if normalize(target)=="none":cited_only+=1
            elif target:linked.update(re.findall(r"[A-Za-z]{1,4}[-–]?\d{1,3}",target))
        rowid=row.get("_id") or next(iter(row.values()),"");relations[rowid]=links
    refids={r.get("_id") or next(iter(r.values()),"") for r in tables["ref"]}
    actual={
     "body_occurrence_groups":len(tables["occ"]),"atomic_author_year_components":len(components),
     "distinct_source_form_author_year_suffix_identities":len(set(components)),"end_reference_records":len(tables["ref"]),
     "records_with_one_or_more_candidate_links":len(linked & refids),"cited_only_atomic_components":cited_only,
     "listed_only_records":sum("listed-only" in normalize(col(r,"status")) for r in tables["ref"]),
     "confirmed_patch_rows":len(tables["patch"]),"non_citation_date_exclusion_groups":len(tables["excl"]),
     "collision_register_rows":len(tables["collision"]),"action_ownership_rows":len(tables["action"]),
     "confirmed_copyeditor_actions":sum(normalize(col(r,"state","status"))=="confirmed" and "copyeditor" in normalize(col(r,"owner")) for r in tables["action"]),
     "author_editor_hold_actions":sum(normalize(col(r,"state","status"))=="hold" and bool(re.search(r"author|editor",normalize(col(r,"owner")))) for r in tables["action"])}
    return {"actual":actual,"expected":controls,"per_control":{k:actual.get(k)==v for k,v in controls.items()}}


def score(answer: Path, workspace: Path) -> dict[str, object]:
    gates = {"readable_report": False, "source_integrity": False}
    details: dict[str, object] = {"issues": {}, "clearances": {}}
    material = find_material(workspace)
    if material is not None:
        gates["source_integrity"] = hashlib.sha256(material.read_bytes()).hexdigest() == EXPECTED_PDF_SHA256

    try:
        raw = _guard_deliverable_text(answer.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = ""
    except OSError as exc:
        scoring_error(f"cannot read {answer}: {exc}")
    except UnicodeError:
        raw = ""
    text = normalize(raw)
    gates["readable_report"] = len(text) >= 500 and bool(re.search(r"19\d{2}|20\d{2}", text)) and bool(re.search(r"reference|citation|callout", text))

    truth_path = Path(__file__).resolve().parent / "ground_truth.json"
    try:
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        active_issue_keys = {item["key"] for item in truth["findings"]}
        active_clearance_keys = {item["key"] for item in truth["clearances"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        scoring_error(f"cannot read {truth_path}: {exc}")

    expected_occurrences = truth.get("occurrences", []) if isinstance(truth, dict) else []
    expected_references = truth.get("references", []) if isinstance(truth, dict) else []
    expected_patches = truth.get("patches", []) if isinstance(truth, dict) else []
    expected_exclusions = truth.get("exclusions", []) if isinstance(truth, dict) else []
    expected_collisions = truth.get("collisions", []) if isinstance(truth, dict) else []
    expected_actions = truth.get("actions", []) if isinstance(truth, dict) else []
    expected_controls = truth.get("controls", {}) if isinstance(truth, dict) else {}

    identity_values: list[float] = []
    action_values: list[float] = []
    evidence_values: list[float] = []
    scope_values: list[float] = []
    for spec in ISSUES:
        if spec.key not in active_issue_keys:
            continue
        candidate, marker_fraction, diagnosis_fraction, action_fraction = best_window(text, spec)
        identity = marker_fraction * (0.15 + 0.85 * diagnosis_fraction)
        has_disposition = matches_group(candidate, spec.actions[0])
        action = action_fraction * marker_fraction if has_disposition else 0.0
        location = group_fraction(candidate, spec.locations)
        evidence_language = 1.0 if re.search(r"evidence|reference|entry|record|list|credits?|contains?|context", candidate) else 0.0
        evidence = diagnosis_fraction * location * (0.7 + 0.3 * evidence_language)
        identity_values.append(identity)
        action_values.append(action)
        evidence_values.append(evidence)
        if spec.scope_item:
            scope_values.append(marker_fraction if diagnosis_fraction == 1.0 else 0.0)
        details["issues"][spec.key] = {
            "identity": round(identity, 4),
            "disposition": round(action, 4),
            "evidence": round(evidence, 4),
        }

    clearance_values: list[float] = []
    false_positive_count = 0
    false_positive_keys: list[str] = []
    clearance_anchors = [
        _anchor_of(item.get("compared_forms", ""))
        for item in (truth.get("clearances", []) if isinstance(truth, dict) else [])
        if item.get("key") in active_clearance_keys
    ]
    clearance_scope = register_scope(text, "cleared near matches", "C",
                                     anchors=clearance_anchors,
                                     kind=r"clear|near.?match|no.?change") or text
    for key, marker_groups in CLEARANCES.items():
        if key not in active_clearance_keys:
            continue
        best_clear = 0.0
        best_context = ""
        best_rank = -1.0
        # Score each clearance on its own record block. A window that reaches the
        # "Cleared near matches" heading would satisfy the clearance vocabulary
        # from the heading alone, whatever the record underneath actually says.
        # A false-positive deduction may only be raised against a clearance the
        # report actually filed. `clearance_blocks` returns the record the report
        # wrote for this key (its own heading block, or the lines around the
        # key). When it returns nothing the report never made a claim about this
        # record at all, and the `windows` fallback below is only a best-effort
        # search for partial coverage credit -- those windows are arbitrary
        # passages of a discrepancy report, so reading a defect claim out of one
        # of them is not evidence of a false repair.
        filed_blocks = clearance_blocks(clearance_scope, key)
        candidates = list(filed_blocks) or windows(clearance_scope, marker_groups[0])
        for candidate in candidates:
            marker_fraction = group_fraction(candidate, marker_groups)
            defect = claims_defect(candidate)
            clear = 1.0 if (matches_group(candidate, CLEAR_SEMANTICS) and not defect) else 0.0
            value = marker_fraction * clear
            rank = marker_fraction + clear
            if rank > best_rank:
                best_context, best_rank = candidate, rank
            best_clear = max(best_clear, value)
        clearance_values.append(best_clear)
        # "missing", "uncited" or "unused" alone is a defect claim only when the
        # record's own block does not also state a no-change outcome for it
        # ("missing companion is possible but not proven ... do not strip").
        strong_claim = claims_defect(best_context) or bool(
            re.search(r"(?:incorrect|mismatch|must change|must replace)", best_context)
        )
        weak_claim = bool(re.search(r"(?:missing|uncited|unused)", best_context)) and not CLEARED_OUTCOME.search(
            rebuilt_normalize(best_context).replace("*", "").replace("`", "")
        )
        bad_claim = strong_claim or weak_claim
        # The charge needs the block to be about this record: its identifying
        # markers (surname and year), not only a row id such as "C02" that a
        # report may also use for its own occurrence rows.
        about_record = group_fraction(best_context, marker_groups[:2]) == 1.0
        if bad_claim and best_clear == 0.0 and filed_blocks and about_record:
            false_positive_count += 1
            false_positive_keys.append(key)
        details["clearances"][key] = round(best_clear, 4)

    readiness, readiness_verdict = readiness_direction(text)
    clearance_score = sum(clearance_values) / len(clearance_values) if clearance_values else 0.0
    occurrence_aliases: dict[str, str] = {}
    occurrence_score, occurrence_details = score_occurrence_ledger(text, expected_occurrences, occurrence_aliases)
    reference_score, reference_details = score_reference_ledger(text, expected_references)
    ledger_score = 0.55 * occurrence_score + 0.45 * reference_score
    mapping_score, mapping_details = score_mapping_control(text, expected_references, expected_occurrences, occurrence_aliases)
    control_score, control_details = score_control_totals(text, expected_controls)
    reconciliation=ledger_control_reconciliation(raw,expected_controls)
    control_details={k:min(v,float(reconciliation["per_control"].get(k,False))) for k,v in control_details.items()}
    control_score=sum(control_details.values())/len(control_details) if control_details else 0.
    semantic=None
    if raw:
        from semantic_judge import adjudicate
        semantic=adjudicate(raw,(Path(__file__).parent/"semantic_source.json").read_text())
    patch_score, patch_details = score_patches(text, expected_patches)
    exclusion_score, exclusion_details = score_exclusions(text, expected_exclusions)
    collision_score, collision_details = score_collision_register(text, expected_collisions)
    ownership_score, ownership_details = score_action_ownership(text, expected_actions, truth.get("findings", []) if isinstance(truth, dict) else [])
    if semantic:
        ownership_score=min(ownership_score,float(semantic["items"]["L07"]["fraction"]))
        exclusion_score=min(exclusion_score,float(semantic["items"]["L09"]["fraction"]))
        occurrence_score=min(occurrence_score,float(semantic["items"]["L11"]["fraction"]))
    split_exclusion_weights(expected_exclusions)
    exclusion_groups: dict[str, list[float]] = {
        "exclusion_period_range": [], "exclusion_caption_table": [], "exclusion_metadata": []}
    for row in expected_exclusions:
        exclusion_groups[exclusion_class(row)].append(float(exclusion_details.get(row["key"], 0.0)))
    dimensions = {
        "scope_reconciliation": sum(scope_values) / len(scope_values) if scope_values else 0.0,
        "identity_resolution": sum(identity_values) / len(identity_values) if identity_values else 0.0,
        "disposition_quality": sum(action_values) / len(action_values) if action_values else 0.0,
        "evidence_traceability": sum(evidence_values) / len(evidence_values) if evidence_values else 0.0,
        "readiness_decision": readiness,
        "cleared_near_matches": clearance_score,
        "occurrence_ledger": occurrence_score,
        "reference_ledger": reference_score,
        "reverse_mapping": mapping_score,
        "control_totals": control_score,
        "patch_register": patch_score,
        "exclusion_period_range": sum(exclusion_groups["exclusion_period_range"]) / len(exclusion_groups["exclusion_period_range"]) if exclusion_groups["exclusion_period_range"] else 0.0,
        "exclusion_caption_table": sum(exclusion_groups["exclusion_caption_table"]) / len(exclusion_groups["exclusion_caption_table"]) if exclusion_groups["exclusion_caption_table"] else 0.0,
        "exclusion_metadata": sum(exclusion_groups["exclusion_metadata"]) / len(exclusion_groups["exclusion_metadata"]) if exclusion_groups["exclusion_metadata"] else 0.0,
        "collision_control": collision_score,
        "action_ownership": ownership_score,
        # reported beside the weighted set: the scope-item coverage and the
        # composites whose parts carry the weight individually
        "closure_precision": 0.35 * readiness + 0.65 * clearance_score,
        "ledger_completeness": ledger_score,
        "mapping_control": 0.65 * mapping_score + 0.35 * control_score,
        "exclusion_audit": exclusion_score,
    }
    # The printed page numbers and the control totals are the report's own
    # arithmetic against the manuscript. A handoff whose locations point at pages
    # the manuscript does not have, or whose totals do not reconcile to the
    # ledgers the brief requires them to reconcile to, is not usable as a
    # handoff however complete its prose is.
    expected_pages = sorted({
        page
        for item in (list(truth.get("findings", [])) + list(truth.get("patches", [])) + list(truth.get("exclusions", [])))
        if isinstance(item, dict)
        for page in re.findall(r"\b4[56]\d\d\b", " ".join(str(value) for value in item.values()))
    })
    pages_present = [page for page in expected_pages if re.search(rf"(?<!\d){page}(?!\d)", text)]
    page_fidelity = len(pages_present) / len(expected_pages) if expected_pages else 1.0
    arithmetic_factor = (0.4 + 0.6 * page_fidelity) * (0.4 + 0.6 * control_score)
    coherence = report_coherence(text, float(patch_details.get("_direction_rate", 1.0)))

    weighted_dimensions = sum(weight * dimensions[name] for name, weight in WEIGHTS.items())

    decision_rate = float(coherence["decision_rate"])
    damage: list[tuple[str, list[str]]] = []
    if not gates["readable_report"]:
        damage.append(("gate: report unreadable or not a citation report", ["D01"]))
    if not gates["source_integrity"]:
        damage.append(("gate: manuscript PDF missing or hash differs", ["D02"]))
    # The manuscript carries confirmed discrepancies and open author queries, so
    # the report's overall decision is a hold. Declaring the reference list ready
    # is the opposite conclusion, and it is the one line of the handoff an editor
    # acts on first; it therefore scales the whole report rather than costing one
    # component.
    if readiness_verdict == "release_asserted":
        damage.append(("decision: reference list declared ready for release", ["D03"]))
    elif readiness_verdict == "no_decision":
        damage.append(("decision: no release/hold decision stated", ["D04"]))
    if decision_rate == 0.0:
        damage.append(("coherence: release asserted while holds remain open", ["D05"]))
    for fp_key in false_positive_keys:
        damage.append((f"false repair claimed on cleared record {fp_key}", ["D06"]))
    patch_section = register_scope(
        text, "confirmed repair patch register", "P",
        anchors=[sorted(set(_anchor_of(row["current"])) | set(_anchor_of(row["proposed"]))) for row in expected_patches],
        kind=r"patch|repair",
    )
    exclusion_section = register_scope(
        text, "non-citation date exclusion register", "E",
        anchors=[sorted({normalize(row["token"]).casefold(), row["printed_page"]} - {""}) for row in expected_exclusions],
        kind=r"exclusion|date|non.?citation|screen",
    )
    findings_section = next(
        (block for block in _top_sections(text)
         if re.search(r"^#{2,3}.*(?:finding|discrepanc)", block.splitlines()[0], re.IGNORECASE)),
        "",
    )
    unresolved_anchors = [
        _anchor_of(item.get("observed_item", ""))
        for item in (truth.get("findings", []) if isinstance(truth, dict) else [])
        if item.get("category") == "Cited-only work"
    ]
    damage.extend(contract_violations(
        text,
        {"findings": findings_section, "patches": patch_section, "exclusions": exclusion_section},
        unresolved_anchors,
    ))
    # D11 - the brief: "For every end-reference record, record the
    # credited-author cardinality". A stated cardinality that contradicts the
    # supplied record (a two-author record filed as single or multiple) is one
    # instance, however many records carry it.
    wrong_cardinality = sorted(key for key, (got, want) in stated_cardinalities(raw, expected_references).items()
                               if got != want)
    if wrong_cardinality:
        damage.append((f"credited-author cardinality contradicts the supplied record(s) {wrong_cardinality}", ["D11"]))
    # D12 - give-away units of the brief every complete handoff carries; each
    # one missing is its own instance. An unreadable report is already charged
    # by D01 and is not charged again unit by unit.
    if gates["readable_report"]:
        for unit in missing_giveaway_units(raw):
            damage.append((f"gate: required unit missing - {unit}", ["D12"]))
    # D13 - the named deliverable path is part of the runtime contract.
    if answer.name != DELIVERABLE_NAME:
        damage.append((f"gate: deliverable scored from {answer.name}, not {DELIVERABLE_NAME}", ["D13"]))
    # The brief names the report path but does not prohibit notes or other
    # files beside it.  Keep the inventory diagnostic; do not penalize an
    # otherwise identical report for workspace hygiene.
    extras = extra_files(answer)
    completion=score_rebuilt(raw,rebuilt_items(),expected_references) if raw else {}
    if semantic:
        semantic_findings=("L01","L02","L03","L04","L05","L06","L10")
        completion["Q14"]=sum(semantic["items"][key]["fraction"] for key in semantic_findings)/len(semantic_findings)
    # Apply the already computed record-level checks to the related weighted items.
    for key,coverage in {"Q05":occurrence_score,"Q06":occurrence_score,"Q07":occurrence_score,
                         "Q08":mapping_score,"Q10":control_score,"Q15":exclusion_score,
                         "Q16":ownership_score}.items():
        completion[key]=coverage
    handoff_complete=all(v>=1-1e-8 for v in (occurrence_score,reference_score,mapping_score,control_score,ownership_score))
    parts = {
        "completion": {**completion,
                       "Q17": score_patch_forms(text, expected_patches) if raw else 0.0,
                       "Q18": (min(score_cleared(raw, active_clearance_keys),
                                   float(semantic["items"]["L08"]["fraction"]))
                               if raw and semantic else 0.0)},
        "damage": damage,
    }

    return {
        "_parts": parts,
        "handoff_complete":handoff_complete,
        "ledger_reconciliation":reconciliation,
        "semantic_judge":semantic,
        "dimensions": {name: round(value, 6) for name, value in dimensions.items()},
        "weighted_dimensions": round(weighted_dimensions, 6),
        "gates": gates,
        "arithmetic_factor": {
            "page_fidelity": round(page_fidelity, 6),
            "control_totals": round(control_score, 6),
            "factor": round(arithmetic_factor, 6),
            "expected_pages": expected_pages,
            "missing_pages": [page for page in expected_pages if page not in pages_present],
        },
        "decision_direction": {"verdict": readiness_verdict},
        "coherence": coherence,
        "false_positive_count": false_positive_count,
        "details": {
            **details,
            "ledger": {
                "occurrence": {key: round(value, 4) for key, value in occurrence_details.items()},
                "reference": {key: round(value, 4) for key, value in reference_details.items()},
            },
            "mapping": {key: round(value, 4) for key, value in mapping_details.items()},
            "controls": {key: round(value, 4) for key, value in control_details.items()},
            "patches": {key: round(value, 4) for key, value in patch_details.items()},
            "exclusions": {key: round(value, 4) for key, value in exclusion_details.items()},
            "collisions": {key: round(value, 4) for key, value in collision_details.items()},
            "actions": {key: round(value, 4) for key, value in ownership_details.items()},
        },
    }


# ---------------------------------------------------------------------------
# Positive item set, read off Golden's own deliverable.
#
# A leaf is one substantive value of the reference: a table cell with its row
# identity and column header, or a prose field with the sentence carrying it.
# Leaves are grouped into the scored items, and a leaf is met only where
# its value appears on a line that also carries the row's identity, so a value
# quoted away from the record it belongs to earns nothing.
# tests/rebuilt_units.json carries the frozen set.
REBUILT = Path(__file__).resolve().parent / "rebuilt_units.json"


def rebuilt_normalize(value: str) -> str:
    """Golden and the report are parsed through the same normalisation.

    Unicode minus signs, en and em dashes, curly quotes and accounting
    parentheses are folded on BOTH sides before anything is compared: a value
    written with U+2212 otherwise silently misses the same value written with
    a hyphen.
    """
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("\u00ad", "")
    for source, target in (("\u2013", "-"), ("\u2014", "-"), ("\u2212", "-"),
                           ("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"')):
        value = value.replace(source, target)
    value = re.sub(r"\((\d[\d.,]*)\)", r"-\1", value)
    return re.sub(r"[^\S\n]+", " ", value).strip()


def rebuilt_items() -> list[dict]:
    try:
        return json.loads(REBUILT.read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        scoring_error(f"cannot read {REBUILT}: {exc}")


# Equivalent forms of a value. A mapping status is also stated by the link
# itself ("B004.a -> R022"): an occurrence that points at a record is a linked
# occurrence. A one-word value (explicit, narrative, parenthetical, ...) may be
# written as the code the report defines in its own legend ("`E` = author and
# year explicit", "`E/E` = explicit author / explicit year", "`NAR` =
# narrative"); a code is read as that value only when the report declares it.
LINKED_FORMS = re.compile(r"\b(?:linked|matched|mapped|resolved)\b|(?:\u2192|->|=>)\s*r-?0*\d{1,3}\b")
LEGEND_PAIR = re.compile(r"`([a-z][a-z/:]{0,5})`\s*(?:=|:|means?|denotes|stands for)?\s*([a-z][^`\n\u00b7;|]{1,79})")


def legend_codes(text: str) -> dict[str, set[str]]:
    """{word: codes the report's legend defines with that word (or a longer form of it, "explicitly") in its first five words}."""
    codes: dict[str, set[str]] = {}
    for code, phrase in LEGEND_PAIR.findall(rebuilt_normalize(text)):
        for word in re.findall(r"[a-z]+", phrase)[:5]:
            codes.setdefault(word, set()).add(code)
    return codes


def _alternate_value(value: str, line: str, codes: dict[str, set[str]], anchor: list[str] = ()) -> bool:
    if value == "linked" and LINKED_FORMS.search(line):
        return True
    if not re.fullmatch(r"[a-z]+", value):
        return False
    # A code that is itself a name of the record (an institutional author such
    # as IPCC) identifies the row, not its value.
    declared = {code for word, found in codes.items() if word.startswith(value) for code in found
                if code not in anchor}
    for code in declared:
        cell = re.escape(code)
        if re.search(rf"(?:^|[\s|;(\[*`])(?:a:|y:)?{cell}(?=$|[\s|;)\],*`/])", line):
            return True
    return False


# ---------------------------------------------------------------------------
# Credited-author cardinality (Q11, D11), read record by record from the
# report's end-reference table. The cardinality column is found by its header
# ("Cardinality", "Card.", "Credited authors", "Author count"); a value may be a
# category (single / two / multiple, one / two / three or more), a number
# ("4", "3+", "four"), a count inside the cell ("3 credited authors",
# "(4 people)"), or a corporate marker for an institution-authored record.
NUMBER_WORDS = "three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen"
CORPORATE_VALUE = re.compile(r"\bcorp|institution|organi[sz]ation|\borg\b|entit")
CARD_LEAD = re.compile(
    rf"^(multiple|multi|many|three or more|several|single|one|sole|two|{NUMBER_WORDS}"
    r"|3\s*\+|>=\s*3|≥\s*3|\d{1,2})(?![\d.])")
CARD_COUNT = re.compile(r"\b(\d{1,2})\s+(?:credited\s+)?(?:authors?|people|persons?|names?)\b")
CARD_WORD = re.compile(r"\b(single|one|two|multi(?:ple)?)[- ]authors?\b")
CARD_HEADER = re.compile(r"\bcard|^credited authors|credited authors$|author count|no\.? of authors|number of (?:credited )?authors")


def _clean_cell(value: str) -> str:
    return rebuilt_normalize(value).replace("*", "").replace("`", "").strip()


def _cardinality_class(word: str) -> str | None:
    word = word.replace(" ", "")
    if word.isdigit():
        number = int(word)
        if not 1 <= number <= 30:
            return None
        return "1" if number == 1 else "2" if number == 2 else "multiple"
    if word in ("single", "one", "sole"):
        return "1"
    if word == "two":
        return "2"
    return "multiple"


def _cardinality_of(cell: str, header_is_cardinality: bool) -> str | None:
    if header_is_cardinality and CORPORATE_VALUE.search(cell):
        return "1"
    match = CARD_LEAD.match(cell) if header_is_cardinality else None
    if match:
        return _cardinality_class(match.group(1))
    match = CARD_COUNT.search(cell) or CARD_WORD.search(cell)
    return _cardinality_class(match.group(1)) if match else None


def _record_keys(references: list[dict]) -> list[tuple[str, str, str, str]]:
    keys = []
    for row in references:
        before_comma = _clean_cell(row.get("head", "")).split(",")[0]
        words = re.findall(r"[a-z]+", before_comma)
        if not words:
            continue
        keys.append((row["key"], max(words, key=len), _clean_cell(row.get("year", "")), row.get("cardinality", "")))
    return keys


def _record_of_row(line: str, keys: list[tuple[str, str, str, str]]) -> tuple[str, str] | None:
    """The end record a table row describes: its head word and year, the head word earliest in the row."""
    cleaned = _clean_cell(line)
    hits = []
    for key, word, year, cardinality in keys:
        name = re.search(rf"\b{re.escape(word)}\b", cleaned)
        if name and re.search(rf"(?<!\d){re.escape(year)}(?![\da-z])", cleaned):
            hits.append((name.start(), key, cardinality))
    hits.sort()
    if not hits or (len(hits) > 1 and hits[0][0] == hits[1][0]):
        return None
    return hits[0][1], hits[0][2]


def stated_cardinalities(text: str, references: list[dict]) -> dict[str, tuple[str, str]]:
    """{record key: (stated class, supplied class)} for every table row or list item that states one."""
    keys = _record_keys(references)
    stated: dict[str, tuple[str, str]] = {}
    lines = text.splitlines()
    header: list[str] | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        if re.match(r"^\|?\s*:?-{2,}", stripped):
            continue
        cells = [_clean_cell(cell) for cell in stripped.strip("|").split("|")]
        if index + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[index + 1].strip()):
            header = cells
            continue
        if header is None:
            continue
        record = _record_of_row(line, keys)
        if record is None or record[0] in stated:
            continue
        order = ([j for j, name in enumerate(header) if re.search(r"\bcard", name)]
                 + [j for j, name in enumerate(header) if "author" in name and not re.search(r"\bcard", name)])
        for column in order:
            if column >= len(cells):
                continue
            found = _cardinality_of(cells[column], bool(CARD_HEADER.search(header[column])))
            if found:
                stated[record[0]] = (found, record[1])
                break
    section=register_scope(
        text,"end-reference ledger","R",require=r"(?:19|20)\d{2}",
        avoid=r"(?<![A-Za-z0-9])O\d+",kind=r"reference|end.?list|bibliograph",
    )
    for key,word,year,want in keys:
        if key in stated:continue
        anchor=[word,year]
        span=anchored_span(section,key,anchor)
        if not span:continue
        match=re.search(r"(?i)(?:credited[- ]author cardinality|cardinality|author count|number of (?:credited )?authors)\s*[:=]\s*([^;|\n]+)",span)
        if match and (found:=_cardinality_of(_clean_cell(match.group(1)),True)):
            stated[key]=(found,want)
    return stated


# ---------------------------------------------------------------------------
# Give-away units (D12). Each is something the brief requires that every
# readable candidate report carries, written with its key value on one line:
#   - each personally authored end-reference record: its inverted head
#     ("Surname, X.") with its year and suffix;
#   - each cited-only work (Bergstrom/Forsman 1973, Leander 2005, Van den Hurk
#     2005, Jacob 2007) with its missing-record disposition;
#   - the action owner (author or editor) assigned to the Forsman 1973, Jacob
#     2007 and Leander 2005 holds;
#   - the reverse mapping of the listed-only SMHI 2007 record, and the control
#     total of 28 end-reference records.
# A missing unit multiplies the score by the D12 coefficient, compounding.
MISSING_RECORD = (r"(?:missing|absent|no\b[^|]{0,60}(?:entry|record|reference)|not (?:found|listed|in)"
                  r"|cited.only|dangling|unmatched|orphan|without (?:a |an )?(?:entry|record|reference))")
OWNER_CELL = r"(?:\|\s*|owner\s*[:=]\s*)(?:author|editor|editorial office)\b"
GIVEAWAY_UNITS: dict[str, list[str]] = {
    **{f"record {name} {year}": [rf"\b{name}(?: van den| de)?,\s*[a-z]\.", rf"(?<!\d){year}(?![\da-z])"]
       for name, year in (
           ("aalders", "2004"), ("ashagrie", "2006"), ("bakker", "2008"), ("bergstrom", "2001"),
           ("bergstrom", "1995"), ("bergstrom", "1994"), ("booij", "2002b"), ("booij", "2005"),
           ("hurk", "2006"), ("leander", "2007"), ("leander", "2008"), ("lenderink", "2003"),
           ("lorenz", "2008"), ("pfister", "2004"), ("roeckner", "2003"), ("smits", "2004"),
           ("tu", "2005a"), ("tu", "2005b"), ("uijlenhoet", "2001"), ("schrojenstein lantman", "2004"),
           ("warmerdam", "2001"), ("wit", "2001a"), ("wit", "2007b"), ("wit", "2001b"), ("wit", "2007a"))},
    "cited-only forsman 1973": [r"forsman", r"1973", MISSING_RECORD],
    "cited-only leander 2005": [r"leander", r"2005", MISSING_RECORD],
    "cited-only hurk 2005": [r"hurk", r"2005", MISSING_RECORD],
    "cited-only jacob 2007": [r"jacob", r"2007", MISSING_RECORD],
    "owner of forsman 1973": [OWNER_CELL, r"forsman|1973"],
    "owner of jacob 2007": [OWNER_CELL, r"jacob", r"2007"],
    "owner of leander 2005": [OWNER_CELL, r"leander", r"2005"],
    "reverse mapping of smhi 2007": [r"smhi|swedish meteorological", r"2007",
                                     r"listed.only|uncited|not cited|no (?:formal |body )?(?:callout|citation)|unused|unmatched|orphan|zero"],
    "control total of 28 end records": [r"(?<!\d)28(?!\d)", r"record|entr|reference"],
}


def missing_giveaway_units(text: str) -> list[str]:
    lines = [rebuilt_normalize(line).replace("*", "").replace("`", "") for line in text.splitlines()]
    return [name for name, patterns in GIVEAWAY_UNITS.items()
            if not any(all(re.search(pattern, line) for pattern in patterns) for line in lines)]


def score_rebuilt(text: str, items: list[dict], references: list[dict] | None = None) -> dict[str, float]:
    """One item per group of Golden leaves; a leaf scores only bound to its object."""
    lines = [rebuilt_normalize(line) for line in text.splitlines()]
    codes = legend_codes(text)
    values: dict[str, float] = {}
    for item in items:
        if item.get("scored_by") == "cardinality":
            # Q11: the share of the supplied end records whose credited-author
            # cardinality the report states correctly.
            stated = stated_cardinalities(text, references or [])
            total = len(references or []) or 1
            values[item["id"]] = sum(1 for got, want in stated.values() if got == want) / total
            continue
        hits=[]
        for leaf in item["leaves"]:
            anchor,value=leaf["anchor"],leaf["value"]
            carriers=[line for line in lines if all(token in line for token in anchor)]
            hit=any(bool(re.search(r"(?<![a-z0-9])"+re.escape(value)+r"(?![a-z0-9])",line)) or _alternate_value(value,line,codes,anchor) for line in carriers)
            if not hit and leaf.get("long"):
                wanted=set(re.findall(r"[a-z]{4,}",value))
                hit=bool(wanted) and any(len(wanted & set(re.findall(r"[a-z]{4,}",line)))/len(wanted)>=.7 for line in carriers)
            hits.append(float(hit))
        # Every bound reference field contributes, never 'one match completes the group'.
        values[item["id"]]=sum(hits)/len(hits) if hits else 0.
    return values


# ---------------------------------------------------------------------------
# pd-ledger-v1 settlement.
PARAMS = Path(os.environ.get("SCORING_PARAMS", Path(__file__).resolve().parent / "scoring_params.json"))
DEFAULT_ANSWER = "/workspace/output/citation_reconciliation.md"


DELIVERABLE_NAME = "citation_reconciliation.md"
EXTRA_ALLOWED = ("manifest.json",)


def extra_files(answer: Path) -> list[str]:
    """Other regular files in the deliverable's own directory."""
    folder = answer.parent
    if not folder.is_dir():
        return []
    return sorted(entry.name for entry in folder.iterdir()
                  if entry.is_file() and entry.name != answer.name
                  and not entry.name.startswith(".") and entry.name not in EXTRA_ALLOWED)


def deliverable(arg: str) -> Path:
    """The contract may pass a directory holding an artifact; the container normally passes the file."""
    path = Path(arg)
    if not path.is_dir():
        return path
    named = path / "citation_reconciliation.md"
    if named.is_file():
        return named
    found = sorted(path.glob("**/citation_reconciliation.md")) or sorted(path.glob("**/*.md"))
    return found[0] if found else named


def settle(result: dict[str, object]) -> dict[str, object]:
    """Settle the scored parts as pd-ledger-v1."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    parts = result.pop("_parts", {"completion": {}, "damage": []})
    completion = {k: round(min(1.0, max(0.0, float(parts["completion"].get(k, 0.0)))), 10) for k in weights}
    instances = [{"key": key, "item_ids": items} for key, items in parts["damage"]]
    earned = sum(weights[k] * completion[k] for k in weights)
    retention = math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances)
    final = earned * retention
    fired = {item_id for inst in instances for item_id in inst["item_ids"]}
    lenient_items = {}
    for item_id in LENIENT_REQUIRED_ITEMS:
        if item_id in coefficients:            # deduction item: met when it never fired
            lenient_items[item_id] = item_id not in fired
        else:                                  # positive item: met at its own full completion
            lenient_items[item_id] = completion.get(item_id, 0.0) >= 1.0
    lenient_items["complete_handoff"]=bool(result.get("handoff_complete",False))
    lenient = 1.0 if all(lenient_items.values()) else 0.0
    result["rewards"] = {"strict": final, "lenient": lenient}
    result["reward_formulas"] = {
        "strict": "positive_earned * retention (pd-ledger-v1; weights and coefficients from scoring_params.json)",
        "lenient": "1.0 only when every must-have item in LENIENT_REQUIRED_ITEMS is met "
                   "(positive item at completion 1.0; deduction item not fired), else 0.0",
    }
    result["lenient_detail"] = {
        "required_items": list(LENIENT_REQUIRED_ITEMS),
        "per_item": {key: bool(value) for key, value in lenient_items.items()},
        "failed_items": [key for key, value in lenient_items.items() if not value],
        "lenient": lenient,
    }
    result["scoring_ledger"] = {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                                "damage_instances": instances, "positive_earned": earned,
                                "retention": retention, "final_score": final}
    return result


def main() -> int:
    answer = deliverable(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ANSWER)
    workspace = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/workspace")
    print(json.dumps(settle(score(answer, workspace)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

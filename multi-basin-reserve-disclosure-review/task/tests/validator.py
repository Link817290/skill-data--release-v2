#!/usr/bin/env python3
"""Condition-blind scorer for the reserve disclosure review deliverables (pd-ledger-v1).

Usage: validator.py <target>
  <target> is the memo path the container passes (/workspace/output/reserve_disclosure_review.md), the register
  CSV, an output directory, a rollout ``artifacts/`` directory or the task ``golden/`` directory. Prints one JSON
  object on stdout.

The strict score is settled in the standard form:

  final = max(0, positive_earned - deduction_total)
  positive_earned = sum(weight[P] * completion[P])          (weights from scoring_params.json, sum 1)
  deduction_total = sum(root-deduplicated damage amounts)

Positive items use the best supported row per matter; complete related matters may share a row.
D04 is source-aware semantic language review; names and citations are exempt.
D05 is retired: omissions lose positive shares. D01-D03/D06-D08 retain their specified checks.
Lenient is the binary usability conjunction documented in RUBRIC.md.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Callable

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
_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)[^\n]*\n.*?^[ \t]*(?:```|~~~)[ \t]*$", re.S | re.M)


def _guard_deliverable_text(raw: str) -> str:
    """Drop fenced blocks and every line (paragraph line or table row) the text disowns."""
    raw = _FENCE_RE.sub("", raw)
    return "\n".join(line for line in raw.split("\n") if not _DISOWN_RE.search(line))



# --------------------------------------------------------------------------
# Lenient lens: the matters this review cannot be delivered without.
#
# The brief asks for "a review that separates genuine filing exceptions from apparent
# inconsistencies that can be cleared by the supplied record", and it says the memo
# "must" carry a filing-readiness conclusion whose headline conclusions "must
# cross-reference the corresponding review identifier in the register". So the lenient
# lens asks for one worked example of each side of that separation plus the artifact
# contract, and nothing else:
#
#   P03  the genuine filing exception - the comparative purchase/extension category
#        swap, caught against a zero-purchase product table with the comparative ending
#        quantity preserved. A review that misses the misclassification it exists to
#        find is not usable by the committee.
#   P08  the cross-source clearance - the four engineer totals reconciled to the
#        issuer's 45,018 MBoe ending proved reserves on the disclosed 5.8:1 basis, while
#        stating that ending-balance agreement does not clear the movement labels. This
#        is the brief's "independent engineer materials ... on their stated reporting
#        bases" together with its instruction to keep facts distinct from conclusions.
#   P09  the apparent high-risk inconsistency that is cleared - the $70.81 versus
#        $69.12 oil price difference explained by the stated quality, transportation and
#        market differentials rather than forced to match. The brief names identifying
#        "apparent high-risk inconsistencies that were cleared" as a requirement.
#   P11  the artifact contract - substantive, source-located register rows, memo
#        conclusions cross-referencing register identifiers, and a readiness conclusion
#        that names corrections, clearances and open evidence needs. These are the
#        brief's explicit "must" clauses about the two deliverables themselves.
#
# Each item is judged on its own strict dimension result, complete or not, and the
# lenient score is 1.0 only when all four are complete (times the D01 integrity gate).
# P02 and P07 carry the largest weights but are deliberately not here: they are
# graduated matters no submission in the sample completes, so gating on them would make
# the lens constant rather than discriminating.
LENIENT_REQUIRED_ITEMS = ("P03", "P08", "P09", "P11")


EXPECTED_SOURCES = {
    "annual_report.html": "9a198c63754b1cb45b47a4f149843a03a58340e76ed3619acf3e980390239841",
    "earnings_release.html": "19a3c46f7a9f50c95d48ec0325be03c9ce620fb403f766ed3bd8f2e87ed20e54",
    "engineer_egypt.html": "c4e3def6a8f7dc18d02162d8e06b5830da6b27760d5b4acda55311c3db8459cc",
    "engineer_gabon.html": "a68ef35b27f9116355dab0dcb877cb9b569c020c1c5c76e62c8e71ffe063a5c7",
    "engineer_cote_divoire.html": "8d475d39403c122e7ceb285803e8e977ab89d4cb78cdd8cda51cdfdc3bdc1c82",
    "engineer_canada.html": "751ee7e507596f5fc7a82dec5444dbbc0069efceb4720a1987b8d4310c3a2e99",
}

# Where in the document the evidence sits. The brief asks for "the supplied file and a
# useful section, table, or nearby text locator" and the rubric adds that "descriptive
# locators ... may vary", so the generic pointer words belong here alongside the
# reference solution's own headings: a row that cites "annual_report.html - Exhibit 99,
# PUD roll-forward heading" has given the same pointer as one that writes "table". The
# list stays a list of *pointers*; substance is still carried by `sourced()`, which
# requires the row to cite figures or several documents.
LOCATOR_TERMS = re.compile(
    r"\b(section|subsection|table|note|footnote|paragraph|passage|page|line|item|exhibit|"
    r"appendix|schedule|heading|header|caption|figure|chart|column|annotation|"
    r"reserve information|reserve data|year.end|fiscal close|controls|procedures|pricing|"
    r"price basis|proved undeveloped|standardized measure|standardised measure|pv.10|"
    r"pv ten|methods|approach|total proved|aggregate proved)\b"
)
SOURCE_TERM = re.compile(r"\b[\w.-]+\.html?\b")

# Quantities the deliverable itself asserts. Identifiers such as "r-03" or "pv-10"
# are not quantities, so they are stripped before the numeric anchors are checked.
ID_TOKEN = re.compile(r"\b(?:r|pv|ifrs|asc|sec|item)-\d+\b")
NUM_TOKEN = re.compile(r"-?\d+(?:\.\d+)?")
WORD_NUMBER = re.compile(
    r"\b(?:zero|nil|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"twenty|thirty|forty|fifty|hundred|thousand|million|billion)\b"
)


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().replace("&", " and ")
    value = re.sub(r"(?<=\d),(?=\d)", "", value)
    value = re.sub(r"[^a-z0-9._$%/+-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def present(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text, re.I) is not None for pattern in patterns)


def parts(*items: tuple[float, bool]) -> float:
    return round(sum(weight for weight, passed in items if passed), 8)


# --------------------------------------------------------------------------
# Direction analysis
#
# Judgement text is scored by *polarity*, not by phrase lists: the text is cut
# into clauses, each clause is cut again at contrastive markers (the material
# after "rather than" / ", not" is the rejected alternative), and a closed-class
# negation lexicon sets the sign of each segment. A wrong-direction assertion
# ("anti") found in a positive segment means the row asserts the inverse of the
# expert conclusion; the same assertion found inside a negation is the correct
# statement and counts as affirmation.
# --------------------------------------------------------------------------

CLAUSE_SPLIT = re.compile(
    r"(?<!\d)\.(?!\d)|[;:|]"
    r"|\b(?:but|although|though|whereas|however|yet|nevertheless|nonetheless|despite|notwithstanding)\b"
    r"|,\s+(?:and|or|so|then|which|because|since)\s+"
    r"|\s+and\s+(?=the\b|that\b|this\b|it\b|they\b|these\b|those\b|there\b|a\s)"
)

CONTRAST_SPLIT = re.compile(
    r"\b(?:rather than|instead of|as opposed to|in place of|not merely|not simply|not just|other than)\b"
    r"|,\s+not\b"
)

NEGATION = re.compile(
    r"\b(?:not|no|never|neither|nor|none|nothing|cannot|cant|without|absent|lacks?|lacking|"
    r"fails?|failed|failing|unable|avoids?|refutes?|refuted|disproves?|disproved|denies|denied|"
    r"insufficient|inadequate|short of|except|unsupported|doesn|dont|don|didn|isn|arent|aren|"
    r"wasn|weren|couldn|wouldn|shouldn|hasn|haven|won)\b"
)


def segments(text: str) -> list[tuple[str, int]]:
    """Return (segment_text, polarity) pairs; polarity is +1 asserted, -1 denied."""
    out: list[tuple[str, int]] = []
    for clause in CLAUSE_SPLIT.split(text):
        clause = clause.strip()
        if not clause:
            continue
        pieces = CONTRAST_SPLIT.split(clause)
        for index, piece in enumerate(pieces):
            piece = piece.strip()
            if not piece:
                continue
            base = 1 if index == 0 else -1
            if NEGATION.search(piece):
                base = -base
            out.append((piece, base))
    return out


# An anti-assertion has to be matched as a word, not as a substring starting in
# the middle of a longer one. Several of the hand-written anti patterns are the
# affirmative stem of the very word that states the expert conclusion:
# "inconsistent with its own additions narrative" contains "consistent with its
# own additions narrative" (R-01), "invalid negative discovery" contains "valid
# negative discovery" (R-02), "incorrectly report" contains "correctly report"
# (R-03), "inconsistently across the tables" (R-07), "reconciliation is
# impracticable" contains "reconciliation is practicable" (R-10). Without this
# guard each of those correct statements is read as its own reversal and the
# whole dimension is zeroed; rewriting "conflicts with" as "is inconsistent with"
# must not change the reading.
#
# The guard only removes matches that begin inside a longer word; it can never
# create a match that did not exist.
ANTI_WORD_START = r"(?<![A-Za-z])"


def anti_hit(pattern: str, text: str) -> bool:
    return re.search(ANTI_WORD_START + "(?:" + pattern + ")", text, re.I) is not None


def inverted(text: str, anti: tuple[str, ...], anti_literal: tuple[str, ...]) -> bool:
    """True when the row asserts the opposite of the expert conclusion."""
    for pattern in anti_literal:
        if anti_hit(pattern, text):
            return True
    for piece, polarity in segments(text):
        if polarity > 0 and any(anti_hit(pattern, piece) for pattern in anti):
            return True
    return False


def affirmed(text: str, anti: tuple[str, ...], pos: tuple[str, ...]) -> bool:
    """True when the row actually states the expert conclusion in some wording.

    Direction is already enforced by ``inverted``; this test only asks whether the
    substance is present at all, so the positive paraphrases are matched without a
    polarity requirement (an inverted row never reaches this point). A
    wrong-direction assertion that sits inside a negation is the correct statement
    and also counts.
    """
    for piece, polarity in segments(text):
        if polarity > 0 and any(re.search(pattern, piece, re.I) for pattern in pos):
            return True
        if polarity < 0 and any(anti_hit(pattern, piece) for pattern in anti):
            return True
    return False


def quantities(text: str) -> set[str]:
    stripped = ID_TOKEN.sub(" ", text)
    found = {match.lstrip("-") for match in NUM_TOKEN.findall(stripped)}
    found.update(WORD_NUMBER.findall(stripped))
    return found


def resolve_outputs(target: Path) -> tuple[Path, Path]:
    if target.is_dir():
        candidates = [target, target / "output"]
        for base in candidates:
            memo = base / "reserve_disclosure_review.md"
            register = base / "reserve_disclosure_register.csv"
            if memo.is_file() or register.is_file():
                return memo, register
        return candidates[0] / "reserve_disclosure_review.md", candidates[0] / "reserve_disclosure_register.csv"
    if target.suffix.lower() == ".csv":
        return target.with_name("reserve_disclosure_review.md"), target
    return target, target.with_name("reserve_disclosure_register.csv")


def scoring_error(message: str) -> None:
    """The scorer cannot evaluate this submission: exit non-zero without printing a reward."""
    sys.stderr.write(f"SCORING ERROR: {message}\n")
    sys.stderr.flush()
    os._exit(2)


def read_rows(path: Path) -> tuple[list[list[str]], list[str]]:
    if not path.is_file():
        return [], []
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            parsed = list(csv.reader(stream))
    except OSError as exc:
        scoring_error(f"cannot read {path}: {exc}")
    except (UnicodeError, csv.Error):
        return [], []
    if len(parsed) < 2:
        return [], parsed[0] if parsed else []
    width = max(len(row) for row in parsed)
    rows = [row + [""] * (width - len(row)) for row in parsed[1:] if any(cell.strip() for cell in row)]
    return rows, parsed[0]


def source_integrity(target: Path) -> tuple[bool, str]:
    candidates = [
        Path("/workspace/source_documents"),
        target / "source_documents" if target.is_dir() else target.parent / "source_documents",
        Path(__file__).resolve().parent.parent / "environment/workspace/source_documents",
    ]
    source_dir = next((path for path in candidates if path.is_dir()), None)
    if source_dir is None:
        return False, "source materials not found"
    for name, expected in EXPECTED_SOURCES.items():
        path = source_dir / name
        if not path.is_file():
            return False, f"missing source: {name}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            return False, f"source changed: {name}"
    return True, "all supplied source files match"


def has_evidence(row: str, minimum_files: int = 1) -> bool:
    cited = set(SOURCE_TERM.findall(row))
    # A filename-shaped token is not evidence unless it is one of the supplied
    # source documents.  This prevents invented engineer/report files from
    # earning traceability credit.
    return (len(cited) >= minimum_files and cited.issubset(EXPECTED_SOURCES)
            and bool(LOCATOR_TERMS.search(row)))


def sourced(row: str) -> bool:
    """A row carries real support only if it cites figures or several documents."""
    cited = set(SOURCE_TERM.findall(row))
    return (bool(quantities(row)) or
            (len(cited) >= 3 and cited.issubset(EXPECTED_SOURCES)))


# --------------------------------------------------------------------------
# Dimension specifications
#
# anchor      : figures (or, where the matter carries none, the specific method /
#               document facts) the row must reproduce correctly. Judgement and
#               evidence credit is conditional on the anchor, so a row with
#               perturbed figures or with no figures at all cannot buy the
#               judgement points with wording alone.
# anti/anti_lit: wrong-direction assertions; any hit zeroes the dimension.
# pos         : several paraphrases of the right-direction assertion.
# items       : (weight, kind, patterns) with kind in {fact, judge, evidence}.
# --------------------------------------------------------------------------

SPECS: dict[str, dict] = {
    "R-01": {
        "anchor": (r"\b6193\b", r"\b24128\b", r"\b377\b", r"\b15670\b"),
        "anti": (
            r"consistent with (its own |the |their )?(additions?|stated )?\s*(narrative|description|prose|disclosure)",
            r"closure validates",
            r"validates? (the |a |this )?negative",
            r"both represent the movement",
            r"(are|is) already correct",
            r"balance is challenged",
            r"correctly (classified|reported|presented|printed)",
            r"no (category )?(exception|correction|conflict)",
        ),
        "anti_lit": (
            r"\bno correction\b",
            r"no [\w\s-]{0,40}schedule is (needed|required)",
            r"requires no conforming",
            r"not require (any )?correction",
        ),
        "pos": (
            r"conflict|contradict|inconsisten|irreconcil|at odds|cannot both|do(es)? not (validate|support|establish)",
            r"misclassif|reclassif|category (exception|error|issue|problem)",
            r"correct the|category allocation|sign(s)? (reversed|and)|wrong sign",
            r"not (challenge|disput|invalidat)",
        ),
        "items": [
            (0.25, "fact", (r"\bpud|proved undeveloped", r"\b6193\b", r"\b15670\b", r"\b2698\b", r"\b377\b", r"\b24128\b")),
            (0.25, "judge", (r"extension", r"\b0?\.4\b|\b400\b", r"canada",
                             r"conflict|contradict|negative|cannot both|inconsisten|irreconcil|at odds|disagree")),
            (0.20, "judge", (r"clos|arith|adds?|foot|sum|tie|total",
                             r"ending|balance|closing",
                             r"not challenge|unchalleng|remain|stand|24128|not .{0,25}(invalid|disput)")),
            (0.20, "judge", (r"schedule|workpaper|roll.?forward|support",
                             r"correct|reclass|allocation|re-?assign|conform",
                             r"sign|categor|classif")),
            (0.10, "evidence", (1, r"annual_report\.html")),
        ],
    },
    "R-02": {
        "anchor": (r"\b93\b", r"\b234\b", r"\b40\b", r"\b14\b"),
        "anti": (
            r"do(es)? cure|cures its categor",
            r"(shows|is|as|reflects) an? valid negative discovery",
            r"valid negative discovery",
            r"does establish|do establish|establishes the corrected",
            r"split is (established|resolved|known)",
            r"categor\w* meaning is (cured|correct|valid)",
        ),
        "anti_lit": (
            r"no [\w\s-]{0,40}schedule (is )?(required|needed)",
            r"\bno correction\b",
            r"allocation (is )?(established|resolved)",
        ),
        "pos": (
            r"do(es)? not cure|not cure|uncured",
            r"propagat|carr(y|ies) (the |through)|repeat",
            r"not establish|unresolv|cannot determin|not determin|undetermined|open",
            r"require|obtain|request|correct|reclass",
        ),
        "items": [
            (0.35, "fact", (r"canada", r"\b93\b", r"\b234\b", r"\b6\b", r"\b40\b", r"\b14\b", r"oil|mbbl", r"gas|mmcf", r"ngl")),
            (0.25, "judge", (r"match|reproduc|tie|agree|equal|consistent",
                             r"negative|\(14\)|-14",
                             r"categor|discover|classif")),
            (0.20, "judge", (r"unresolv|not establish|cannot determine|not determin|undetermined|open|outstanding",
                             r"split|allocation|apportion|breakdown|correct")),
            (0.10, "judge", (r"schedule|workpaper|roll.?forward|(?:event|movement)[ -]+(?:ledger|register|schedule)",
                             r"product|boe|equivalent",
                             r"correct|reclass|restate|revis")),
            (0.10, "evidence", (1, r"annual_report\.html")),
        ],
    },
    "R-03": {
        "anchor": (r"\b810\b", r"\b3219\b", r"\b505\b", r"\b1945\b|\b1944\.5\b"),
        "anti": (
            r"correctly report|purchases? (is|are) correctly|purchase (classification|presentation) is correct",
            r"do(es)? report a purchase",
            r"chang(e|es|ed) the (comparative[- ]?year )?ending",
            r"keep [\w\s,$.-]{0,50}as purchases",
            r"leave [\w\s,$.-]{0,50}as purchases",
            r"(is|was) an actual purchase",
        ),
        "anti_lit": (
            r"not a (cross.?table )?categor\w* swap",
            r"no (reclassification|correction|reclass)",
            r"needs? no (reclassification|correction)",
        ),
        "pos": (
            r"swap|misclassif|reclassif|move|shift|transfer|mislabel",
            r"no purchase|zero (purchase|extension)|nil purchase",
            r"unchang|does not change|preserv|same ending|identical",
            r"organic|replacement|trend",
        ),
        "items": [
            (0.35, "fact", (r"comparative|2023|prior|earlier", r"\b93\b", r"\b810\b", r"\b3219\b", r"\b505\b", r"\b1944\.5\b|\b1945\b")),
            (0.25, "judge", (r"purchase", r"extension", r"swap|move|reclass|misclass|shift|transfer|mislabel",
                             r"zero|no purchase|nil|none|nothing")),
            (0.15, "judge", (r"ending|closing", r"unchang|not change|preserv|same|intact|identical")),
            (0.15, "judge", (r"correct|move|reclass|restate|shift", r"trend|replacement|organic|history|acquisition")),
            (0.10, "evidence", (1, r"annual_report\.html")),
        ],
    },
    "R-04": {
        "anchor": (r"\b8318\b|8\.318", r"\b144956\b|144\.956"),
        "anti": (
            r"can be derived|is derivable|may be derived",
            r"volume alone can|volumes? can allocate",
            r"prorate (the )?dollars|prorat\w+ (the )?(dollar|value|amount)",
            r"\bare reliable\b|classifications are reliable",
            r"is disproved|are disproved",
            r"follow the volumes proportionally|proportional to the volume",
            r"(is|are) not misstated",
        ),
        "anti_lit": (
            r"need not rerun|no (property.level )?(rerun|bridge)",
            r"not require review|no review (is )?(required|needed)",
            r"dollar split can be derived",
        ),
        "pos": (
            r"cannot (be )?(deriv|allocat)|not .{0,20}deriv|unable to (deriv|allocat)",
            r"unreliab|misstat|suspect|tainted|questionab|affected",
            r"unresolv|undetermin|open|outstanding",
            r"rerun|bridge|reconcil|recomput|recalculat|do not prorate|without prorat",
        ),
        "items": [
            (0.25, "fact", (r"standardized measure", r"\b8318\b|8\.318", r"\b144956\b|144\.956")),
            (0.25, "judge", (r"upstream|quantity|reserve", r"downstream|value|cash flow", r"categor",
                             r"affect|review|unreliable|misstat|suspect|questionab")),
            (0.25, "judge", (r"cannot|not .*deriv|unresolv|undetermin|unable",
                             r"property|timing",
                             r"cost|tax|discount|price")),
            (0.15, "judge", (r"rerun|bridge|reconcil|recomput|recalculat",
                             r"do not|not prorate|not .*volume|without prorat|no prorat")),
            (0.10, "evidence", (1, r"annual_report\.html")),
        ],
    },
    "R-05": {
        "anchor": (r"\b(five|5)[\s-]*year",),
        "anti": (
            r"do(es)? provide (the )?(booking|conversion) dates",
            r"demonstrates? that the (complete|entire|full)",
            r"(is|are) covered by a current adopted development plan",
            r"(specific )?puds? (are|is) invalid",
            r"non.?complian",
            r"violation (is |was )?(concluded|established|found)",
            r"write down the",
            r"support (is|was) (provided|sufficient|adequate) for the entire",
        ),
        "anti_lit": (
            r"no [\w\s-]{0,40}(roll.?forward|aging) (needs|is needed|is required)",
            r"need(s)? not be obtained",
            r"conclude(s|d)? a violation",
        ),
        "pos": (
            r"does not (demonstrate|provide|establish|show)|not demonstrate|fails? to (demonstrate|show)",
            r"evidence (gap|request)|disclosure.evidence|insufficient|missing|silent|absent",
            r"obtain|request|seek|require .{0,20}(from|the)",
            r"no (violation|invalid)|not .{0,60}(violation|invalid|noncomplian)",
        ),
        "items": [
            (0.20, "fact", (r"histor|annual|each year|every year",
                             r"review|reassess|re-?examin|looks at|revisit|evaluat",
                             r"pud|undeveloped", r"\b(five|5)[\s-]*year")),
            (0.25, "judge", (r"entire|complete|full|population|acquired|all of",
                             r"booking|initial|booked",
                             r"plan",
                             r"missing|not demonstrate|does not provide|insufficient|absent|no evidence|silent|lack"
                             r"|nowhere|stops short|falls short|fails? to (show|demonstrate|establish)|gap in")),
            (0.20, "judge", (r"(not|no|rather than|short of|without)[^.;|]{0,90}(violation|invalid|noncomplian|non.complian|breach|deficien)"
                             r"|evidence (gap|request)|disclosure.evidence gap|stops short",)),
            (0.25, "judge", (r"request|obtain|seek|ask for|provide",
                             r"aging|booking date|roll.?forward|vintage",
                             r"adopted plan|approval|approved plan",
                             r"conversion|drill|exception|delay")),
            (0.10, "evidence", (1, r"annual_report\.html")),
        ],
    },
    "R-06": {
        # This matter carries no figures; the anchor is the specific evaluation
        # method set and the documents that supply it.
        "anchor": (r"performance", r"volumetric", r"analog", r"reservoir model|simulation"),
        "anti": (
            r"(contains|includes|provides|supplies|has) an? general discussion",
            r"(are|is) an? general discussion of applied technolog",
            r"fully suppl|completely suppl",
            r"replace(s)? management",
            r"connect(s)? the (methods|technolog)",
            r"(is|are) (already )?(adequate|sufficient|complete)",
        ),
        "anti_lit": (
            r"no (issuer.?level )?(discussion|supplement|addition) (needs|is needed|is required)",
            r"\bno supplement\b",
            r"need(s)? no (discussion|supplement)",
            r"not .{0,30}need(ed|s)? to be (added|supplemented)",
        ),
        "pos": (
            r"lack|absent|missing|omission|does not (contain|include|provide|connect)|not a general discussion|insufficient",
            r"add|supplement|expand|provide an issuer",
            r"mitigat|within (their|its) scope|partial|limited",
            r"not replace|cannot substitute|no substitute|does not replace",
        ),
        "items": [
            (0.25, "judge", (r"definition|input list|control|policy",
                             r"not|lack|insufficient|absent|short of|does not|fail|omission",
                             r"applied|actually used|general discussion|in practice",
                             r"technolog")),
            (0.25, "judge", (r"performance", r"volumetric", r"analog", r"reservoir model|engineer|evaluator|simulation")),
            (0.20, "judge", (r"scope", r"partial|mitigat|within|limited|only",
                             r"issuer|management",
                             r"not replace|does not replace|gap|omission|substitute")),
            (0.20, "judge", (r"add|supplement|expand|provide", r"issuer|management",
                             r"material addition|reserve class|properties")),
            (0.10, "evidence", (2, r"annual_report\.html")),
        ],
    },
    "R-07": {
        "anchor": (r"\b16465\b", r"\b18496\b"),
        "anti": (
            r"described consistently|consistent(ly)? (across|between|with) the (reserve.?change )?(narrative|tables)",
            r"\bboth\b[^.;|]{0,120}(directly )?connected",
            r"same matter as|same (issue|exception) as",
            r"(is|are) fully (described|explained|disclosed)",
        ),
        "anti_lit": (
            r"\bno qualification\b",
            r"no (added|additional|further) (explanation|cross.?reference|disclosure)",
            r"need(s)? no (explanation|cross.?reference)",
        ),
        "pos": (
            r"not .{0,40}(described|explained) consistent|inconsisten|incomplete|narrative.completeness",
            r"assemble|elsewhere|broader|piece together|reader must|requires the reader",
            r"add|cross.?reference|expand|explain",
            r"separate|distinct|apart from",
        ),
        "items": [
            (0.30, "fact", (r"\b16465\b", r"\b18496\b", r"sven", r"transglobe", r"purchase|acquisition")),
            (0.25, "judge", (r"current|2024|this year", r"direct|tie|connect|link",
                             r"comparative|earlier|2022|prior",
                             r"elsewhere|broader|assemble|cross|piece together|reader")),
            (0.20, "judge", (r"separate|after|distinct|apart from", r"swap|classif|r-03|category")),
            (0.15, "judge", (r"add|cross.reference|include|expand", r"period", r"geograph|transaction|deal")),
            (0.10, "evidence", (1, r"annual_report\.html")),
        ],
    },
    "R-08": {
        "anchor": (r"9448\.1", r"11063\.1", r"15251\.6", r"6551\.3", r"\b45018\b"),
        "anti": (
            r"clear(s)? the movement (classification|label|categor)",
            r"(is|are) an audit",
            r"do validate|does validate|validate(s)? .{0,40}movement (label|classif|categor)",
            r"discard the",
            r"(is|are) an audit of issuer controls",
        ),
        "anti_lit": (
            r"(do|does) not reconcile|fails? to reconcile|did not reconcile",
            r"(do|does) not support the rounded",
            r"do(es)? not tie",
        ),
        "pos": (
            r"reconcil|tie|agree|within rounding|foot",
            r"not an? audit|not .{0,30}control|reliance|rely|management input|scope limitation",
            r"do(es)? not (validate|clear)|not validate|separate|remediate",
            r"independent (estimate|evaluation|report)",
        ),
        "items": [
            (0.35, "fact", (r"9448\.1", r"11063\.1", r"8126", r"15251\.6", r"6551\.3", r"5\.8")),
            (0.20, "judge", (r"45018", r"round|within|approximat", r"reconcil|tie|agree|match|foot")),
            (0.20, "judge", (r"independent", r"estimate|evaluation|appraisal",
                             r"not an? audit|not .*control|reliance|management input|rely")),
            (0.15, "judge", (r"movement", r"not|separate|beyond|distinct", r"classif|label|categor")),
            (0.10, "evidence", (3, None)),
        ],
    },
    "R-09": {
        "anchor": (r"70\.81", r"69\.12"),
        "anti": (
            r"(is|as|was) an? (reserve.?)?pricing error",
            r"must equal|has to equal|should equal",
            r"(should|must) be forced to match|should match the (unadjusted )?reference",
            r"correct the [\w\s-]{0,30}price",
            r"requires? correction|correction (is )?(required|needed)",
        ),
        "anti_lit": (
            r"(prices?|figures?) should be forced to match",
            r"price (error|misstatement) (is|was) identified",
            r"restate the (property |reference )?price",
        ),
        "pos": (
            r"adjust|differential|quality|transport",
            r"need not equal|should not .{0,30}match|not .{0,20}error|no .{0,20}correction|not require",
            r"clear|supported|explain|justif|consistent with the stated basis",
            r"constant|held (flat|constant)|unescalated",
        ),
        "items": [
            (0.30, "fact", (r"70\.81", r"69\.12", r"oil|barrel")),
            (0.25, "judge", (r"quality", r"transport", r"market|differential", r"adjust")),
            (0.20, "judge", (r"constant|held flat|unescalated|flat price", r"price")),
            (0.15, "judge", (r"clear|not .*error|no .*correction|need not equal|should not .*match|supported|explain|justif",)),
            (0.10, "evidence", (1, r"engineer_canada\.html")),
        ],
    },
    "R-10": {
        "anchor": (r"\b45\.0\b", r"\b379\.4\b", r"\b96\.1\b", r"\b686\.6\b"),
        "anti": (
            r"(are|is) an? reconcilable pair|reconcilable pair",
            r"(are|is) comparable|makes? the measures comparable",
            r"assumptions are (equivalent|the same|identical)",
            r"reconciliation is practicable",
            r"present \$?686\.6|as a bridge to the sec",
            r"may be (compared|bridged)",
            r"reconcil(?:es|ed) (?:directly )?(?:back )?to (?:the )?(?:\$?379\.4|standardi[sz]ed measure)",
        ),
        "anti_lit": (
            r"reconciliation is practicable",
            r"\bno qualification\b",
            r"need not be repeated",
        ),
        "pos": (
            r"incompar|not .{0,30}(comparable|reconcilable)|cannot be (compared|reconciled)|differ|different bas",
            r"separat|qualif|distinct|basis",
            r"non.gaap|before .{0,20}royalt|escalat|2p|working interest",
            r"includes? (income )?tax|issuer.specific",
        ),
        "items": [
            (0.30, "fact", (r"\b45\.0\b", r"\b379\.4\b", r"\b96\.1\b", r"\b686\.6\b")),
            (0.30, "judge", (r"sec", r"2p", r"wi|working interest", r"before.*royalt|prior.*royalt", r"escalat", r"non.gaap")),
            (0.20, "judge", (r"not|incompar|cannot|differ", r"reconcil|comparable|bridge",
                             r"discount|basis|framework|class")),
            (0.10, "judge", (r"includ|inclusive", r"tax", r"issuer|source|definition|generic|usual")),
            (0.10, "evidence", (1, r"earnings_release\.html")),
        ],
    },
}


# --------------------------------------------------------------------------
# Support credit versus judgement credit
#
# Only the `judge` sub-items are conditional on ``affirmed`` -- on the row
# actually stating the expert conclusion for that matter. The `fact` and
# `evidence` sub-items ask whether the row reproduces the disclosed figures and
# names a supplied file with a locator. Those are the record-keeping layer: a row
# can transcribe every anchor figure, cite the filing, and assert nothing at all,
# and still collect them. R-01 is the plain case: a row that copies
# 6,193 / 24,128 / 377 / 15,670 out of the bridge and names annual_report.html
# takes 0.35 there (0.25 fact + 0.10 evidence) with ``affirmed`` False, having
# reached no conclusion about the contradiction.
#
# Correct figures and a real citation are what make a finding checkable, not what
# makes it a finding, so the support credit is paid out in proportion to the
# submission's own judgement credit (see the support scaling in main). A review
# that reaches every expert conclusion scores 1.0 there and keeps its support
# credit at face value.
JUDGEMENT_KIND = "judge"


def judgement_capacity(weights) -> float:
    """Total weighted `judge` sub-item weight a reference-quality review can reach."""
    return sum(
        float(weights[name]) * sum(w for w, kind, _ in SPECS[name]["items"] if kind == JUDGEMENT_KIND)
        for name in SPECS
    )


def score_dimension(row: str, spec: dict) -> tuple[float, dict]:
    anti = tuple(spec["anti"])
    anti_lit = tuple(spec["anti_lit"])
    pos = tuple(spec["pos"])
    if inverted(row, anti, anti_lit):
        return 0.0, {"inverted": True, "anchor": False, "affirmed": False,
                     "judgement": 0.0, "support": 0.0}
    source_ok = sourced(row)
    anchor_ok = all(re.search(pattern, row, re.I) for pattern in spec["anchor"])
    unit_ok = not (re.search(r"\b24128\b",row) and not re.search(r"\b24128\s*M(?:M)?Boe\b",row,re.I))
    ratio_ok = not (re.search(r"\bR[-_ ]?02\b",row,re.I) and re.search(r"\b(?:0\.6|6)\s*:\s*1\b",row) and not re.search(r"\b6\s*:\s*1\b",row))
    says_it = affirmed(row, anti, pos)
    scored: list[tuple[float, bool]] = []
    judgement = 0.0
    support = 0.0
    for weight, kind, patterns in spec["items"]:
        if kind == "fact":
            ok = source_ok and unit_ok and ratio_ok and present(row, *patterns)
        elif kind == "judge":
            ok = source_ok and unit_ok and ratio_ok and bool(anchor_ok) and says_it and present(row, *patterns)
        else:
            minimum_files, required = patterns
            ok = bool(anchor_ok) and has_evidence(row, minimum_files)
            if required is not None:
                ok = ok and re.search(required, row, re.I) is not None
        scored.append((weight, bool(ok)))
        if ok:
            if kind == JUDGEMENT_KIND:
                judgement += weight
            else:
                support += weight
    return parts(*scored), {"inverted": False, "anchor": bool(anchor_ok), "affirmed": bool(says_it),
                            "judgement": round(judgement, 8), "support": round(support, 8)}


def make_scorer(name: str) -> Callable[[str], float]:
    spec = SPECS[name]

    def scorer(row: str) -> float:
        return score_dimension(row, spec)[0]

    return scorer


DIMENSIONS: dict[str, Callable[[str], float]] = {name: make_scorer(name) for name in SPECS}


MEMO_READINESS_ANTI = (
    r"(package|filing|record) (is|remains) ready",
    r"ready (to be reused|for reuse)",
    r"may approve reuse|can approve reuse|approve reuse",
    r"\bis (also )?sufficient to close\b",
    r"require no correction|requires no correction|no correction",
    r"withdraw|retract|abandon|drop (?:the )?(?:correction|evidence request)",
)
MEMO_READINESS_ANTI_LIT = (
    r"no correction (is )?(needed|required)",
    r"requires no correction",
)


def row_identifier(cells: list[str], index: int) -> str:
    for cell in cells:
        match = re.fullmatch(r"\s*([A-Za-z]{1,12}[-_ ]?\d{1,4})\s*", cell)
        if match:
            return re.sub(r"\s+", "", match.group(1)).lower()
    for cell in cells:
        match = re.search(r"\b[A-Za-z]{1,8}[-_ ]?\d{1,4}\b", cell)
        if match:
            return re.sub(r"\s+", "", match.group(0)).lower()
    return f"row-{index + 1}"


def evidence_closure(rows: list[list[str]], memo: str) -> tuple[float, dict[str, float]]:
    if not rows:
        return 0.0, {"substantive_rows": 0.0, "evidence_rows": 0.0, "memo_crossrefs": 0.0, "readiness": 0.0}
    blobs = [norm(" | ".join(row)) for row in rows]
    substantive = sum(
        len(row) >= 6
        and all(cell.strip() for cell in row[:6])
        and sum(len(re.findall(r"\b\w+\b", cell)) >= 5 for cell in row) >= 4
        and sourced(blob)
        for row, blob in zip(rows, blobs)
    ) / len(rows)
    evidence = sum(has_evidence(blob) and sourced(blob) for blob in blobs) / len(rows)
    identifiers = [row_identifier(row, i) for i, row in enumerate(rows)]
    referenced = sum(identifier in memo for identifier in identifiers)
    crossrefs = referenced / len(identifiers)
    readiness = float(
        not inverted(memo, MEMO_READINESS_ANTI, MEMO_READINESS_ANTI_LIT)
        and present(memo, r"ready|readiness|reuse|filing", r"correct|reclass|exception",
                    r"clear|reconcil|supported", r"unresolv|request|insufficient")
    )
    score = 0.30 * substantive + 0.25 * evidence + 0.25 * crossrefs + 0.20 * readiness
    return round(score, 8), {
        "substantive_rows": round(substantive, 8),
        "evidence_rows": round(evidence, 8),
        "memo_crossrefs": round(crossrefs, 8),
        "readiness": readiness,
    }


PARAMS = Path(os.environ.get("SCORING_PARAMS", Path(__file__).resolve().parent / "scoring_params.json"))
POSITIVE_OF = {**{f"R-{i:02d}": f"P{i:02d}" for i in range(1, 11)}, "evidence_and_closure": "P11"}
POSITIVE_ITEMS = sorted(POSITIVE_OF.values())
DEDUCTION_ITEMS = ["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08"]

# A negator within this many characters before a match turns it into a disclaimer
# ("we do not create a market valuation of the reserves").
GUARD_WINDOW = 30
GUARD_NEGATION = re.compile(r"\b(?:not|no|never|nor|without|neither|cannot|refrain(?:s|ed)? from|declin(?:e|es|ed) to|avoid(?:s|ed)?)\b")

# D02: the brief says "Do not re-estimate field reserves or create a market valuation".
MARKET_VALUATION = (
    r"\b(?:our|my|the review s|the reviewer s) (?:own )?(?:market |fair )?valuation\b",
    r"\bmarket valuation of the (?:proved )?reserves (?:is|of|at)\b",
    r"\bwe (?:value|revalue|re-estimate|estimate) the (?:field )?reserves\b",
)

# D03: "no conclusion may depend on information that is not provided there".
OUTSIDE_INFO = (
    r"\b(?:industry press|trade press|press reports?|news reports?|analyst (?:reports?|notes?|estimates?))\b"
    r"[^.;]{0,80}\b(?:confirm|show|indicate|establish|state|report|support)",
    r"\b(?:sources|information|reports|data) outside the (?:package|record|materials)\b"
    r"[^.;]{0,80}\b(?:confirm|show|indicate|establish|state|report|support)",
    r"\baccording to (?:news|industry|analysts?|press)\b",
)

# D07: the source states that a reconciliation of the 2P PV-10 to the SEC standardized
# measure is not practicable; asserting one manufactures a bridge the record does not support.
FORCED_RECONCILIATION = (
    r"\breconcil(?:es|ed) (?:directly )?(?:back )?to (?:the )?(?:\$?379\.4|standardi[sz]ed measure)",
    r"\b(?:is|are) (?:directly )?reconcilable (?:directly )?to (?:the )?(?:\$?379\.4|standardi[sz]ed measure)",
    r"\breconciliation (?:to the standardi[sz]ed measure )?is practicable\b",
)

# D04: the deliverables are "English-language"; any line carrying CJK, kana or hangul
# script is read on the raw text, before normalisation drops non-ASCII characters.
NON_ENGLISH = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")

# D05: core register units. Each is one material matter together with its key disclosed
# value, and must appear together in a single register row. Every unit is one the brief
# requires the register to cover (the PUD bridge, the PUD booking policy horizon, the
# engineer-to-issuer ending balance, the competing SEC / 2P value bases).
# --- memo give-away unit gate ------------------------------------------------------------------
# The register carries nearly all of the weighted score, so without a gate an emptied, halved,
# fenced or misplaced memorandum would still be paid. instruction.md makes the memo a deliverable in
# its own right ("The memo must give the committee a filing-readiness conclusion, explain the material
# matters that drive it, identify apparent high-risk inconsistencies that were cleared, and state what
# remains unresolved"), so its own units are gated rather than weighted: each missing unit is one
# damage instance at D08. Only units every complete memorandum carries are listed; cross-references
# and optional vocabulary ("unresolved", "purchase", "technology", "comparative") are not give-away.
MEMO_UNITS = {
    "filing_readiness_conclusion": r"filing[- ]readiness|filing ready|ready to file",
    "cleared_matters": r"cleared|no exception|reconcile",
    "pud_population": r"proved[- ]undeveloped|\bPUD\b",
    "standardized_measure": r"standardized|standardised measure",
    "engineer_reports": r"engineer|consultant (?:report|letter)s?",
    "extension_category": r"extension|reuse recommendation",
    "boe_basis": r"\bBOE\b|MBoe|equivalent",
}


def missing_memo_units(memo: str) -> list[str]:
    return [name for name, pattern in MEMO_UNITS.items() if not re.search(pattern, memo, re.I)]


REGISTER_UNITS = {
    "pud_bridge": (r"\b24128\b", r"\b(?:6193|15670|2698)\b"),
    "pud_policy_horizon": (r"\b(?:five|5)[\s-]*year",),
    "engineer_ending_balance": (r"\b45018\b", r"\b8126\b"),
    "competing_value_bases": (r"\b686\.6\b", r"\b96\.1\b"),
}


def guarded_hits(text: str, patterns: tuple[str, ...]) -> int:
    count = 0
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if GUARD_NEGATION.search(text[max(0, match.start() - GUARD_WINDOW):match.start()]):
                continue
            count += 1
    return count


def register_units(row_blobs: list[str]) -> dict[str, bool]:
    return {
        unit: any(all(re.search(p, blob) for p in patterns) for blob in row_blobs)
        for unit, patterns in REGISTER_UNITS.items()
    }


def extra_damage(memo: str, row_blobs: list[str], raw_texts: list[str], units: dict[str, bool],
                 memo_present: bool, register_present: bool) -> list[dict]:
    instances = []
    for label, text in [("memo", memo)] + [(f"row{i}", blob) for i, blob in enumerate(row_blobs)]:
        for _ in range(guarded_hits(text, MARKET_VALUATION)):
            instances.append({"key": f"market_valuation:{label}", "item_ids": ["D02"]})
        for _ in range(guarded_hits(text, OUTSIDE_INFO)):
            instances.append({"key": f"outside_support:{label}", "item_ids": ["D03"]})
        for _ in range(guarded_hits(text, FORCED_RECONCILIATION)):
            instances.append({"key": f"forced_reconciliation:{label}", "item_ids": ["D07"]})
    if any(NON_ENGLISH.search(raw) for raw in raw_texts):
        from semantic_judge import adjudicate
        candidate = "MEMORANDUM\n" + raw_texts[0] + "\nREGISTER\n" + (raw_texts[1] if len(raw_texts)>1 else "")
        source = (Path(__file__).parent / "language_source.json").read_text()
        try:
            language = adjudicate(candidate, source)
        except Exception as exc:
            scoring_error("required language adjudication failed: " + type(exc).__name__)
        for key,role in (("MEMO_NONENGLISH","memo"),("REGISTER_NONENGLISH","register")):
            if language["items"][key]["fraction"]:
                instances.append({"key": "non_english_analysis:"+role, "item_ids": ["D04"], "semantic_evidence": language["items"][key]})
    # D05 retired: missing substantive units already lose their positive shares.
    if memo_present or register_present:
        if not memo_present:
            instances.append({"key": "missing_deliverable:reserve_disclosure_review.md", "item_ids": ["D06"]})
        missing_units = missing_memo_units(memo)
        if missing_units:
            instances.append({"key": "memo_units_missing", "item_ids": ["D08"],
                              "missing_units": missing_units})
        if not register_present:
            instances.append({"key": "missing_deliverable:reserve_disclosure_register.csv", "item_ids": ["D06"]})
    return instances


def load_params() -> dict:
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    if set(params["positive_weights"]) != set(POSITIVE_ITEMS) or set(params["deduction_amounts"]) != set(DEDUCTION_ITEMS):
        raise ValueError(f"{PARAMS}: item vocabulary differs from the validator ledger")
    return params


def settle(scaled_scores: dict[str, float], dispersion: float, integrity: bool,
           integrity_detail: str, extra_instances: list[dict]) -> tuple[float, dict]:
    """Settle the strict score in pd-ledger-v1 form and return it with its ledger."""
    params = load_params()
    weights, amounts = params["positive_weights"], params["deduction_amounts"]
    completion = {item: 0.0 for item in POSITIVE_ITEMS}
    for name, score in scaled_scores.items():
        completion[POSITIVE_OF[name]] = round(max(0.0, min(1.0, float(score) * dispersion)), 8)
    instances = []
    if not integrity:
        instances.append({"key": "source_integrity:" + str(integrity_detail), "item_ids": ["D01"]})
    instances.extend(extra_instances)
    positive_earned = sum(float(weights[item]) * completion[item] for item in POSITIVE_ITEMS)
    by_key = {}
    for instance in instances:
        amount = max(float(amounts[item]) for item in instance["item_ids"])
        by_key[instance["key"]] = max(by_key.get(instance["key"], 0.0), amount)
    deduction_total = min(1.0, sum(by_key.values()))
    final = round(max(0.0, positive_earned - deduction_total), 8)
    return final, {
        "schema_version": "pd-ledger-v1",
        "positive_completion": completion,
        "damage_instances": instances,
        "positive_earned": round(positive_earned, 8),
        "deduction_by_key": by_key,
        "deduction_total": round(deduction_total, 8),
        "final_score": final,
    }


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/output")
    memo_path, register_path = resolve_outputs(target)
    rows, header = read_rows(register_path)
    try:
        memo_raw = _guard_deliverable_text(memo_path.read_text(encoding="utf-8") if memo_path.is_file() else "")
    except OSError as exc:
        scoring_error(f"cannot read {memo_path}: {exc}")
    except UnicodeError:
        memo_raw = ""
    memo = norm(memo_raw)
    row_blobs = [norm(" | ".join(row)) for row in rows]

    # Support scaling and settlement must use one parameter source.  The old
    # diagnostic R-weights were used here while settle() used P-weights, making
    # the displayed contribution and the actual score disagree.
    params = load_params()
    weights = {name: float(params["positive_weights"][POSITIVE_OF[name]]) for name in SPECS}
    weights["evidence_and_closure"] = float(params["positive_weights"]["P11"])

    dimension_scores: dict[str, float] = {}
    winning_rows: dict[str, int | None] = {}
    direction_detail: dict[str, dict] = {}
    winning_split: dict[str, tuple[float, float]] = {}
    row_ids=[row_identifier(row,i) for i,row in enumerate(rows)]
    superseded=set()
    all_adoption_text=[memo,*row_blobs]
    for identifier in row_ids:
        pattern=rf"(?:supersed|replace|withdraw|retract|no longer adopt)[^.;]{{0,60}}\b{re.escape(identifier)}\b"
        if any(re.search(pattern,text,re.I) for text in all_adoption_text):superseded.add(identifier)
    for name in SPECS:
        spec = SPECS[name]
        results = [(0.0,{"inverted":False,"anchor":False,"affirmed":False,"judgement":0.0,"support":0.0})
                   if row_ids[i] in superseded else score_dimension(row, spec)
                   for i,row in enumerate(row_blobs)]
        # A row explicitly marked as an inverted conclusion cannot be the
        # winning support for a matter merely because an older correct row is
        # also present.  Resolve the adopted direction before taking the best
        # row; if every row is inverted the matter earns zero.
        admissible = [item for item in results if not item[1]["inverted"]]
        scores = [item[0] for item in admissible]
        best = max(scores, default=0.0)
        dimension_scores[name] = best
        chosen = admissible[scores.index(best)] if best > 0 else None
        index = results.index(chosen) if chosen is not None else None
        winning_rows[name] = index
        # The row that supports a dimension is still chosen on its unscaled total,
        # so the support scaling below cannot move which row wins or the
        # dispersion factor computed from the winners.
        if index is None:
            winning_split[name] = (0.0, 0.0)
        else:
            meta = results[index][1]
            winning_split[name] = (meta["judgement"], meta["support"])
        direction_detail[name] = {
            "inverted_rows": [i for i, item in enumerate(results) if item[1]["inverted"]],
            "anchor_rows": [i for i, item in enumerate(results) if item[1]["anchor"]],
        }

    closure_score, closure_detail = evidence_closure(rows, memo)
    dimension_scores["evidence_and_closure"] = closure_score
    positive_winners = [winning_rows[name] for name in SPECS if dimension_scores[name] > 0 and winning_rows[name] is not None]
    dispersion = 1.0  # Independently complete matters may share a register row.

    # Support credit (figures transcribed, files cited, register/memo structure)
    # is paid out in proportion to the judgement credit the submission reached;
    # see the note beside JUDGEMENT_KIND. `evidence_and_closure` is entirely
    # support, so the whole dimension is scaled.
    local_support_scales = {}
    scaled_scores = {}
    judgement_total = sum(
        float(weights[name]) * winning_split[name][0] for name in SPECS)
    judgement_capacity_total = sum(
        float(weights[name]) * sum(weight for weight, kind, _ in SPECS[name]["items"]
                                   if kind == JUDGEMENT_KIND)
        for name in SPECS)
    for name in SPECS:
        capacity = sum(weight for weight, kind, _ in SPECS[name]["items"]
                       if kind == JUDGEMENT_KIND)
        local_scale = (max(0.0, min(1.0, winning_split[name][0] / capacity))
                       if capacity else 1.0)
        local_support_scales[name] = local_scale
        scaled_scores[name] = round(
            winning_split[name][0] + winning_split[name][1] * local_scale, 8)
    scaled_scores["evidence_and_closure"] = round(closure_score, 8)
    integrity, integrity_detail = source_integrity(target)
    units = register_units(row_blobs)
    raw_texts = [memo_raw]
    if register_path.is_file():
        try:
            raw_texts.append(register_path.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            scoring_error(f"cannot read {register_path}: {exc}")
        except UnicodeError:
            pass
    extra = extra_damage(memo, row_blobs, raw_texts, units, memo_path.is_file(), register_path.is_file())
    strict, ledger = settle(scaled_scores, dispersion, integrity, integrity_detail, extra)

    # Required matters retain continuous unscaled partial credit.
    lenient_completion = {POSITIVE_OF[name]: float(score) for name, score in dimension_scores.items()}
    lenient_required_met = {
        item: lenient_completion.get(item, 0.0) >= 1.0 - 1e-9 for item in LENIENT_REQUIRED_ITEMS
    }
    # The memo's own give-away units are part of the lens: a memorandum missing them is not a
    # circulable deliverable, so a half-deleted memo does not pass the lenient lens.
    memo_units_met = not missing_memo_units(memo)
    delivery_gate = memo_path.is_file() and register_path.is_file() and bool(memo_raw.strip()) and bool(rows)
    blocking_damage = bool(ledger.get("damage_instances"))
    lenient = float(
        integrity and delivery_gate and memo_units_met and not blocking_damage
        and all(lenient_required_met.values()))
    lenient_detail = {
        "required_items": list(LENIENT_REQUIRED_ITEMS),
        "required_item_met": lenient_required_met,
        "required_item_completion": {
            item: round(lenient_completion.get(item, 0.0), 8) for item in LENIENT_REQUIRED_ITEMS
        },
        "register_units": units,
        "memo_units_missing": missing_memo_units(memo),
        "source_integrity_gate": bool(integrity),
    }

    result = {
        "rewards": {"strict": strict, "lenient": lenient},
        "reward": strict,
        "reward_formulas": {
            "strict": "max(0, positive_earned - deduplicated root deductions)",
            "lenient": "1 iff P03,P08,P09,P11 are complete, both deliverables and source integrity pass, memo units are present, and no damage root fires",
        },
        "group_points": {name: round(float(weights[name]) * score, 8) for name, score in scaled_scores.items()},
        "dimension_scores": scaled_scores,
        "dimension_scores_unscaled": dimension_scores,
        "gates": {
            "source_integrity": integrity,
            "memo_present": memo_path.is_file(),
            "register_present": register_path.is_file(),
        },
        "diagnostics": {
            "source_integrity": integrity_detail,
            "row_count": len(rows),
            "header_width": len(header),
            "semantic_dispersion": round(dispersion, 8),
            "support_scaling": {
                "judgement_credit": round(judgement_total, 8),
                "judgement_capacity": round(judgement_capacity_total, 8),
                "local_support_scales": {name: round(value, 8) for name, value in local_support_scales.items()},
                "winning_split": {name: list(winning_split[name]) for name in SPECS},
            },
            "winning_rows": winning_rows,
            "direction": direction_detail,
            "closure": closure_detail,
            "lenient": lenient_detail,
        },
        "scoring_ledger": ledger,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Derive the reference reconciliation report from anchored manuscript evidence."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path


EXPECTED_SHA256 = "55eb299c521ddcba76991e3de46ad205cb8a08be8f1b5f8c4a48ff6d01e74ed7"


@dataclass(frozen=True)
class FindingRule:
    key: str
    state: str
    category: str
    location: str
    observed: str
    counterpart: str
    evidence: str
    disposition: str
    required_anchors: tuple[tuple[int, str], ...]
    absent_from_references: str | None = None
    absent_from_body: str | None = None


@dataclass(frozen=True)
class ClearedRule:
    key: str
    forms: str
    location: str
    reason: str
    required_anchors: tuple[tuple[int, str], ...]


FINDING_RULES = (
    FindingRule(
        "F01", "Author decision required", "Cited-only work", "printed p. 4592, opening lines (physical p. 4)",
        "Bergstrom and Forsman, 1973", "No Bergstrom/Forsman 1973 entry appears on reference-list pp. 4605-4607.",
        "The callout occurs in the HBV-96 expansion, while the supplied list contains Bergstrom records from 1994, 1995, and 2001 but none coauthored by Forsman in 1973.",
        "Ask the authors to supply the full 1973 record or remove/replace the callout; do not infer the missing metadata.",
        ((4, "Bergstrom and Forsman, 1973"),), r"forsman.{0,80}1973",
    ),
    FindingRule(
        "F02", "Author decision required", "Cited-only work", "printed p. 4594, lines 23-25 (physical p. 6)",
        "Van den Hurk et al., 2005", "No Van den Hurk-led 2005 entry appears on reference-list pp. 4605-4607.",
        "The PRUDENCE sentence gives 2005; the available Hurk van den-led record is explicitly 2006 and is a different year identity.",
        "Request the full 2005 record or author-confirmed replacement/removal of the callout; do not collapse it into the 2006 record.",
        ((6, "Van den Hurk et al, 2005"), (18, "Hurk van den, B.")), r"hurk van den.{0,250}2005",
    ),
    FindingRule(
        "F03", "Author decision required", "Cited-only work", "printed p. 4603, lines 15-17 (physical p. 15)",
        "Jacob et al., 2007", "No Jacob-led 2007 entry appears on reference-list pp. 4605-4607.",
        "The discussion groups this callout with two Leander studies; the only listed record containing Jacob is Lorenz and Jacob (2008), not a Jacob-led 2007 work.",
        "Ask the authors for the full Jacob et al. 2007 record or removal/replacement of that atomic callout.",
        ((15, "Jacob et al., 2007"), (18, "Lorenz, P. and Jacob, D.")), r"\bjacob\s*,[^.;]{0,100}2007",
    ),
    FindingRule(
        "F04", "Author decision required", "Cited-only work", "printed pp. 4604-4605, line 25 and opening lines (physical pp. 16-17)",
        "Leander et al. 2005", "No Leander-led 2005 entry appears on reference-list pp. 4605-4607.",
        "The work is invoked twice for HBV flood-peak and inundation limitations; the list contains Leander records only for 2007 and 2008.",
        "Request the full 2005 record or author-confirmed replacement/removal, preserving both occurrence locations in the query.",
        ((16, "Leander et al. 2005"), (17, "Leander et al. (2005)"), (18, "Leander, R. and Buishand")), r"\bleander\s*,[^.;]{0,160}2005",
    ),
    FindingRule(
        "F05", "Author decision required", "Listed-only record", "reference list, printed p. 4607, opening lines (physical p. 19)",
        "Swedish Meteorological and Hydrological Institute (SMHI): The HBV model, 2007", "No formal SMHI 2007 author-date callout occurs before the reference list.",
        "The methods text mentions the institute and says HBV was developed in the early 1970s, but it does not attach 2007 to that attribution.",
        "Ask whether a claim should receive an SMHI (2007) callout; otherwise remove the unused record. Do not turn the undated institution mention into a citation silently.",
        ((7, "Swedish Meteorological and Hydrological Institute (SMHI)"), (19, "Swedish Meteorological and Hydrological Institute (SMHI): The HBV model, 2007")),
        absent_from_body=r"smhi.{0,15}(?:,|\()\s*2007|swedish meteorological and hydrological institute.{0,40}2007",
    ),
    FindingRule(
        "F06", "Author decision required", "Credited-author conflict", "callout at printed p. 4591, lines 25-26; candidate entry at p. 4607 (physical pp. 3 and 19)",
        "STOWA, 2004", "The only 2004 entry containing STOWA credits Smits, Wijngaarden, Versteeg, and Kok as authors and places STOWA later in the record.",
        "The shared year and unique STOWA token make the Smits record a candidate, but the supplied manuscript does not establish that a publisher-like field may replace the credited author.",
        "Ask the authors to confirm the intended work and credited author; if the candidate is intended, change the callout to Smits et al. (2004), otherwise supply the intended STOWA-authored record.",
        ((3, "STOWA, 2004"), (19, "Smits, I., Wijngaarden, J., Versteeg, R. and Kok, M."), (19, "Utrecht, STOWA, 2004")),
    ),
    FindingRule(
        "F07", "Confirmed discrepancy", "Two-author callout form", "printed p. 4595, lines 23-24 (physical p. 7)",
        "Bergstrom et al., 1994", "The p. 4606 record has exactly two authors: Bergstrom and Carlsson.",
        "Elsewhere the manuscript distinguishes named pairs from multi-author et al. forms; the work identity is otherwise established by first author and year.",
        "Replace the callout component Bergstrom et al., 1994 with Bergstrom and Carlsson, 1994 within the parenthetical group, retaining the manuscript's chosen accent convention.",
        ((7, "Bergstrom et al., 1994"), (18, "Bergstrom, S. and Carlsson, B.")),
    ),
    FindingRule(
        "F08", "Confirmed discrepancy", "Two-author callout form", "printed p. 4593, opening line (physical p. 5)",
        "Warmerdam et al., 2001", "The p. 4607 record has exactly two authors: Warmerdam and Wit de.",
        "The author-year identity is unique, but et al. suppresses the second author of a two-author record.",
        "Change the callout component Warmerdam et al., 2001 to Warmerdam and de Wit, 2001 within the parenthetical group, using the manuscript's particle convention consistently.",
        ((5, "Warmerdam et al., 2001"), (19, "Warmerdam, P. M. M. and Wit de, M. J. M.")),
    ),
    FindingRule(
        "F09", "Confirmed discrepancy", "Two-author callout form", "printed p. 4593, lines 5-7 (physical p. 5)",
        "Lorenz et al., 2008", "The p. 4606 record has exactly two authors: Lorenz and Jacob.",
        "The ENSEMBLES context and unique first-author/year link establish the record, leaving an author-cardinality error in the callout.",
        "Change the parenthetical callout to (Lorenz and Jacob, 2008).",
        ((5, "Lorenz et al., 2008"), (18, "Lorenz, P. and Jacob, D.")),
    ),
    FindingRule(
        "F10", "Confirmed discrepancy", "Two-author callout form", "printed pp. 4593, 4595-4598 and 4603 (physical pp. 5, 7-10 and 15)",
        "Leander et al., 2007", "The p. 4606 record has exactly two authors: Leander and Buishand.",
        "Multiple occurrences resolve to the same two-author 2007 record, whereas the listed 2008 Leander work has four authors.",
        "At each 2007 occurrence, use Leander and Buishand while preserving whether the source location is narrative or parenthetical; do not change correct 2008 et al. callouts.",
        ((5, "Leander et al., 2007"), (7, "Leander et al. (2007)"), (18, "Leander, R. and Buishand, T. A.")),
    ),
    FindingRule(
        "F11", "Confirmed discrepancy", "Single-author callout form", "printed pp. 4592 and 4604 (physical pp. 4 and 16)",
        "Wit de et al., 2001a", "The p. 4607 record for 2001a credits only M. J. M. de Wit.",
        "The year suffix and unique title entry resolve identity; et al. invents additional authors. On p. 4604 the malformed item shares a group with the valid multi-author 2007b item.",
        "Use the single-author de Wit form with 2001a while preserving local citation grammar; on p. 4604 separate it from the retained de Wit et al. 2007b component.",
        ((4, "Wit de et al., 2001a"), (16, "2001a, 2007b; Booij, 2005"), (19, "Wit de, M. J. M.: Effect of climate change")),
    ),
    FindingRule(
        "F12", "Confirmed discrepancy", "Year-suffix mismatch", "printed p. 4592, lines 10-13 (physical p. 4)",
        "De Wit (2001)", "The matching single-author record is labeled 2001a on p. 4607; no unsuffixed de Wit 2001 entry is listed.",
        "The unique single-author record and matching climate-impact context establish the candidate without changing authorship.",
        "Change the narrative citation to De Wit (2001a).",
        ((4, "De Wit (2001)"), (19, "Wit de, M. J. M.: Effect of climate change"), (19, "UR, 2001a")),
    ),
    FindingRule(
        "F13", "Confirmed discrepancy", "Multi-author callout form", "printed p. 4592, lines 20-25 (physical p. 4)",
        "De Wit (2007a)", "The p. 4607 low-flows record labeled 2007a has six authors.",
        "The same page later uses De Wit et al. (2007a) for the same low-flow work, establishing the manuscript's own applicable form.",
        "Change the singular narrative form to De Wit et al. (2007a).",
        ((4, "De Wit (2007a)"), (4, "De Wit et al. (2007a)"), (19, "Impact of climate change on low-flows")),
    ),
    FindingRule(
        "F14", "Confirmed discrepancy", "Multi-author callout form", "printed p. 4604, line 25 (physical p. 16)",
        "De Wit (2007b)", "The p. 4607 record labeled 2007b has three authors: de Wit, Buiteveld, and van Deursen.",
        "The suffix uniquely identifies the listed record, but the narrative form omits two credited authors.",
        "Change the narrative citation to De Wit et al. (2007b).",
        ((16, "De Wit (2007b)"), (19, "Buiteveld, H., and Deursen van"), (19, "RIZA, 2007b")),
    ),
    FindingRule(
        "F15", "Author decision required", "Unsuffixed ambiguous callout", "printed p. 4605, lines 5-10 (physical p. 17)",
        "De Wit (2007)", "No unsuffixed de Wit 2007 record is listed; p. 4607 instead has distinct 2007a and 2007b multi-author records.",
        "The surrounding critical-low-flow claim points toward the 2007a low-flows title, but context alone does not prove the authors' intended source.",
        "Ask the authors to confirm the intended work; if 2007a is intended, change to De Wit et al. (2007a), otherwise supply the correct identity.",
        ((17, "results of De Wit (2007)"), (19, "RIZA, 2007b"), (19, "Impact of climate change on low-flows")),
    ),
    FindingRule(
        "F16", "Confirmed discrepancy", "Compact narrative, 2007 component", "printed p. 4598, lines 13-15 (physical p. 10)",
        "Leander (2007, 2008) - 2007 component", "The p. 4606 record for 2007 has two authors: Leander and Buishand.",
        "The one-name narrative cannot correctly represent this two-author component, and the adjacent year resolves to a different author group.",
        "Split the compact citation and render this component as Leander and Buishand (2007).",
        ((10, "described by Leander (2007, 2008)"), (18, "Leander, R. and Buishand, T. A.")),
    ),
    FindingRule(
        "F17", "Confirmed discrepancy", "Compact narrative, 2008 component", "printed p. 4598, lines 13-15 (physical p. 10)",
        "Leander (2007, 2008) - 2008 component", "The p. 4606 record for 2008 has four authors: Leander, Buishand, van den Hurk, and de Wit.",
        "The singular narrative omits coauthors, and the author list differs from the preceding 2007 component.",
        "Split the compact citation and render this component as Leander et al. (2008).",
        ((10, "described by Leander (2007, 2008)"), (18, "Leander, R., Buishand, T., van den Hurk")),
    ),
)


CLEARED_RULES = (
    ClearedRule("C01", "Ashagrie et al. (2006) / Ashagrie-led 2006 entry", "printed pp. 4594 and 4605", "The formal body callout and the reference head agree; no listed-only finding is warranted.", ((6, "Ashagrie et al., 2006"), (17, "Ashagrie, A. G."))),
    ClearedRule("C02", "Bakker (2008) / Bakker 2008 entry", "printed pp. 4595 and 4606", "This is a narrative callout split across text lines, not an unused record.", ((7, "developed by Bakker"), (7, "(2008)"), (18, "Bakker, A."))),
    ClearedRule("C03", "Bergstrom et al. (2001) / Bergstrom-led 2001 entry", "printed pp. 4592 and 4606", "Accent loss and Unicode composition do not change the author-year identity.", ((4, "Bergstrom et al., 2001"), (18, "Climate change impacts on runoff in Sweden"))),
    ClearedRule("C04", "Hurk van den et al. (2006) / Hurk van den-led 2006 entry", "printed pp. 4591 and 4606", "Capitalization and surname-particle presentation preserve identity; this is distinct from the missing 2005 work.", ((3, "Hurk van den et al., 2006"), (18, "KNMI Climate Change Scenarios 2006"))),
    ClearedRule("C05", "van Schrojenstein Lantman (2004) / Van Schrojenstein Lantman 2004 entry", "printed pp. 4596 and 4607", "Sentence-position capitalization does not create a different author.", ((8, "van Schrojenstein Lantman, 2004"), (19, "Van Schrojenstein Lantman, J."))),
    ClearedRule("C06", "Booij (2002b) / Booij 2002b entry", "printed pp. 4591 and 4606", "The suffix agrees on both surfaces. The absence of a visible 2002a record is not evidence for changing a matching pair.", ((3, "Booij, 2002b"), (18, "2002b"))),
    ClearedRule("C07", "Wit de / De Wit / de Wit", "multiple body locations and printed p. 4607", "Reference inversion, sentence capitalization, and lowercase particles are compatible identity forms; author cardinality and suffix defects are evaluated separately.", ((4, "De Wit et al. (2007a)"), (19, "Wit de, M. J. M."))),
    ClearedRule("C08", "Leander et al. (2008) / four-author Leander 2008 entry", "multiple body locations and printed p. 4606", "The et al. form is compatible with the four-author record and must not be changed with the defective 2007 forms.", ((11, "Leander et al., 2008"), (18, "Leander, R., Buishand, T., van den Hurk"))),
)


@dataclass(frozen=True)
class OccurrenceRule:
    key: str
    physical_page: int
    printed_page: str
    observed: str
    components: tuple[str, ...]
    status: str
    mapping: str
    anchor: str
    explicitness: str = "explicit"


@dataclass(frozen=True)
class ReferenceRule:
    key: str
    physical_page: int | str
    printed_page: str
    head: str
    year: str
    title: str
    status: str
    anchor: str


@dataclass(frozen=True)
class PatchRule:
    key: str
    finding: str
    location: str
    current: str
    proposed: str
    record: str
    evidence: str


@dataclass(frozen=True)
class ExclusionRule:
    key: str
    physical_page: int
    printed_page: str
    token: str
    context: str
    reason: str


@dataclass(frozen=True)
class CollisionRule:
    key: str
    stem: str
    body_components: str
    candidate_records: str
    explicitness: str
    state: str
    evidence: str
    required_anchors: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class ActionRule:
    key: str
    finding: str
    owner: str
    precondition: str
    state: str


# The ledger rows are deliberately occurrence-level.  Repeated uses of one work
# remain separate rows so that a production editor can check every occurrence.
OCCURRENCE_RULES = (
    OccurrenceRule("O01", 2, "4590", "(IPCC, 2007)", ("IPCC 2007",), "linked", "R10", "IPCC, 2007"),
    OccurrenceRule("O02", 3, "4591", "(Hurk van den et al., 2006)", ("Hurk van den 2006",), "linked", "R09", "Hurk van den et al., 2006"),
    OccurrenceRule("O03", 3, "4591", "(Wit de et al., 2001b)", ("Wit de 2001b",), "linked", "R27", "Wit de et al., 2001b"),
    OccurrenceRule("O04", 3, "4591", "(Uijlenhoet et al., 2001)", ("Uijlenhoet 2001",), "linked", "R22", "Uijlenhoet"),
    OccurrenceRule("O05", 3, "4591", "(Tu et al., 2005b)", ("Tu 2005b",), "linked", "R21", "Tu et al., 2005b"),
    OccurrenceRule("O06", 3, "4591", "(Booij, 2002b)", ("Booij 2002b",), "linked", "R07", "Booij, 2002b"),
    OccurrenceRule("O07", 3, "4591", "(STOWA, 2004)", ("STOWA 2004",), "candidate", "R19", "STOWA, 2004"),
    OccurrenceRule("O08", 4, "4592", "(Hydrologiska Byråns Vattenbalansavdelning; Hydrological Bureau Water balance-section; Bergström and Forsman, 1973)", ("Bergstrom Forsman 1973",), "cited-only", "none", "Bergstrom and Forsman, 1973"),
    OccurrenceRule("O09", 4, "4592", "(Bergstrom et al., 2001)", ("Bergstrom 2001",), "linked", "R04", "Bergstrom et al., 2001"),
    OccurrenceRule("O10", 4, "4592", "(Pfister et al., 2004)", ("Pfister 2004",), "linked", "R16", "Pfister et al., 2004"),
    OccurrenceRule("O11", 4, "4592", "(Wit de et al., 2001a; Wit de et al., 2007b)", ("Wit de 2001a", "Wit de 2007b"), "mixed", "R25; R26", "Wit de et al., 2001a; Wit de et al., 2007b"),
    OccurrenceRule("O12", 4, "4592", "(Tu et al., 2005a)", ("Tu 2005a",), "linked", "R20", "demonstrated statistically (Tu et"),
    OccurrenceRule("O13", 4, "4592", "De Wit (2001)", ("De Wit 2001",), "suffix-defect", "R25", "De Wit (2001)"),
    OccurrenceRule("O14", 4, "4592", "(Booij, 2005)", ("Booij 2005",), "linked", "R08", "Booij, 2005"),
    OccurrenceRule("O15", 4, "4592", "(Aalders et al., 2004)", ("Aalders 2004",), "linked", "R01", "Aalders"),
    OccurrenceRule("O16", 4, "4592", "(Wit de et al., 2007a)", ("Wit de 2007a",), "linked", "R28", "de et al., 2007a). On the occurrence"),
    OccurrenceRule("O17", 4, "4592", "De Wit (2007a)", ("De Wit 2007a",), "form-defect", "R28", "De Wit (2007a)"),
    OccurrenceRule("O18", 4, "4592", "De Wit et al. (2007a)", ("De Wit 2007a",), "linked", "R28", "De Wit et al. (2007a)"),
    OccurrenceRule("O19", 5, "4593", "(Warmerdam et al., 2001; Wit de et al., 2001b)", ("Warmerdam 2001", "Wit de 2001b"), "mixed", "R24; R27", "Warmerdam et al., 2001; Wit de et al., 2001b"),
    OccurrenceRule("O20", 5, "4593", "(Lorenz et al., 2008)", ("Lorenz 2008",), "form-defect", "R15", "Lorenz et al., 2008"),
    OccurrenceRule("O21", 5, "4593", "(Leander et al., 2007; Wit de et al., 2007a; Leander et al., 2008)", ("Leander 2007", "Wit de 2007a", "Leander 2008"), "mixed", "R12; R28; R13", "Leander et al., 2007; Wit de et al., 2007a; Leander"),
    OccurrenceRule("O22", 5, "4593", "(Booij, 2005)", ("Booij 2005",), "linked", "R08", "Booij, 2005"),
    OccurrenceRule("O23", 5, "4593", "(Leander et al., 2007)", ("Leander 2007",), "form-defect", "R12", "Leander et al., 2007"),
    OccurrenceRule("O24", 5, "4593", "(Leander et al., 2007)", ("Leander 2007",), "form-defect", "R12", "Leander et al., 2007"),
    OccurrenceRule("O25", 6, "4594", "(Pfister et al., 2004)", ("Pfister 2004",), "linked", "R16", "Pfister et al., 2004"),
    OccurrenceRule("O26", 6, "4594", "(Ashagrie et al., 2006)", ("Ashagrie 2006",), "linked", "R02", "Ashagrie et al., 2006"),
    OccurrenceRule("O27", 6, "4594", "(Lenderink et al., 2003)", ("Lenderink 2003",), "linked", "R14", "Lenderink et al., 2003"),
    OccurrenceRule("O28", 6, "4594", "(Van den Hurk et al, 2005)", ("Van den Hurk 2005",), "cited-only", "none", "Van den Hurk et al, 2005"),
    OccurrenceRule("O29", 7, "4595", "(Roeckner et al., 2003)", ("Roeckner 2003",), "linked", "R17", "Roeckner et al., 2003"),
    OccurrenceRule("O30", 7, "4595", "Leander et al. (2007)", ("Leander 2007",), "form-defect", "R12", "Leander et al. (2007)"),
    OccurrenceRule("O31", 7, "4595", "(Leander et al., 2007)", ("Leander 2007",), "form-defect", "R12", "first bias correction method is developed by (Leander et"),
    OccurrenceRule("O32", 7, "4595", "Bakker (2008)", ("Bakker 2008",), "linked", "R03", "Bakker"),
    OccurrenceRule("O33", 7, "4595", "(Bergström et al., 1994; Bergström, 1995)", ("Bergstrom 1994", "Bergstrom 1995"), "mixed", "R06; R05", "Bergström et al., 1994; Bergström, 1995"),
    OccurrenceRule("O34", 8, "4596", "(Booij, 2005)", ("Booij 2005",), "linked", "R08", "Booij, 2005"),
    OccurrenceRule("O35", 8, "4596", "(Leander et al., 2007)", ("Leander 2007",), "form-defect", "R12", "al., 2007). The HBV model is run"),
    OccurrenceRule("O36", 8, "4596", "(van Schrojenstein Lantman, 2004)", ("van Schrojenstein Lantman 2004",), "linked", "R23", "van Schrojenstein Lantman, 2004"),
    OccurrenceRule("O37", 8, "4596", "(Wit de et al., 2007a)", ("Wit de 2007a",), "linked", "R28", "Wit de et al., 2007a"),
    OccurrenceRule("O38", 9, "4597", "(Leander et al., 2007)", ("Leander 2007",), "form-defect", "R12", "Leander et al., 2007"),
    OccurrenceRule("O39", 10, "4598", "Leander (2007, 2008)", ("Leander 2007", "Leander 2008"), "compact-form-defect", "R12; R13", "Leander (2007, 2008)", "inherited/mixed"),
    OccurrenceRule("O40", 10, "4598", "(Leander et al., 2007)", ("Leander 2007",), "form-defect", "R12", "Leander et al., 2007"),
    OccurrenceRule("O41", 11, "4599", "(Leander et al., 2008)", ("Leander 2008",), "linked", "R13", "Leander et al., 2008"),
    OccurrenceRule("O42", 15, "4603", "(Jacob et al., 2007; Leander et al., 2007; Leander et al., 2008)", ("Jacob 2007", "Leander 2007", "Leander 2008"), "mixed", "none; R12; R13", "Jacob et al., 2007; Leander et al., 2007; Leander et al., 2008"),
    OccurrenceRule("O43", 16, "4604", "(KNMI, 2006)", ("KNMI 2006",), "linked", "R11", "KNMI, 2006"),
    OccurrenceRule("O44", 16, "4604", "(Wit de et al., 2001a, 2007b; Booij, 2005)", ("Wit de 2001a", "Wit de 2007b", "Booij 2005"), "mixed", "R25; R26; R08", "Wit de et al., 2001a, 2007b; Booij, 2005", "inherited/mixed"),
    OccurrenceRule("O45", 16, "4604", "(Leander et al., 2008)", ("Leander 2008",), "linked", "R13", "Leander et al., 2008"),
    OccurrenceRule("O46", 16, "4604", "(Booij 2005; Leander et al. 2005)", ("Booij 2005", "Leander 2005"), "mixed", "R08; none", "Booij 2005; Leander et al. 2005"),
    OccurrenceRule("O47", 16, "4604", "De Wit (2007b)", ("De Wit 2007b",), "form-defect", "R26", "De Wit (2007b)"),
    OccurrenceRule("O48", 17, "4605", "Leander et al. (2005)", ("Leander 2005",), "cited-only", "none", "Leander et al. (2005)"),
    OccurrenceRule("O49", 17, "4605", "De Wit (2007)", ("De Wit 2007",), "ambiguous", "R28; R26", "De Wit (2007)"),
    OccurrenceRule("O50", 17, "4605", "(Wit de et al., 2007a)", ("Wit de 2007a",), "linked", "R28", "Wit de et al., 2007a"),
)


REFERENCE_RULES = (
    ReferenceRule("R01", 17, "4605", "Aalders, P., Warmerdam, P. M. M., and Torfs, P. J. J. F.", "2004", "Rainfall generator for the Meuse basin", "used", "Aalders, P., Warmerdam"),
    ReferenceRule("R02", 17, "4605", "Ashagrie, A. G., Laat de, P. J. M., Wit de, M. J. M., and Uhlenbrook, S.", "2006", "Detecting the influence of land use changes", "used", "Ashagrie, A. G."),
    ReferenceRule("R03", 18, "4606", "Bakker, A.", "2008", "Bias correction and resampling of RCM daily precipitation", "used", "Bakker, A."),
    ReferenceRule("R04", 18, "4606", "Bergstrom, S., Carlsson, B., Gardelin, M., Lindstrom, G., Pettersson, A. and Rummukainen, M.", "2001", "Climate change impacts on runoff in Sweden", "used", "Bergstrom, S., Carlsson"),
    ReferenceRule("R05", 18, "4606", "Bergström, S.", "1995", "The HBV model", "used", "Bergström, S.: The HBV model"),
    ReferenceRule("R06", 18, "4606", "Bergström, S. and Carlsson, B.", "1994", "River Runoff to the Baltic Sea", "used", "Bergström, S. and Carlsson"),
    ReferenceRule("R07", 18, "4606", "Booij, M. J.", "2002b", "Extreme daily precipitation in western Europe", "used", "Booij, M. J.: Extreme daily"),
    ReferenceRule("R08", 18, "4606", "Booij, M. J.", "2005", "Impact of climate change on river flooding", "used", "Booij, M. J.: Impact of climate"),
    ReferenceRule("R09", 18, "4606", "Hurk van den, B., Albert, K. T., Lenderink, G., Ulden van, A., Oldenborgh van, G. J., Katsman, C., Brink van den, H., Keller, F., Bessembinder, J., Burgers, G., Komen, G., Hazeleger, W. and Drijfhout, S.", "2006", "KNMI Climate Change Scenarios 2006", "used", "Hurk van den, B., Albert"),
    ReferenceRule("R10", 18, "4606", "IPCC", "2007", "Climate Change 2007: Synthesis Report", "used", "IPCC: Climate Change 2007"),
    ReferenceRule("R11", 18, "4606", "KNMI", "2006", "Climate in the 21st century", "used", "KNMI: Climate in the 21st"),
    ReferenceRule("R12", 18, "4606", "Leander, R. and Buishand, T. A.", "2007", "Resampling of regional climate model output", "used", "Leander, R. and Buishand"),
    ReferenceRule("R13", 18, "4606", "Leander, R., Buishand, T., van den Hurk, B., and de Wit, M.", "2008", "Estimated changes in flood quantiles", "used", "Leander, R., Buishand"),
    ReferenceRule("R14", 18, "4606", "Lenderink, G., Hurk van den, B., Meijgaard van, E., Ulden van, A., and Cuijpers, H.", "2003", "Simulation of present-day climate in RACMO 2", "used", "Lenderink, G., Hurk van den"),
    ReferenceRule("R15", 18, "4606", "Lorenz, P. and Jacob, D.", "2008", "Validation of temperature trends in the ENSEMBLES RCM runs", "used", "Lorenz, P. and Jacob"),
    ReferenceRule("R16", 18, "4606", "Pfister, L., Kwadijk, J., Musy, A., Bronstert, A., and Hoffmann, L.", "2004", "Climate change, land use change and runoff prediction", "used", "Pfister, L., Kwadijk"),
    ReferenceRule("R17", 18, "4606-4607", "Roeckner, E., Bäuml, G., Bonaventura, L., Brokopf, R., Esch, M., Giorgetta, M., Hagemann, S., Kirchner, I., Kornblueh, L., Manzine, E., Rhodin, A., Schlese, U., Schulzweida, U., and Tompkins, A.", "2003", "The atmospheric general circulation model ECHAM 5", "used", "Roeckner, E."),
    ReferenceRule("R18", 19, "4607", "Swedish Meteorological and Hydrological Institute (SMHI)", "2007", "The HBV model", "listed-only", "Swedish Meteorological and Hydrological Institute (SMHI)"),
    ReferenceRule("R19", 19, "4607", "Smits, I., Wijngaarden, J., Versteeg, R. and Kok, M.", "2004", "Statistiek van extreme neerslag in Nederland", "candidate-author-conflict", "Smits, I., Wijngaarden"),
    ReferenceRule("R20", 19, "4607", "Tu, M., Hall, M. J., Laat de, P. J., and Wit de, M. J. M.", "2005a", "Extreme floods in the Meuse river", "used", "Tu, M., Hall, M. J."),
    ReferenceRule("R21", 19, "4607", "Tu, M., Laat de, P. J. M., Hall, M. J., and Wit de, M. J. M.", "2005b", "Precipitation variability in the Meuse basin", "used", "Tu, M., Laat de"),
    ReferenceRule("R22", 19, "4607", "Uijlenhoet, R., Wit de, M. J. M., Warmerdam, P. M. M., and Torfs, P. J. J. F.", "2001", "Statistical analysis of daily discharge data", "used", "Uijlenhoet, R."),
    ReferenceRule("R23", 19, "4607", "Van Schrojenstein Lantman, J.", "2004", "Hoogwatervoorspellingen op de Maas", "used", "Van Schrojenstein Lantman, J."),
    ReferenceRule("R24", 19, "4607", "Warmerdam, P. M. M. and Wit de, M. J. M.", "2001", "Climate change and low flows in the river Meuse", "used", "Warmerdam, P. M. M."),
    ReferenceRule("R25", 19, "4607", "Wit de, M. J. M.", "2001a", "Effect of climate change on the hydrology of the river Meuse", "used", "Wit de, M. J. M.: Effect of climate change"),
    ReferenceRule("R26", 19, "4607", "Wit de, M. J. M., Buiteveld, H., and Deursen van, W. P. A.", "2007b", "Klimaatverandering en de afvoer van Rijn en Maas", "used", "Wit de, M. J. M., Buiteveld"),
    ReferenceRule("R27", 19, "4607", "Wit de, M. J. M., Uijlenhoet, R., Warmerdam, P. M. M., Torfs, P. J. J. F., Roulin, E., and Dewil, P.", "2001b", "Statistical analysis of discharge time series", "used", "Wit de, M. J. M., Uijlenhoet"),
    ReferenceRule("R28", 19, "4607", "Wit de, M. J. M., Hurk van den, B., Warmerdam, P. M. M., Torfs, P. J. J. F., Roulin, E., and Deursen van, W. P. A.", "2007a", "Impact of climate change on low-flows in the river Meuse", "used", "Wit de, M. J. M., Hurk van den"),
)


PATCH_RULES = (
    PatchRule("P01", "F07", "occurrence O33, 1994 component; physical p. 7 / printed p. 4595", "Bergstrom et al., 1994", "Bergstrom and Carlsson, 1994", "R06", "The matched record has exactly two authors; retain the enclosing parenthetical group."),
    PatchRule("P02", "F08", "occurrence O19, Warmerdam component; physical p. 5 / printed p. 4593", "Warmerdam et al., 2001", "Warmerdam and de Wit, 2001", "R24", "The matched record has exactly two authors; retain the enclosing parenthetical group."),
    PatchRule("P03", "F09", "occurrence O20; physical p. 5 / printed p. 4593", "(Lorenz et al., 2008)", "(Lorenz and Jacob, 2008)", "R15", "The matched record has exactly two authors and the occurrence is parenthetical."),
    PatchRule("P04", "F10", "occurrence O21, 2007 component; physical p. 5 / printed p. 4593", "Leander et al., 2007", "Leander and Buishand, 2007", "R12", "The 2007 record has exactly two authors; retain the enclosing parenthetical group."),
    PatchRule("P05", "F10", "occurrence O23; physical p. 5 / printed p. 4593", "(Leander et al., 2007)", "(Leander and Buishand, 2007)", "R12", "The 2007 record has exactly two authors and the occurrence is parenthetical."),
    PatchRule("P06", "F10", "occurrence O24; physical p. 5 / printed p. 4593", "(Leander et al., 2007)", "(Leander and Buishand, 2007)", "R12", "The 2007 record has exactly two authors and the occurrence is parenthetical."),
    PatchRule("P07", "F10", "occurrence O30; physical p. 7 / printed p. 4595", "Leander et al. (2007)", "Leander and Buishand (2007)", "R12", "The 2007 record has exactly two authors."),
    PatchRule("P08", "F10", "occurrence O31; physical p. 7 / printed p. 4595", "(Leander et al., 2007)", "(Leander and Buishand, 2007)", "R12", "The 2007 record has exactly two authors and the occurrence is parenthetical."),
    PatchRule("P09", "F10", "occurrence O35; physical p. 8 / printed p. 4596", "(Leander et al., 2007)", "(Leander and Buishand, 2007)", "R12", "The 2007 record has exactly two authors and the occurrence is parenthetical."),
    PatchRule("P10", "F10", "occurrence O38; physical p. 9 / printed p. 4597", "(Leander et al., 2007)", "(Leander and Buishand, 2007)", "R12", "The 2007 record has exactly two authors and the occurrence is parenthetical."),
    PatchRule("P11", "F10", "occurrence O40; physical p. 10 / printed p. 4598", "(Leander et al., 2007)", "(Leander and Buishand, 2007)", "R12", "The 2007 record has exactly two authors and the occurrence is parenthetical."),
    PatchRule("P12", "F10", "occurrence O42, 2007 component; physical p. 15 / printed p. 4603", "Leander et al., 2007", "Leander and Buishand, 2007", "R12", "The 2007 record has exactly two authors; retain the enclosing parenthetical group."),
    PatchRule("P13", "F11", "occurrence O11, 2001a component; physical p. 4 / printed p. 4592", "Wit de et al., 2001a", "de Wit, 2001a", "R25", "The 2001a record credits one author; retain the enclosing parenthetical group."),
    PatchRule("P14", "F11", "occurrence O44, compact Wit de component; physical p. 16 / printed p. 4604", "Wit de et al., 2001a, 2007b", "de Wit, 2001a; de Wit et al., 2007b", "R25; R26", "Split the inherited years because the 2001a and 2007b records have different author cardinalities."),
    PatchRule("P15", "F12", "occurrence O13; physical p. 4 / printed p. 4592", "De Wit (2001)", "De Wit (2001a)", "R25", "The only matching record carries suffix 2001a."),
    PatchRule("P16", "F13", "occurrence O17; physical p. 4 / printed p. 4592", "De Wit (2007a)", "De Wit et al. (2007a)", "R28", "The 2007a record has multiple credited authors."),
    PatchRule("P17", "F14", "occurrence O47; physical p. 16 / printed p. 4604", "De Wit (2007b)", "De Wit et al. (2007b)", "R26", "The 2007b record has three credited authors."),
    PatchRule("P18", "F16", "occurrence O39, 2007 atomic component; physical p. 10 / printed p. 4598", "Leander (2007, 2008)", "Leander and Buishand (2007)", "R12", "When the compact narrative is split, the 2007 component takes the two credited authors."),
    PatchRule("P19", "F17", "occurrence O39, 2008 atomic component; physical p. 10 / printed p. 4598", "Leander (2007, 2008)", "Leander et al. (2008)", "R13", "When the compact narrative is split, the 2008 component takes the four-author callout form."),
)


# Date-like strings in prose, tables, captions, and publication furniture that
# must not be mistaken for author-year callouts. Rows are grouped only when the
# same expression has one local meaning on one page.
EXCLUSION_RULES = (
    ExclusionRule("E01", 1, "4589", "2009", "journal masthead and article metadata", "Publication metadata, not a source callout."),
    ExclusionRule("E02", 1, "4589", "Received: 3 June 2009", "received/accepted/published line", "Editorial history dates, not citations."),
    ExclusionRule("E03", 3, "4591", "1911-2002", "long observation records for the Meuse basin", "Study-period range without an author expression."),
    ExclusionRule("E04", 3, "4591", "1980", "precipitation amounts have significantly increased since 1980", "Measurement period, not a bibliographic year."),
    ExclusionRule("E05", 4, "4592", "21st century", "continue during the 21st century", "Ordinal time phrase, not a four-digit citation year."),
    ExclusionRule("E06", 5, "4593", "1950-2100", "transient simulation of the GCM ECHAM 5", "Simulation horizon, not an author-year construction."),
    ExclusionRule("E07", 5, "4593", "1950-2000", "observed greenhouse gases for 1950-2000", "Input-data period, not a citation."),
    ExclusionRule("E08", 8, "4596", "1951-2100", "model is run for the period 1951-2100", "Model run period, not a source callout."),
    ExclusionRule("E09", 9, "4597", "1969-1998", "control period and observational records", "Control/observation period, not a citation."),
    ExclusionRule("E10", 10, "4598", "1969-1998", "calendar month m in the period 1969-1998", "Calibration period, not a citation."),
    ExclusionRule("E11", 11, "4599", "1969-1998", "averages for the period 1969-1998", "Comparison period, not a citation."),
    ExclusionRule("E12", 13, "4601", "2071-2100", "RACMO2 scenario period 2071-2100", "Scenario period, not a citation."),
    ExclusionRule("E13", 14, "4602", "1969-1998", "control period 1969-1998", "Table/control period, not a citation."),
    ExclusionRule("E14", 14, "4602", "1969-1998", "annual mean control-period sentence in the Table 3 discussion", "Control period, not a citation."),
    ExclusionRule("E15", 16, "4604", "1985-1998", "deviations in the HBV model for the 1985-1998 record", "Data-record period, not a citation."),
    ExclusionRule("E16", 16, "4604", "1969-1998", "observed/control-period comparison before the KNMI callout", "Comparison period, not a citation."),
    ExclusionRule("E17", 17, "4605", "1969-1998", "bias corrections are developed using data from the period 1969-1998", "Calibration period, not a citation."),
    ExclusionRule("E18", 17, "4605", "1951-2100", "applied on the whole RACMO2 run of 1951-2100", "Model run period, not a citation."),
    ExclusionRule("E19", 17, "4605", "1998-2100", "assumption is made for the period 1998-2100", "Projection period, not a citation."),
    ExclusionRule("E20", 20, "4608", "1969-1998", "Table 1 statistics over period 1969-1998", "Table period, not a citation."),
    ExclusionRule("E21", 21, "4609", "1969-1998", "Table 2 observed and column-label period", "Table period, not a citation."),
    ExclusionRule("E22", 22, "4610", "1969-1998", "Table 3 control-period column labels", "Table period, not a citation."),
    ExclusionRule("E23", 22, "4610", "2071-2100", "Table 3 scenario-period column labels", "Table period, not a citation."),
    ExclusionRule("E24", 22, "4610", "2069", "Table 3 maximal-discharge value", "Numeric model output, not a year or citation."),
    ExclusionRule("E25", 23, "4611", "2009", "representative recurring article header on physical pp. 2-30", "Recurring publication furniture, not a source callout."),
    ExclusionRule("E26", 24, "4612", "1969-1998", "Fig. 2 control period", "Figure caption period, not a citation."),
    ExclusionRule("E27", 25, "4613", "1969-1998", "Fig. 3 temperature-bias period", "Figure caption period, not a citation."),
    ExclusionRule("E28", 26, "4614", "1969-1998", "Fig. 4 relative-bias period", "Figure caption period, not a citation."),
    ExclusionRule("E29", 27, "4615", "1969-1998", "Fig. 5 ten-day precipitation period", "Figure caption period, not a citation."),
    ExclusionRule("E30", 28, "4616", "1969-1998", "Fig. 6 observed control-period series", "Figure data period, not a citation."),
    ExclusionRule("E31", 28, "4616", "2071-2100", "Fig. 6 scenario period", "Figure caption period, not a citation."),
    ExclusionRule("E32", 29, "4617", "1969-1998", "Fig. 7 control period", "Figure caption period, not a citation."),
    ExclusionRule("E33", 29, "4617", "2071-2100", "Fig. 7 scenario period", "Figure caption period, not a citation."),
    ExclusionRule("E34", 30, "4618", "1969-1998", "Fig. 8 control period", "Figure data period, not a citation."),
    ExclusionRule("E35", 30, "4618", "2071-2100", "Fig. 8 scenario-run labels", "Figure data period, not a citation."),
)


# Collision rows force the audit to preserve suffix and inherited-year logic
# instead of reducing the manuscript to a flat set of author-year strings.
COLLISION_RULES = (
    CollisionRule("K01", "Tu 2005", "(Tu et al., 2005a); (Tu et al., 2005b)", "R20; R21", "explicit suffixes", "resolved as two records", "The two suffixes are printed on separate body callouts and on separate end records.", ((3, "Tu et al., 2005b"), (4, "demonstrated statistically (Tu et"), (19, "Tu, M."))),
    CollisionRule("K02", "Wit de 2001", "(Wit de et al., 2001a); (Wit de et al., 2001b); De Wit (2001)", "R25; R27", "explicit and missing suffix", "2001a/2001b are distinct; the unsuffixed occurrence resolves to R25 from its single-author form and climate-impact context", "The source uses singular De Wit in the climate-impact statement, matching the single-author 2001a record; the separate multi-author 2001b record remains distinct.", ((4, "De Wit (2001)"), (19, "2001a"), (19, "2001b"))),
    CollisionRule("K03", "Wit de 2007", "Wit de et al. (2007a); Wit de et al. (2007b); De Wit (2007)", "R26; R28", "explicit and missing suffix", "2007a/2007b are distinct; unsuffixed form is ambiguous", "Both suffixes occur in the reference list and the body, but the p. 4605 unsuffixed callout does not identify one of them.", ((16, "2007b"), (17, "De Wit (2007)"), (19, "2007a"))),
    CollisionRule("K04", "Leander 2007/2008", "Leander (2007, 2008)", "R12; R13", "inherited within a compact group", "split required", "The compact narrative carries two years over one author token even though the two records have different author cardinalities.", ((10, "Leander (2007, 2008)"), (18, "Leander, R. and Buishand"))),
    CollisionRule("K05", "Leander 2005/2007/2008", "Leander et al. (2005); Leander et al. (2007); Leander et al. (2008)", "R12; R13; none for 2005", "explicit years", "2005 is cited-only; 2007 is a two-author form defect; 2008 is linked", "The same first author spans a missing year and two listed years, so first-author matching alone is insufficient.", ((16, "Leander et al. 2005"), (18, "Leander, R. and Buishand"))),
    CollisionRule("K06", "Van den Hurk 2005/2006", "Van den Hurk et al, 2005; Hurk van den et al. (2006)", "R09; none for 2005", "explicit years", "2005 is cited-only; 2006 is linked", "The body distinguishes the PRUDENCE 2005 callout from the listed 2006 scenario record.", ((6, "Van den Hurk et al, 2005"), (18, "Hurk van den, B."))),
    CollisionRule("K07", "Bergstrom 1994/1995/2001", "Bergström et al., 1994; Bergström, 1995; Bergstrom et al., 2001", "R04; R05; R06", "explicit years", "three distinct records", "The shared surname is paired with three different years and listed records; only 1994 has an author-cardinality defect.", ((4, "Bergstrom et al., 2001"), (7, "Bergstrom et al., 1994"), (18, "Bergström, S. and Carlsson"))),
    CollisionRule("K08", "Booij 2002/2005", "(Booij, 2002b); (Booij, 2005)", "R07; R08", "explicit suffix/year", "two distinct records", "The 2002b suffix and 2005 year resolve to separate listed titles; the visible 2002b pair is a clearance.", ((3, "Booij, 2002b"), (8, "Booij, 2005"), (18, "2002b"))),
    CollisionRule("K09", "Bergstrom/Forsman 1973", "Bergström and Forsman, 1973", "none", "explicit year", "cited-only; author query", "A shared Bergström surname in later records does not supply the absent Forsman coauthor or 1973 record.", ((4, "Bergstrom and Forsman, 1973"), (18, "Bergstrom, S."))),
    CollisionRule("K10", "SMHI 2007", "undated SMHI body mention", "R18", "year absent in body", "listed-only; author/editor query", "The body names SMHI without a formal 2007 callout, while the end list contains an institutional 2007 record.", ((7, "Swedish Meteorological and Hydrological Institute (SMHI)"), (19, "Swedish Meteorological and Hydrological Institute (SMHI)"))),
)


ACTION_RULES = (
    ActionRule("A01", "F01", "author", "author supplies the missing 1973 record or confirms removal/replacement", "hold"),
    ActionRule("A02", "F02", "author", "author confirms the 2005 source or supplies a replacement", "hold"),
    ActionRule("A03", "F03", "author", "author supplies or replaces the Jacob 2007 source", "hold"),
    ActionRule("A04", "F04", "author", "author supplies or replaces both Leander 2005 occurrences", "hold"),
    ActionRule("A05", "F05", "editor", "editor and author decide whether the listed SMHI record supports a claim", "hold"),
    ActionRule("A06", "F06", "author", "author confirms whether STOWA or Smits et al. is the credited author", "hold"),
    ActionRule("A07", "F07", "copyeditor", "matched R06 is retained as the intended work", "confirmed"),
    ActionRule("A08", "F08", "copyeditor", "matched R24 is retained as the intended work", "confirmed"),
    ActionRule("A09", "F09", "copyeditor", "matched R15 is retained as the intended work", "confirmed"),
    ActionRule("A10", "F10", "copyeditor", "matched R12 is retained and every 2007 occurrence is patched", "confirmed"),
    ActionRule("A11", "F11", "copyeditor", "matched single-author R25 is retained and grouped components are split", "confirmed"),
    ActionRule("A12", "F12", "copyeditor", "matched R25 and its 2001a suffix are retained", "confirmed"),
    ActionRule("A13", "F13", "copyeditor", "matched multi-author R28 is retained", "confirmed"),
    ActionRule("A14", "F14", "copyeditor", "matched multi-author R26 is retained", "confirmed"),
    ActionRule("A15", "F15", "author", "author identifies which supplied or missing 2007 work is intended", "hold"),
    ActionRule("A16", "F16", "copyeditor", "author-year components are separated and R12 is retained", "confirmed"),
    ActionRule("A17", "F17", "copyeditor", "author-year components are separated and R13 is retained", "confirmed"),
)


def occurrence_form(row: OccurrenceRule) -> str:
    if len(row.components) > 1 and ";" in row.observed:
        return "grouped"
    if len(row.components) > 1:
        return "compact"
    return "parenthetical" if row.observed.lstrip().startswith("(") else "narrative"


def occurrence_explicitness(row: OccurrenceRule) -> str:
    return row.explicitness


def reference_cardinality(row: ReferenceRule) -> str:
    head = row.head.casefold()
    if "others" in head:
        return "multiple"
    # The handoff only needs the supplied record's one/two/multiple class.
    # A comma-rich author head contains more than two explicit authors even
    # when the final separator is a single ``and``.
    if "," not in head:
        return "1"
    if " and " not in head:
        return "1" if head.count(",") <= 1 else "multiple"
    return "multiple" if head.count(",") >= 3 or head.count(" and ") > 1 else "2"


def reference_owner(row: ReferenceRule) -> str:
    if row.status in {"listed-only", "candidate-author-conflict"}:
        return "author/editor"
    if row.status == "used":
        return "copyeditor"
    return "editor"


def comparison_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("\u00ad", "").replace("–", "-").replace("—", "-").replace("−", "-")
    return re.sub(r"\s+", " ", value).strip()


def extract_pages(pdf: Path) -> dict[int, str]:
    with tempfile.TemporaryDirectory(prefix="citation-reconciliation-") as temporary:
        base = Path(temporary)
        pages: dict[int, str] = {}
        for page in range(1, 31):
            target = base / f"page-{page:03d}.txt"
            subprocess.run(
                ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), str(target)],
                check=True,
                capture_output=True,
            )
            pages[page] = target.read_text(encoding="utf-8")
        return pages


def verify_rules(pages: dict[int, str]) -> None:
    normalized = {page: comparison_text(text) for page, text in pages.items()}
    reference_text = "\n".join(normalized[page] for page in (17, 18, 19))
    page_17_body = normalized[17].split(" aalders, p.", 1)[0]
    body_text = "\n".join(normalized[page] for page in range(1, 17)) + "\n" + page_17_body

    def require_unique_keys(label: str, rows: tuple[object, ...]) -> None:
        keys = [getattr(row, "key") for row in rows]
        if len(keys) != len(set(keys)):
            raise RuntimeError(f"Duplicate {label} key")

    require_unique_keys("finding", FINDING_RULES)
    require_unique_keys("clearance", CLEARED_RULES)
    require_unique_keys("occurrence", OCCURRENCE_RULES)
    require_unique_keys("reference", REFERENCE_RULES)
    require_unique_keys("patch", PATCH_RULES)
    require_unique_keys("exclusion", EXCLUSION_RULES)
    require_unique_keys("collision", COLLISION_RULES)
    require_unique_keys("action", ACTION_RULES)

    for rule in FINDING_RULES:
        for page, anchor in rule.required_anchors:
            if comparison_text(anchor) not in normalized[page]:
                raise RuntimeError(f"Source anchor failed for {rule.key} on physical page {page}: {anchor}")
        if rule.absent_from_references and re.search(rule.absent_from_references, reference_text, flags=re.MULTILINE):
            raise RuntimeError(f"Expected reference-list absence failed for {rule.key}")
        if rule.absent_from_body and re.search(rule.absent_from_body, body_text, flags=re.MULTILINE):
            raise RuntimeError(f"Expected body absence failed for {rule.key}")

    for rule in CLEARED_RULES:
        for page, anchor in rule.required_anchors:
            if comparison_text(anchor) not in normalized[page]:
                raise RuntimeError(f"Source anchor failed for {rule.key} on physical page {page}: {anchor}")

    occurrence_by_key = {rule.key: rule for rule in OCCURRENCE_RULES}
    reference_keys = {rule.key for rule in REFERENCE_RULES}
    finding_by_key = {rule.key: rule for rule in FINDING_RULES}

    for rule in OCCURRENCE_RULES:
        if comparison_text(rule.anchor) not in normalized[rule.physical_page]:
            raise RuntimeError(
                f"Source anchor failed for {rule.key} on physical page {rule.physical_page}: {rule.anchor}"
            )
        for record in rule.mapping.split("; "):
            if record != "none" and record not in reference_keys:
                raise RuntimeError(f"Unknown reference mapping {record} in {rule.key}")

    for rule in REFERENCE_RULES:
        if comparison_text(rule.anchor) not in normalized[rule.physical_page]:
            raise RuntimeError(
                f"Source anchor failed for {rule.key} on physical page {rule.physical_page}: {rule.anchor}"
            )

    for rule in COLLISION_RULES:
        for page, anchor in rule.required_anchors:
            if comparison_text(anchor) not in normalized[page]:
                raise RuntimeError(f"Source anchor failed for {rule.key} on physical page {page}: {anchor}")

    patch_signatures: set[tuple[str, str, str]] = set()
    patched_findings: set[str] = set()
    for rule in PATCH_RULES:
        occurrence_match = re.search(r"\b(O\d+)\b", rule.location)
        if not occurrence_match or occurrence_match.group(1) not in occurrence_by_key:
            raise RuntimeError(f"Patch {rule.key} has no valid occurrence location")
        occurrence = occurrence_by_key[occurrence_match.group(1)]
        if comparison_text(rule.current) not in comparison_text(occurrence.observed):
            raise RuntimeError(f"Patch {rule.key} current form is not present in {occurrence.key}")
        finding_keys = set(re.findall(r"\bF\d+\b", rule.finding))
        record_keys = set(re.findall(r"\bR\d+\b", rule.record))
        if not finding_keys or not finding_keys.issubset(finding_by_key):
            raise RuntimeError(f"Patch {rule.key} has an unknown finding")
        if not record_keys or not record_keys.issubset(reference_keys):
            raise RuntimeError(f"Patch {rule.key} has an unknown governing record")
        if any(finding_by_key[key].state != "Confirmed discrepancy" for key in finding_keys):
            raise RuntimeError(f"Patch {rule.key} attempts to repair an unresolved author decision")
        signature = (
            occurrence.key,
            comparison_text(rule.current),
            comparison_text(rule.proposed),
        )
        if signature in patch_signatures:
            raise RuntimeError(f"Duplicate physical repair in {rule.key}")
        patch_signatures.add(signature)
        patched_findings.update(finding_keys)

    confirmed_findings = {
        rule.key for rule in FINDING_RULES if rule.state == "Confirmed discrepancy"
    }
    if patched_findings != confirmed_findings:
        raise RuntimeError("Confirmed findings and repair-patch findings do not close")

    action_findings = [rule.finding for rule in ACTION_RULES]
    if set(action_findings) != set(finding_by_key) or len(action_findings) != len(set(action_findings)):
        raise RuntimeError("Action ownership does not cover each finding exactly once")

    for rule in EXCLUSION_RULES:
        if comparison_text(rule.token) not in normalized[rule.physical_page]:
            raise RuntimeError(
                f"Source anchor failed for {rule.key} on physical page {rule.physical_page}: {rule.token}"
            )


def _control_totals() -> dict[str, int]:
    """Compute release-control totals from the anchored ledger rules."""
    components: list[str] = []
    mapped_records: set[str] = set()
    cited_only = 0
    for row in OCCURRENCE_RULES:
        mappings = row.mapping.split("; ")
        # Most rows align one mapping token to each component. A single
        # ambiguous component may intentionally carry two candidate records.
        if len(mappings) != len(row.components) and len(row.components) != 1:
            raise RuntimeError(f"Occurrence mapping width failed for {row.key}")
        components.extend(row.components)
        for mapping in mappings:
            if mapping == "none":
                cited_only += 1
            elif mapping != "none":
                mapped_records.add(mapping)

    def comparison_key(value: str) -> str:
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", value.casefold()).strip()

    return {
        "body_occurrence_groups": len(OCCURRENCE_RULES),
        "atomic_body_components": len(components),
        "distinct_source_form_identities": len({comparison_key(item) for item in components}),
        "end_reference_records": len(REFERENCE_RULES),
        "records_with_candidate_links": len(mapped_records),
        "cited_only_atomic_components": cited_only,
        "listed_only_records": sum(item.status == "listed-only" for item in REFERENCE_RULES),
        "confirmed_patch_rows": len(PATCH_RULES),
        "noncitation_date_exclusion_groups": len(EXCLUSION_RULES),
        "collision_register_rows": len(COLLISION_RULES),
        "action_ownership_rows": len(ACTION_RULES),
        "confirmed_copyeditor_actions": sum(item.owner == "copyeditor" for item in ACTION_RULES),
        "author_or_editor_holds": sum(item.owner in {"author", "editor"} for item in ACTION_RULES),
    }


def render_report(pdf: Path) -> str:
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError("The supplied manuscript does not match the frozen audit source")

    pages = extract_pages(pdf)
    verify_rules(pages)
    confirmed = sum(rule.state == "Confirmed discrepancy" for rule in FINDING_RULES)
    queries = len(FINDING_RULES) - confirmed

    totals = _control_totals()
    reverse_map: dict[str, list[str]] = {rule.key: [] for rule in REFERENCE_RULES}
    for occurrence in OCCURRENCE_RULES:
        for record in occurrence.mapping.split("; "):
            if record in reverse_map and occurrence.key not in reverse_map[record]:
                reverse_map[record].append(occurrence.key)

    lines = [
        "# Citation-Reconciliation Report",
        "",
        "## Editorial decision",
        "",
        "**Not reference-ready.** The manuscript has unresolved cited-only records and author-identity decisions that require author input. Copyediting can apply the confirmed callout-form repairs, but the reference list should not be released until the queries are closed.",
        "",
        "## Scope and result",
        "",
        "The audit covers formal author-date callouts in active manuscript text through the acknowledgements and every record under the end References heading. Running navigation text, affiliation dates, study periods, and undated acknowledgements were excluded as callouts. The two inventories were reconciled in both directions.",
        "",
        f"Result: {len(FINDING_RULES)} independently actionable findings ({confirmed} confirmed discrepancies; {queries} author decisions) and {len(CLEARED_RULES)} documented near-match clearances.",
        "",
        "## Non-citation date exclusion register",
        "",
        "Every date-like expression reviewed during the citation scan is retained here when it could be mistaken for an author-year callout. Grouping is limited to one page-local expression and keeps the exact source token separate from the classification reason.",
        "",
        "| Exclusion | Physical page | Printed page | Exact date-like text | Local context | Why excluded |",
        "|---|---:|---:|---|---|---|",
    ]
    for exclusion in EXCLUSION_RULES:
        lines.append(
            f"| {exclusion.key} | {exclusion.physical_page} | {exclusion.printed_page} | {exclusion.token} | {exclusion.context} | {exclusion.reason} |"
        )

    lines.extend(
        [
        "",
        "## Control totals",
        "",
        "The following totals are release controls for the two closed ledgers. Repeated body uses remain separate occurrence groups; atomic components may point to the same end record.",
        "",
        f"- Body occurrence groups: **{totals['body_occurrence_groups']}**",
        f"- Atomic author-year components: **{totals['atomic_body_components']}**",
        f"- Distinct source-form author-year/suffix identities: **{totals['distinct_source_form_identities']}** (a transcription control; particle/order variants are preserved here rather than deduplicated as people or works)",
        f"- End-reference records: **{totals['end_reference_records']}**",
        f"- Records with one or more candidate links: **{totals['records_with_candidate_links']}**",
        f"- Cited-only atomic components: **{totals['cited_only_atomic_components']}**",
        f"- Listed-only records: **{totals['listed_only_records']}**",
        f"- Confirmed patch rows: **{totals['confirmed_patch_rows']}**",
        f"- Non-citation date exclusion groups: **{totals['noncitation_date_exclusion_groups']}**",
        f"- Collision-register rows: **{totals['collision_register_rows']}**",
        f"- Action-ownership rows: **{totals['action_ownership_rows']}**",
        f"- Confirmed copyeditor actions: **{totals['confirmed_copyeditor_actions']}**",
        f"- Author/editor hold actions: **{totals['author_or_editor_holds']}**",
        "",
        "## Body-citation occurrence ledger",
        "",
        "Every visible formal callout group has its own row. The atomic components and mapping column preserve grouped, repeated, compact, and unresolved uses.",
        "",
            "| Occurrence | Physical page | Printed page | Exact callout group | Atomic components | Citation form | Author/year explicitness | Status | Candidate record(s) |",
            "|---|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for row in OCCURRENCE_RULES:
        lines.append(
            f"| {row.key} | {row.physical_page} | {row.printed_page} | {row.observed} | "
            f"{'; '.join(row.components)} | {occurrence_form(row)} | {occurrence_explicitness(row)} | {row.status} | {row.mapping} |"
        )

    lines.extend(
        [
            "",
            "## Bidirectional mapping control",
            "",
            "The reverse view is checked against the occurrence ledger. `none` is an explicit absence, not an omitted row.",
            "",
            "| Reference | Occurrence row(s) | Reference status |",
            "|---|---|---|",
        ]
    )
    for row in REFERENCE_RULES:
        occurrence_ids = ", ".join(reverse_map[row.key]) if reverse_map[row.key] else "none"
        lines.append(f"| {row.key} | {occurrence_ids} | {row.status} |")

    lines.extend(
        [
            "",
            "## Collision and inheritance register",
            "",
            "Rows are retained for author-year stems that collide, inherit a year inside a compact construction, or require a suffix/absence decision. The state is the audit result, not a claim about material outside the manuscript.",
            "",
            "| Collision | Author-year stem | Body component(s) | Candidate record(s) | Suffix/explicitness | Resulting state | Evidence |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in COLLISION_RULES:
        lines.append(
            f"| {row.key} | {row.stem} | {row.body_components} | {row.candidate_records} | {row.explicitness} | {row.state} | {row.evidence} |"
        )

    lines.extend(
        [
            "",
            "## End-reference ledger",
            "",
            "Each visible record under the References heading is retained, including records with no formal callout or an unresolved author candidate.",
            "",
            "| Record | Physical page | Printed page | Reference head | Year/suffix | Credited-author cardinality | Title anchor | Status | Follow-up owner |",
            "|---|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for row in REFERENCE_RULES:
        lines.append(
            f"| {row.key} | {row.physical_page} | {row.printed_page} | {row.head} | {row.year} | {reference_cardinality(row)} | {row.title} | {row.status} | {reference_owner(row)} |"
        )

    lines.extend([
        "",
        "Record R17 starts on printed p. 4606 and continues onto printed p. 4607; its complete author string and title are retained as one record.",
        "Occurrence O23 is the p. 4593 earlier-studies sentence (lines 6-8), while O24 is the later large-quantiles sentence (lines 14-16). These repeated source strings are separate production locations.",
    ])

    lines.extend(
        [
            "",
        "## Findings",
        "",
        ]
    )
    for rule in FINDING_RULES:
        lines.extend(
            [
                f"### {rule.key} - {rule.state}",
                "",
                f"- Category: {rule.category}",
                f"- Location: {rule.location}",
                f"- Observed item: `{rule.observed}`",
                f"- Counterpart: {rule.counterpart}",
                f"- Manuscript evidence: {rule.evidence}",
                f"- Recommended disposition: {rule.disposition}",
                "",
            ]
        )

    lines.extend(["## Confirmed repair patch register", ""])
    lines.extend(
        [
            "Only confirmed, manuscript-supported repairs appear here. Items requiring author input remain in the findings and are not silently converted into patches.",
            "",
            "| Patch | Finding | Location | Current form | Proposed form | Governing record | Evidence reason |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for patch in PATCH_RULES:
        lines.append(
            f"| {patch.key} | {patch.finding} | {patch.location} | {patch.current} | {patch.proposed} | {patch.record} | {patch.evidence} |"
        )

    lines.extend([
        "",
        "P18 and P19 are one joint edit at O39: replace the compact source string with `Leander and Buishand (2007) and Leander et al. (2008)`. Execute both atomic rows together; neither row is a standalone partial replacement.",
    ])

    lines.extend(
        [
            "",
            "## Action-ownership matrix",
            "",
            "Every finding has an owner and an execution precondition. A hold is not a confirmed repair and must remain open until its stated input is available.",
            "",
            "| Action | Finding | Owner | Precondition | State |",
            "|---|---|---|---|---|",
        ]
    )
    for row in ACTION_RULES:
        lines.append(f"| {row.key} | {row.finding} | {row.owner} | {row.precondition} | {row.state} |")

    lines.extend(["", "## Cleared near matches", ""])
    for rule in CLEARED_RULES:
        lines.extend(
            [
                f"### {rule.key} - Cleared; no identity repair",
                "",
                f"- Compared forms: `{rule.forms}`",
                f"- Location: {rule.location}",
                f"- Decision: {rule.reason}",
                "",
            ]
        )

    lines.extend(
        [
            "## Handoff",
            "",
            "Author input is required for the four missing end records, the uncited institutional record, the organization-versus-personal-author conflict, and the unsuffixed 2007 callout. After those decisions, apply the confirmed minimal callout repairs and repeat both cited-to-listed and listed-to-cited checks. No missing title, coauthor list, or publication field has been invented in this report.",
            "",
        ]
    )
    return "\n".join(lines)


def locate_pdf(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    container = Path("/workspace/materials/hydrology_manuscript.pdf")
    if container.is_file():
        return container
    return Path(__file__).resolve().parents[1] / "environment/workspace/materials/hydrology_manuscript.pdf"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path("/workspace/output/citation_reconciliation.md"))
    args = parser.parse_args()

    pdf = locate_pdf(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(pdf), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

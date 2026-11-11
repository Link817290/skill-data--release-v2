#!/usr/bin/env python3
"""Build the reference disclosure review from the supplied filing materials."""

from __future__ import annotations

import argparse
import csv
import math
import re
import unicodedata
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from pathlib import Path


class SourceText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def normalized_html(path: Path) -> str:
    parser = SourceText()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    text = unicodedata.normalize("NFKD", " ".join(parser.parts))
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip()


def require(text: str, fragment: str, source: str) -> None:
    if fragment not in text:
        raise RuntimeError(f"bound source passage is missing from {source}: {fragment[:80]}")


@dataclass(frozen=True)
class Matter:
    review_id: str
    disposition: str
    statement: str
    evidence: str
    analysis: str
    proposed_action: str


def build_matters(materials: Path) -> list[Matter]:
    names = {
        "annual": "annual_report.html",
        "release": "earnings_release.html",
        "egypt": "engineer_egypt.html",
        "gabon": "engineer_gabon.html",
        "cdi": "engineer_cote_divoire.html",
        "canada": "engineer_canada.html",
    }
    text = {key: normalized_html(materials / name) for key, name in names.items()}

    # Bind every expert conclusion to distinctive passages in the supplied documents.
    require(text["annual"],
            "Beginning proved undeveloped reserves at December 31, 2023 6,193 "
            "Undeveloped reserves converted to developed reserves (56) Acquisitions "
            "15,670 Revisions 2,698 Extensions and discoveries (377) Ending proved "
            "undeveloped reserves at December 31, 2024 24,128", names["annual"])
    require(text["annual"],
            "Extensions and discoveries of 0.4 MMBoe are primarily due to our Canada "
            "segment", names["annual"])
    require(text["annual"],
            "Extensions and discoveries (93) (93) Revisions of previous estimates "
            "4,782 1,441 (225) 1,018 7,016", names["annual"])
    require(text["annual"],
            "Extensions and discoveries 234 234 Revisions of previous estimates 446 "
            "(253) 193", names["annual"])
    require(text["annual"],
            "Extensions and discoveries 40 40 Revisions of previous estimates 170 170",
            names["annual"])
    require(text["annual"],
            "Purchase of reserves Extensions and discoveries 93 810 903 Revisions of "
            "previous estimates 2,042 4,693 (652) 6,083", names["annual"])
    require(text["annual"],
            "Extensions and discoveries 3,219 3,219 Revisions of previous estimates "
            "(1,298) (1,298)", names["annual"])
    require(text["annual"],
            "Purchase of reserves Extensions and discoveries 505 505 Revisions of "
            "previous estimates (295) (295)", names["annual"])
    require(text["annual"],
            "Extensions and discoveries 8,318 28,849 Revisions of previous quantity "
            "estimates 144,956 139,856 95,623 Purchases 175,849 415,385",
            names["annual"])
    require(text["annual"],
            "Historically, we have reviewed on an annual basis all of our PUDs to "
            "ensure an appropriate plan for development exists", names["annual"])
    require(text["annual"],
            "the Company does not book proved reserves on discoveries until such time "
            "as a development plan has been prepared", names["annual"])
    require(text["egypt"],
            "performance analysis, volumetric analysis, and analogy", names["egypt"])
    require(text["gabon"],
            "performance analysis, volumetric analysis, analogy, and reservoir modeling",
            names["gabon"])
    require(text["egypt"],
            "Total Proved (1P) 16,352.8 9,448.1", names["egypt"])
    require(text["gabon"],
            "Total Proved 22,023.0 11,063.1", names["gabon"])
    require(text["cdi"],
            "Total Proved (1P) 15,251.6 6,551.3", names["cdi"])
    require(text["canada"],
            "8,126 Mboe total proved net after royalty reserves evaluated by us",
            names["canada"])
    require(text["canada"],
            "The following average prices have been adjusted for quality, transportation "
            "fees and market differentials", names["canada"])
    require(text["release"],
            "year-end 2024 2P WI CPR estimate of reserves is 96.1 MMBOE", names["release"])
    require(text["release"],
            "PV-10 does include the effect of income taxes", names["release"])

    pud_close = 6193 - 56 + 15670 + 2698 - 377
    if pud_close != 24128:
        raise RuntimeError("PUD bridge did not close")

    current_canada_extensions = -93 + 234 / 6 + 40
    if round(current_canada_extensions) != -14:
        raise RuntimeError("current-period product conversion did not reproduce summary")

    prior_extensions = 93 + 810 + 3219 / 6 + 505
    if math.floor(prior_extensions + 0.5) != 1945:
        raise RuntimeError("prior-period product conversion did not reproduce moved amount")

    engineer_total = 9448.1 + 11063.1 + 8126 + 15251.6 + 6551.3 / 5.8
    if round(engineer_total) != 45018:
        raise RuntimeError("engineer reports did not reconcile to issuer ending reserves")

    return [
        Matter(
            "R-01", "CORRECT",
            "The current-year proved-undeveloped extension/discovery line conflicts "
            "with its own additions narrative.",
            f"{names['annual']} - Proved Undeveloped Reserves table and adjacent "
            "Extensions and Discoveries narrative: 6,193 - 56 + 15,670 + 2,698 - 377 "
            "= 24,128 MBoe; the bridge prints (377) MBoe for extensions while the prose "
            "reports 0.4 MMBoe of additions, primarily in Canada.",
            f"The printed bridge closes to {pud_close:,} MBoe, but arithmetic closure "
            "does not validate a negative extension/discovery classification. The table "
            "and the description cannot both represent the movement as printed; the "
            "ending PUD balance is not challenged by this category exception.",
            "Obtain the reserve-engineer movement schedule, correct the PUD category "
            "allocation and signs, and conform the adjacent narrative without assuming "
            "that the parenthesized amount merely needs its sign reversed."
        ),
        Matter(
            "R-02", "CORRECT; AMOUNT ALLOCATION UNRESOLVED",
            "The current-year product tables reproduce the negative equivalent-unit "
            "extension amount, but they do not cure its category meaning.",
            f"{names['annual']} - Reserve Information oil, natural gas, NGL, and Total "
            "Reserves tables: Canada shows oil (93) MBbl, gas 234 MMcf and NGL 40 MBbl; "
            "using the disclosed 6:1 factor gives -93 + 234/6 + 40 = "
            f"{current_canada_extensions:.0f} MBoe, matching the total table's (14) MBoe.",
            "The product-to-BOE tie-out shows consistent propagation of the printed "
            "classification, not a valid negative discovery. The supplied package does "
            "not establish the corrected split between extensions and revisions.",
            "Require a property-level reserve movement schedule, correct all product and "
            "BOE category layers together, and retain the ending-balance tie-out."
        ),
        Matter(
            "R-03", "CORRECT",
            "The comparative-year BOE summary moved an organic extension amount into "
            "purchases even though the product tables report no purchase.",
            f"{names['annual']} - Reserve Information comparative-year product and Total "
            "Reserves tables: oil extensions are 93 MBbl in Egypt and 810 MBbl in Canada, "
            "Canada gas extensions are 3,219 MMcf and NGL extensions are 505 MBbl. "
            f"The disclosed 6:1 factor gives {prior_extensions:,.1f} MBoe, which rounds "
            "to 1,945 MBoe; the BOE summary reports 1,945 as purchases and zero extensions.",
            "This is a cross-table category swap. Reclassifying the 1,945 MBoe does not "
            "change the comparative-year ending reserve quantity, but it changes the "
            "reported acquisition-versus-organic history.",
            "Move 1,945 MBoe in the comparative BOE summary from purchases to extensions "
            "and discoveries, then reassess every trend or replacement statement that "
            "uses the affected comparative categories."
        ),
        Matter(
            "R-04", "CORRECT; VALUE REALLOCATION UNRESOLVED",
            "Quantity-category exceptions require review of the standardized-measure "
            "movement categories, but the corrected dollar split cannot be derived here.",
            f"{names['annual']} - Changes in Standardized Measure of Discounted Future "
            "Net Cash Flows: current-year extensions and discoveries are $8.318 million "
            "and revisions of previous quantity estimates are $144.956 million.",
            "The upstream extension/revision classifications are unreliable, so these "
            "downstream change categories may also be misstated. Volume alone cannot "
            "allocate value because property timing, prices, costs, taxes and discounting "
            "are not supplied at the level needed. The $379.400 million ending measure is "
            "not disproved merely by a category presentation error.",
            "Have accounting and the reserve engineers rerun or bridge the property-level "
            "cash flows and correct the change categories; do not prorate dollars from "
            "the volume reclassification."
        ),
        Matter(
            "R-05", "EVIDENCE REQUEST; NO VIOLATION CONCLUDED",
            "The package states a PUD policy but does not demonstrate that the complete "
            "year-end PUD population is covered by a current adopted development plan.",
            f"{names['annual']} - Proved Undeveloped Reserves and reserve-policy text: "
            "management says it historically reviews all PUDs annually and says newly "
            "booked discoveries require a development plan with drilling within five "
            "years from initial booking and required approvals.",
            "Those policy statements do not provide booking dates, scheduled conversion "
            "dates, plan approval, or exception support for the entire current population, "
            "including acquired PUDs. The record supports a disclosure-evidence gap, not "
            "a conclusion that any specific PUD is invalid.",
            "Obtain the location-level PUD aging roll-forward, adopted plan and approval "
            "evidence, expected conversion dates, delay history, and support for any "
            "location extending beyond the ordinary development horizon."
        ),
        Matter(
            "R-06", "QUALIFY AND SUPPLEMENT",
            "The issuer-level filing lacks a general discussion connecting technologies "
            "actually applied to material reserve additions, although evaluator exhibits "
            "partially supply method evidence.",
            f"{names['annual']} - Controls over Reserve Estimates and reliable-technology "
            f"definition; {names['egypt']}, {names['gabon']} and {names['cdi']} - methods "
            "paragraphs identifying performance analysis, volumetric analysis, analogy "
            "and, for some properties, reservoir modeling.",
            "A definition, an input list, and management's control description are not a "
            "general discussion of applied technology. The independent reports mitigate "
            "the omission within their scopes but do not replace management's coherent "
            "issuer-level explanation or connect methods to the material additions.",
            "Add an issuer-level discussion of the technologies used to establish "
            "reasonable certainty for material additions, linked to the relevant reserve "
            "classes and properties while preserving evaluator scope."
        ),
        Matter(
            "R-07", "QUALIFY",
            "Significant purchase movements are not described consistently across the "
            "reserve-change narrative and comparative reserve tables.",
            f"{names['annual']} - Total Reserves table and acquisition descriptions: the "
            "current year reports 16,465 MBoe of purchases tied to the Svenska acquisition, "
            "while the earlier comparative BOE table reports 18,496 MBoe of purchases and "
            "the broader filing identifies the TransGlobe acquisition.",
            "The current acquisition is directly connected to the reserve addition, while "
            "the comparative reserve-change presentation requires the reader to assemble "
            "the connection elsewhere. This is a narrative-completeness matter separate "
            "from the comparative category swap identified in R-03.",
            "Add or cross-reference a concise explanation of each significant purchase "
            "movement by period, geography and transaction, after correcting the "
            "comparative classification."
        ),
        Matter(
            "R-08", "CLEARED WITH SCOPE LIMITATION",
            "The independent engineer reports reconcile to the issuer's ending proved "
            "reserve total within rounding; this does not clear movement classifications.",
            f"{names['egypt']} - Total Proved net 9,448.1 MBbl; {names['gabon']} - Total "
            f"Proved net 11,063.1 MBbl; {names['canada']} - 8,126 MBoe evaluated; "
            f"{names['cdi']} - Total Proved net 15,251.6 MBbl oil and 6,551.3 MMcf gas. "
            f"Using the disclosed 5.8:1 gas factor gives {engineer_total:,.1f} MBoe, "
            "rounding to the issuer's 45,018 MBoe.",
            "The four reports support geographic coverage and the rounded ending quantity. "
            "They are independent estimates or evaluations that rely on identified "
            "management inputs; they are not an audit of issuer controls and do not "
            "validate reserve movement labels.",
            "Retain the ending-balance tie-out as a clearance, preserve each evaluator's "
            "scope and reliance wording, and remediate the category exceptions separately."
        ),
        Matter(
            "R-09", "CLEARED",
            "The apparent difference between a benchmark price and a property price is "
            "supported as an adjustment rather than a reserve-pricing error.",
            f"{names['canada']} - pricing paragraph and tables: the Canada oil reference "
            "price is $70.81 per barrel and the Harmattan property price is $69.12 per "
            "barrel; the report says prices are adjusted for quality, transportation fees "
            "and market differentials and held constant.",
            "A property-adjusted price need not equal the unadjusted reference price. The "
            "stated adjustment basis and constant-price treatment explain the difference, "
            "so the figures should not be forced to match.",
            "Document the clearance and retain the adjustment support; no price correction "
            "is proposed from the supplied evidence."
        ),
        Matter(
            "R-10", "CLEARED AS INCOMPARABLE BASES; QUALIFY PRESENTATION",
            "The external summary places SEC proved measures near a larger 2P working-"
            "interest measure, but the figures are not a reconcilable pair on the supplied "
            "bases.",
            f"{names['release']} - Year-End Reserves, PV-10 Value and Probable Reserves, "
            "and WI CPR Reserves: SEC proved reserves are 45.0 MMBOE with standardized "
            "measure of $379.4 million; 2P WI CPR reserves are 96.1 MMBOE before government "
            "royalties with PV-10 of $686.6 million using management timing and escalated "
            "prices and costs. The release defines PV-10 as non-GAAP and says its measure "
            "includes income taxes.",
            "Reserve class, framework, ownership, price and cost assumptions differ. A "
            "shared discount rate does not make the measures comparable, and the source "
            "says a reconciliation is not practicable. The issuer-specific tax definition "
            "also overrides a generic assumption that PV-10 excludes tax.",
            "Keep the measures visibly separated, repeat the basis qualifications near "
            "each headline figure, and do not present $686.6 million as a bridge to the "
            "SEC standardized measure or as fair value."
        ),
    ]


def write_register(path: Path, matters: list[Matter]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(asdict(matters[0])))
        writer.writeheader()
        writer.writerows(asdict(matter) for matter in matters)


def write_memo(path: Path, matters: list[Matter]) -> None:
    matter = {item.review_id: item for item in matters}
    lines = [
        "# Reserve disclosure exception review",
        "",
        "## Filing-readiness conclusion",
        "",
        "The package is not ready to be reused without correction. The current-period "
        "PUD movement conflict, the product-to-BOE classification issue, and the "
        "comparative-period category swap require coordinated correction (R-01, R-02, "
        "R-03). Their value-table effect must be recalculated rather than inferred from "
        "volumes (R-04). Current support is also insufficient to close the population-wide "
        "PUD plan and issuer-level applied-technology disclosures (R-05, R-06).",
        "",
        "## Matters requiring correction or qualification",
        "",
    ]
    for key in ("R-01", "R-02", "R-03", "R-04", "R-05", "R-06", "R-07"):
        item = matter[key]
        lines.extend([
            f"### {key} - {item.statement}",
            "",
            item.analysis,
            "",
            f"Action: {item.proposed_action}",
            "",
        ])
    lines.extend([
        "## Cleared high-risk apparent inconsistencies",
        "",
    ])
    for key in ("R-08", "R-09", "R-10"):
        item = matter[key]
        lines.extend([
            f"### {key} - {item.statement}",
            "",
            item.analysis,
            "",
            f"Disposition: {item.disposition}. {item.proposed_action}",
            "",
        ])
    lines.extend([
        "## Open evidence requests",
        "",
        "The committee should not approve reuse until the reserve team supplies the "
        "property-level movement schedule and the accounting team supplies the resulting "
        "cash-flow-category bridge (R-02, R-04). The location-level PUD aging, plan and "
        "approval record remains necessary before a compliance conclusion can be made "
        "about the full PUD population (R-05).",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    matters = build_matters(args.workspace / "source_documents")
    write_register(args.output_dir / "reserve_disclosure_register.csv", matters)
    write_memo(args.output_dir / "reserve_disclosure_review.md", matters)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

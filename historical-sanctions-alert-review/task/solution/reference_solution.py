#!/usr/bin/env python3
"""Build the reference alert review from the supplied records and source documents."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import subprocess
import zipfile
from pathlib import Path


SANCTIONS = {
    "224546": (
        "TRUE MATCH",
        "NO APPLICABLE RESTRICTION DURING TRANSACTION PERIOD",
        "CLOSE HISTORICAL SANCTIONS ALERT; DO NOT APPLY THE LATER DESIGNATION RETROACTIVELY",
        "The payment predates the March 2014 designation. The current-list identity is real, but it does not change the legal state of the 2008 transfer.",
        ["review_transactions.csv transaction 224546", "action-2014-03-20.html list update"],
    ),
    "241389": (
        "TRUE MATCH",
        "NO APPLICABLE RESTRICTION DURING TRANSACTION PERIOD",
        "CLOSE HISTORICAL SANCTIONS ALERT; DO NOT APPLY THE LATER DESIGNATION RETROACTIVELY",
        "The payment predates the March 2014 designation. A present-day true match is not a transaction-time block for the 2011 transfer.",
        ["review_transactions.csv transaction 241389", "action-2014-03-20.html list update"],
    ),
    "224861": (
        "TRUE MATCH",
        "NON-BLOCKING DIRECTIVE 1 RESTRICTION APPLIED; TRANSACTION SCOPE UNRESOLVED",
        "DO NOT BLOCK; OBTAIN THE INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS BEFORE DECIDING WHETHER REJECTION WAS REQUIRED",
        "VTB was identified under Directive 1 before this September 2014 payment. That measure was not blocking and covered specified new debt or equity; the summary record does not identify the instrument or terms.",
        ["review_transactions.csv transaction 224861", "action-2014-07-29.html SSI additions", "faq-370.html"],
    ),
    "227437": (
        "TRUE MATCH",
        "NON-BLOCKING DIRECTIVE 1 RESTRICTION APPLIED; TRANSACTION SCOPE UNRESOLVED",
        "DO NOT BLOCK; OBTAIN THE INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS BEFORE DECIDING WHETHER REJECTION WAS REQUIRED",
        "VTB was already subject to Directive 1, but a one-payment bank summary does not show whether the 2015 transfer dealt in covered debt or equity.",
        ["review_transactions.csv transaction 227437", "action-2014-07-29.html SSI additions", "faq-370.html"],
    ),
    "232714": (
        "TRUE MATCH",
        "NON-BLOCKING DIRECTIVE 1 RESTRICTION APPLIED; TRANSACTION SCOPE UNRESOLVED",
        "DO NOT BLOCK; OBTAIN THE INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS BEFORE DECIDING WHETHER REJECTION WAS REQUIRED",
        "The institutional name and Russian geography support the VTB identity. Directive 1 applied in 2015, but the record supplies no financing-product or tenor facts.",
        ["review_transactions.csv transaction 232714", "candidate_list_records.csv UID 17013", "faq-370.html"],
    ),
    "234749": (
        "TRUE MATCH",
        "NON-BLOCKING DIRECTIVE 1 RESTRICTION APPLIED; TRANSACTION SCOPE UNRESOLVED",
        "DO NOT BLOCK; OBTAIN THE UNDERLYING PAYMENT DATES, INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS",
        "VTB was subject to the non-blocking financing restriction. This row aggregates four payments across a period and does not reveal the product, issuance date, or terms needed to decide scope.",
        ["review_transactions.csv transaction 234749", "action-2014-07-29.html SSI additions", "faq-370.html"],
    ),
    "238675": (
        "TRUE MATCH",
        "TRANSACTION PERIOD STRADDLES THE VTB IDENTIFICATION DATE; COMPONENT STATUS UNRESOLVED",
        "DO NOT BLOCK OR CLEAR; OBTAIN EACH COMPONENT VALUE DATE AND THEN THE INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS",
        "The two-payment summary begins before and ends after VTB's July 2014 identification. It cannot show which component fell on which side of the effective date, and it also lacks Directive 1 scope facts.",
        ["review_transactions.csv transaction 238675", "action-2014-07-29.html SSI additions", "faq-370.html"],
    ),
    "225021": (
        "TRUE MATCH",
        "NO APPLICABLE RESTRICTION DURING TRANSACTION PERIOD",
        "CLOSE HISTORICAL SANCTIONS ALERT; DO NOT APPLY THE LATER SECTORAL OR BLOCKING MEASURES RETROACTIVELY",
        "This June-to-August 2014 period ended before Sberbank was added to the sectoral financing restriction in September 2014.",
        ["review_transactions.csv transaction 225021", "action-2014-09-12.html"],
    ),
    "229306": (
        "TRUE MATCH",
        "NO APPLICABLE RESTRICTION DURING TRANSACTION PERIOD",
        "CLOSE HISTORICAL SANCTIONS ALERT; DO NOT APPLY THE LATER SECTORAL OR BLOCKING MEASURES RETROACTIVELY",
        "The May 2014 transfer predates Sberbank's September 2014 sectoral identification.",
        ["review_transactions.csv transaction 229306", "action-2014-09-12.html"],
    ),
    "240310": (
        "TRUE MATCH",
        "NON-BLOCKING DIRECTIVE 1 RESTRICTION APPLIED; TRANSACTION SCOPE UNRESOLVED",
        "DO NOT BLOCK; OBTAIN THE INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS BEFORE DECIDING WHETHER REJECTION WAS REQUIRED",
        "Sberbank was under Directive 1 by November 2014. The payment summary establishes involvement but not whether the transfer was a prohibited dealing in new debt or equity.",
        ["review_transactions.csv transaction 240310", "action-2014-09-12.html", "faq-370.html"],
    ),
    "240104": (
        "TRUE MATCH",
        "NON-BLOCKING DIRECTIVE 1 RESTRICTION APPLIED; TRANSACTION SCOPE UNRESOLVED",
        "DO NOT BLOCK; OBTAIN THE TWO COMPONENT VALUE DATES, INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS",
        "Sberbank was subject to Directive 1 throughout this late-2014 to early-2015 period. The aggregate identifies two payments but omits the product and financing terms.",
        ["review_transactions.csv transaction 240104", "action-2014-09-12.html", "faq-370.html"],
    ),
    "227490": (
        "TRUE MATCH",
        "NON-BLOCKING DIRECTIVE 1 RESTRICTION APPLIED; TRANSACTION SCOPE UNRESOLVED",
        "DO NOT BLOCK; OBTAIN THE INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS BEFORE DECIDING WHETHER REJECTION WAS REQUIRED",
        "The 2015 activity postdates the sectoral identification. The row does not establish that either of the two transfers was covered debt, equity, or extended payment terms.",
        ["review_transactions.csv transaction 227490", "action-2014-09-12.html", "faq-419.html"],
    ),
    "226828": (
        "TRUE MATCH",
        "NON-BLOCKING DIRECTIVE 1 RESTRICTION APPLIED; TRANSACTION SCOPE UNRESOLVED",
        "DO NOT BLOCK; OBTAIN THE UNDERLYING PAYMENT DATES, INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS",
        "The 56-payment aggregate involves Sberbank after its sectoral identification. Amount and involvement alone do not establish prohibited financing; the underlying product and terms are absent.",
        ["review_transactions.csv transaction 226828", "action-2014-09-12.html", "faq-370.html", "faq-419.html"],
    ),
    "227538": (
        "TRUE MATCH",
        "HISTORICAL OWNERSHIP COVERAGE UNRESOLVED; THE SUPPLIED LATER OWNERSHIP PERCENTAGE CANNOT ESTABLISH THE TRANSACTION-TIME STATE",
        "DO NOT BLOCK OR CLEAR; OBTAIN DATED OWNERSHIP RECORDS FOR THE COMPONENT PAYMENT DATES, THEN OBTAIN THE PAYMENT DATES, INSTRUMENT, ISSUANCE DATE, MATURITY OR TENOR, AND PAYMENT TERMS IF COVERAGE IS ESTABLISHED",
        "Vnesheconombank was under Directive 1 before the reviewed period, and the seven-payment aggregate runs from 9 April 2015 through 22 April 2016. The supplied 2015 report states 97.52 percent ownership but does not establish when that percentage took effect or that majority ownership remained continuous through each 2015-2016 payment date. Transaction-time ownership and downstream Directive 1 scope therefore remain unresolved.",
        ["review_transactions.csv transaction 227538", "action-2014-07-16.html Vnesheconombank entry", "vnesheconombank-group-non-financial-report-2015.pdf page 22", "faq-373.html"],
    ),
    "228525": (
        "TRUE MATCH",
        "NO APPLICABLE RESTRICTION DURING TRANSACTION PERIOD",
        "CLOSE HISTORICAL SANCTIONS ALERT; DO NOT APPLY THE 2022 DESIGNATION RETROACTIVELY",
        "The March 2014 transaction predates the supplied April 2022 action that added this institution to the blocked list.",
        ["review_transactions.csv transaction 228525", "action-2022-04-06.html"],
    ),
    "237602": (
        "TRUE MATCH",
        "NO APPLICABLE RESTRICTION DURING TRANSACTION PERIOD",
        "CLOSE HISTORICAL SANCTIONS ALERT; DO NOT APPLY THE 2022 DESIGNATION RETROACTIVELY",
        "The December 2014 payment predates the supplied February 2022 blocking action against Otkritie.",
        ["review_transactions.csv transaction 237602", "action-2022-02-24.html"],
    ),
    "237854": (
        "TRUE MATCH",
        "NO APPLICABLE RESTRICTION DURING TRANSACTION PERIOD",
        "CLOSE HISTORICAL SANCTIONS ALERT; DO NOT APPLY THE 2022 DESIGNATION RETROACTIVELY",
        "The July 2012 transfer predates the supplied December 2022 Rosbank designation.",
        ["review_transactions.csv transaction 237854", "action-2022-12-15.html"],
    ),
    "224191": (
        "TRUE MATCH",
        "NO APPLICABLE RESTRICTION DURING TRANSACTION PERIOD",
        "CLOSE HISTORICAL SANCTIONS ALERT; DO NOT APPLY THE 2022 MEASURES RETROACTIVELY",
        "The October 2016 payment predates the supplied 2022 measures involving Alfa-Bank.",
        ["review_transactions.csv transaction 224191", "action-2022-02-24.html", "action-2022-04-06.html"],
    ),
    "239784": (
        "FALSE POSITIVE",
        "NO SANCTIONS STATUS FOR THE TRANSACTION PARTY FROM THIS CANDIDATE",
        "CLOSE THE SANCTIONS ALERT AS A DIFFERENT ENTITY",
        "The payment names a Chinese bank. The candidate record is a DPRK program entity without the China qualifier; the shared generic words do not establish identity.",
        ["review_transactions.csv transaction 239784", "candidate_list_records.csv UID 22983"],
    ),
    "235107": (
        "FALSE POSITIVE",
        "NO SANCTIONS STATUS FOR THE TRANSACTION PARTY FROM THIS CANDIDATE",
        "CLOSE THE SANCTIONS ALERT AS A DIFFERENT ENTITY",
        "The transaction party is an Indian bank, while the candidate is a Russian machinery wholesaler. The shared word is not an entity match.",
        ["review_transactions.csv transaction 235107", "candidate_list_records.csv UID 47535"],
    ),
}


AML = {
    "3730": (
        "ESCALATE FOR ENHANCED REVIEW",
        "The case contains opposite-direction Amsterdam Trade Bank and VTB Bank transfers of about 2.67 million on consecutive days, plus other cross-border flows. This supports a reciprocal-flow lead, but bank-level rows do not prove the same customer or funds; obtain payment messages, ordering-customer identifiers, purpose, and account linkage.",
        ["review_transactions.csv SAR 3730 transactions 232768-232770 and 232777", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "2340": (
        "ESCALATE FOR ENHANCED REVIEW WITHOUT ASSERTING STRUCTURING",
        "Many small payments from one bank to Sberbank cluster over several days, alongside other larger flows. The burst warrants review, but currency, an applicable threshold, customer linkage, and purpose are absent, so the amounts cannot establish structuring; obtain those facts and payment messages.",
        ["review_transactions.csv SAR 2340 transactions 228440-228461 and 228470-228481", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "4208": (
        "ESCALATE FOR ENHANCED REVIEW WITH AGGREGATION LIMITATION",
        "The case shows repeated high-value cross-border flows over long overlapping date ranges, including two same-direction Amsterdam Trade Bank summaries. The rows warrant review but must not be summed as disjoint exposure; obtain transaction-level data, customer linkage, and purposes.",
        ["review_transactions.csv SAR 4208 transactions 235033-235039", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "2380": (
        "ESCALATE FOR ENHANCED REVIEW",
        "The case shows substantial opposite-direction institution-level flows involving Rosbank, Russian Commercial Bank, and Amsterdam Trade Bank over a short period. This is a flow-through or reciprocal-flow lead, not proof that the same funds returned; obtain customer and payment-message linkage.",
        ["review_transactions.csv SAR 2380 transactions 237839-237856", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "2336": (
        "ESCALATE FOR ENHANCED REVIEW",
        "Several transfers went from Eesti Kreditbank to Bank Rossiya within days amid broader cross-border flows. The repetition supports targeted review independent of the later sanctions designation, but customer, purpose, and trade context are missing.",
        ["review_transactions.csv SAR 2336 transactions 224546, 224547, 236745", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "2716": (
        "HOLD AS INCONCLUSIVE PENDING DEFINED FACTS; DO NOT LABEL STRUCTURING",
        "Several values are close to round numbers, but the rows involve different bank pairs and the record supplies no common customer, currency, applicable threshold, or payment purpose. Obtain those facts before treating the cluster as threshold evasion.",
        ["review_transactions.csv SAR 2716 transactions 224119 and 224186-224192", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "3230": (
        "ESCALATE FOR ENHANCED REVIEW ON THE ACTIVITY, NOT THE FALSE SANCTIONS MATCH",
        "The sanctions candidate for the Chinese bank is false, but the case independently contains repeated cross-border aggregates to multiple beneficiary banks over overlapping periods. Review the underlying customers, purposes, and disjoint transaction detail without using the false hit as adverse evidence.",
        ["review_transactions.csv SAR 3230 transactions 239775-239786", "financial-crime-advisory.txt red-flag discussion"],
    ),
}


CONTROLS = {
    "OWNERSHIP-ASOF": (
        "HOLD HISTORICAL OWNERSHIP COVERAGE OPEN",
        ["227538"],
        "Obtain dated ownership records effective on each component payment date from 9 April 2015 through 22 April 2016 and, only if majority ownership is established for that date, the payment and instrument facts needed for Directive 1 scope.",
        "The report gives a 97.52 percent Vnesheconombank share in 2015, but it does not state when that percentage took effect or establish continuity through every payment in the 2015-2016 aggregate. It therefore cannot by itself prove majority ownership at each component payment date, even though Vnesheconombank was already under Directive 1.",
        ["review_transactions.csv transaction 227538", "action-2014-07-16.html", "vnesheconombank-group-non-financial-report-2015.pdf page 22", "faq-373.html"],
    ),
    "EFFECTIVE-DATE-RANGE": (
        "HOLD THE AGGREGATE OPEN ACROSS THE EFFECTIVE DATE",
        ["238675"],
        "Obtain both component value dates, then the instrument, issuance date, maturity or tenor, and payment terms for any post-identification component.",
        "The two-payment range starts before and ends after VTB's 29 July 2014 Directive 1 identification. An aggregate range cannot assign either component to the pre- or post-effective-date state.",
        ["review_transactions.csv transaction 238675", "action-2014-07-29.html", "faq-370.html"],
    ),
    "NONBLOCKING-SCOPE": (
        "KEEP CONFIRMED POST-EFFECTIVE DIRECTIVE 1 ALERTS OPEN FOR SCOPE; DO NOT DEFAULT TO BLOCKING",
        ["224861", "227437", "232714", "234749", "240310", "240104", "227490", "226828"],
        "Obtain component dates where aggregated and the instrument, issuance date, maturity or tenor, and payment terms before determining whether rejection was required.",
        "These VTB and Sberbank records postdate the applicable Directive 1 identifications, but Directive 1 was non-blocking and reached specified new debt or equity rather than every payment involving the institution.",
        ["review_transactions.csv identified transactions", "action-2014-07-29.html", "action-2014-09-12.html", "faq-370.html", "faq-419.html"],
    ),
    "OVERLAP-CONTROL": (
        "DO NOT SUM OVERLAPPING AGGREGATES AS DISJOINT EXPOSURE",
        ["4208", "3230"],
        "Obtain underlying transaction-level records and stable payment identifiers before calculating totals or treating repeated summaries as separate activity.",
        "Both AML groups include aggregate rows whose periods overlap. Counts and values can support a review lead, but summing those summaries would create an unsupported exposure amount.",
        ["review_transactions.csv SAR 4208", "review_transactions.csv SAR 3230", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "RECIPROCAL-FLOW": (
        "TREAT THE OPPOSITE-DIRECTION FLOWS AS AN INVESTIGATIVE LEAD, NOT PROOF OF RETURNED FUNDS",
        ["3730", "2380"],
        "Obtain ordering-customer and beneficiary identifiers, account linkage, payment messages, value dates, purpose, and a source-of-funds trail.",
        "The bank-level summaries show opposite-direction flows close in time, but they do not establish a common customer, common account, or that the same funds returned.",
        ["review_transactions.csv SAR 3730", "review_transactions.csv SAR 2380", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "STRUCTURING-SUPPORT": (
        "DO NOT CONCLUDE STRUCTURING; ESCALATE THE 2340 CLUSTER BUT HOLD 2716 INCONCLUSIVE",
        ["2340", "2716"],
        "Obtain transaction currency, the applicable reporting or control threshold, customer and account linkage, instrument type, and payment purpose.",
        "SAR 2340 has a repeated small-payment burst that supports review, while SAR 2716 combines different bank pairs and only superficially round values. Neither record establishes threshold evasion without the missing threshold and linkage facts.",
        ["review_transactions.csv SAR 2340", "review_transactions.csv SAR 2716", "financial-crime-advisory.txt red-flag discussion"],
    ),
    "AML-SANCTIONS-INDEPENDENCE": (
        "BASE AML ESCALATION ON ACTIVITY, NOT THE SANCTIONS MATCH OUTCOME",
        ["2336", "3230"],
        "Obtain customer linkage, purposes, payment messages, and underlying transaction detail for the observed activity without treating either alert result as adverse evidence.",
        "The Bank Rossiya identity is real but its designation came later, while the Chinese-bank sanctions candidate is false. The respective AML activity can still warrant review, and neither match result proves or disproves suspicious conduct.",
        ["review_transactions.csv SAR 2336", "review_transactions.csv SAR 3230", "action-2014-03-20.html", "candidate_list_records.csv"],
    ),
}


REQUIRED_TEXT = {
    "action-2014-03-20.html": ["BANK ROSSIYA", "03/20/2014"],
    "action-2014-07-16.html": ["VNESHECONOMBANK", "Directive 1"],
    "action-2014-07-29.html": ["VTB BANK", "longer than 90 days"],
    "action-2014-09-12.html": ["Sberbank", "30 days"],
    "faq-370.html": ["not require", "block"],
    "faq-373.html": ["owned", "50 percent"],
    "faq-419.html": ["payment terms", "invoice"],
    "action-2022-02-24.html": ["OTKRITIE", "VTB"],
    "action-2022-04-06.html": ["AMSTERDAM TRADE BANK", "ALFA-BANK"],
    "action-2022-12-15.html": ["ROSBANK", "12/15/2022"],
}


def visible_html(path: Path) -> str:
    body = path.read_text(encoding="utf-8", errors="replace")
    body = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", body, flags=re.I | re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", body))


def validate_materials(workspace: Path) -> dict[str, dict[str, str]]:
    data = workspace / "data"
    docs = workspace / "source_documents"
    rows = {r["id"]: r for r in csv.DictReader((data / "review_transactions.csv").open(encoding="utf-8"))}
    missing = sorted(set(SANCTIONS) - set(rows))
    if missing:
        raise RuntimeError(f"review transactions missing: {missing}")

    with zipfile.ZipFile(data / "transaction_archive.zip") as archive:
        archived = {
            r["id"]: r
            for r in csv.DictReader(
                archive.read("download_transactions_map.csv").decode("utf-8-sig").splitlines()
            )
        }
    for key in SANCTIONS:
        if archived.get(key) != rows[key]:
            raise RuntimeError(f"review row {key} does not match the archived record")

    for filename, needles in REQUIRED_TEXT.items():
        text = visible_html(docs / filename)
        if any(needle.lower() not in text.lower() for needle in needles):
            raise RuntimeError(f"source anchor not found in {filename}")

    advisory = (docs / "financial-crime-advisory.txt").read_text(encoding="utf-8", errors="replace")
    if "not proof of illegal activity" not in advisory.lower() or "red flags" not in advisory.lower():
        raise RuntimeError("financial-crime advisory anchors not found")

    report = docs / "vnesheconombank-group-non-financial-report-2015.pdf"
    ownership = subprocess.run(
        ["pdftotext", "-f", "24", "-l", "24", "-layout", str(report), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if "BelVEB" not in ownership or "97.52%" not in ownership:
        raise RuntimeError("ownership report anchors not found")
    return rows


def build(workspace: Path) -> dict:
    validate_materials(workspace)
    template = json.loads((workspace / "review_template.json").read_text(encoding="utf-8"))
    for row in template["sanctions_reviews"]:
        identity, status, action, rationale, evidence = SANCTIONS[row["transaction_id"]]
        row.update(
            identity_assessment=identity,
            transaction_time_status=status,
            required_action=action,
            rationale=rationale,
            evidence=evidence,
        )
    for row in template["aml_reviews"]:
        assessment, rationale, evidence = AML[row["sar_id"]]
        row.update(assessment=assessment, rationale=rationale, evidence=evidence)
    for row in template["control_assessments"]:
        assessment, affected, fact_request, rationale, evidence = CONTROLS[row["control_id"]]
        row.update(
            assessment=assessment,
            affected_records=affected,
            fact_request=fact_request,
            rationale=rationale,
            evidence=evidence,
        )
    template["executive_summary"] = (
        "The queue contains true current-list identities, false positives, later designations, "
        "historical non-blocking restrictions, an unresolved transaction-time ownership chain, and "
        "a date-range ambiguity. None of the supplied historical payment summaries alone supports a "
        "retroactive block or a finding of money laundering. Defined ownership, scope, aggregation, "
        "and AML evidence requests remain open."
    )
    return template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.add_argument("--output", type=Path, default=Path("/workspace/alert_review.json"))
    args = parser.parse_args()
    result = build(args.workspace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

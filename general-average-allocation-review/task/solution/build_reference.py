#!/usr/bin/env python3
"""Build the reference review from the supplied adjustment and decision record."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path


SOURCE_HASHES = {
    "general_average_adjustment.pdf": "619145dc604bd41d6eed641431c2ba8627738da047231877567402e695859d73",
    "first_instance_judgment.pdf": "74acc1d2c639cf5c769153eb18a286d67848adff70f7a74bdc6e05a72c6df781",
    "court_of_appeal_judgment.pdf": "5725d8ec96f904f3c20081830ea29b64854f3341af2d28513f22577e34a97c54",
    "final_judgment.pdf": "cb547aaee028dbbb982655eb17a5e0e16b3804273d316528536427515f9b99f0",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_text(path: Path) -> str:
    with tempfile.NamedTemporaryFile(suffix=".txt") as temporary:
        subprocess.run(
            ["pdftotext", "-layout", str(path), temporary.name],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return Path(temporary.name).read_text(encoding="utf-8", errors="replace")


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def require(text: str, fragments: list[str], source: str) -> None:
    flattened = compact(text)
    missing = [fragment for fragment in fragments if compact(fragment) not in flattened]
    if missing:
        raise RuntimeError(f"source anchor missing in {source}: {missing[0]}")


def write_schedule(path: Path) -> None:
    rows = [
        ["contributory_interest", "Vessel", "sound value less particular-average casualty repairs", "119614487.00", "3199209.07", "2.67460000", "historical adjusted contribution", "general_average_adjustment.pdf p.50, p.95"],
        ["contributory_interest", "Cargo including freight", "freight fully earned and embedded; two shipper-owned boxes embedded", "367418702.00", "9826980.60", "2.67460000", "historical adjusted contribution", "general_average_adjustment.pdf pp.10, 50, 95"],
        ["contributory_interest", "Containers", "5,981 boxes excluding two shipper-owned boxes carried in cargo", "14315119.00", "382872.17", "2.67460000", "historical adjusted contribution", "general_average_adjustment.pdf pp.10, 50, 95"],
        ["contributory_interest", "Bunkers", "remaining plus discharged/not reloaded less voyage consumption plus amount made good", "1675696.00", "44818.17", "2.67460000", "historical adjusted contribution", "general_average_adjustment.pdf pp.10, 50, 95"],
        ["control", "Total contributory capital and apportioned claim", "sum of four interests", "503024004.00", "13453880.01", "2.67460000", "reconciled", "general_average_adjustment.pdf p.95"],
        ["rule_fund", "YAR 1974/1990", "single-rule fund before population apportionment", "503024004.00", "13407562.70", "2.66539223", "historical quantum", "general_average_adjustment.pdf p.93"],
        ["rule_fund", "YAR 1994", "single-rule fund before population apportionment", "503024004.00", "13609501.74", "2.70553724", "historical quantum", "general_average_adjustment.pdf p.93"],
        ["allowance_section", "A Salvage remuneration and costs", "gross less remainder equals admitted general average", "10310794.05", "10203263.24", "", "remainder 107530.81", "general_average_adjustment.pdf pp.89-90"],
        ["allowance_section", "B Expenditure in China", "gross less remainder equals admitted general average", "1158590.22", "1141911.02", "", "remainder 16679.20", "general_average_adjustment.pdf pp.89-90"],
        ["allowance_section", "C Crew wages maintenance and bunker consumption", "all gross expenditure admitted", "37761.14", "37761.14", "", "remainder 0.00", "general_average_adjustment.pdf pp.89-90"],
        ["allowance_section", "D Miscellaneous disbursements", "gross less remainder equals admitted general average", "423848.94", "422596.78", "", "remainder 1252.16", "general_average_adjustment.pdf pp.89-90"],
        ["allowance_control", "Principal allowance ledger", "sum of sections A through D", "11930994.35", "11805532.18", "", "remainder 125462.17", "general_average_adjustment.pdf pp.89-90"],
        ["allowance_control", "Commission base", "printed Rule XX base is not the whole admitted principal", "11306541.09", "226130.84", "2.00000000", "commission bridge", "general_average_adjustment.pdf pp.89-90"],
        ["allowance_control", "YAR 1974/1990 interest", "7 percent Rule XXI amount; detailed source calculation not supplied", "", "509909.02", "7.00000000", "rule-specific add-on", "general_average_adjustment.pdf pp.89-90"],
        ["allowance_control", "YAR 1994 interest", "7 percent Rule XXI amount; detailed source calculation not supplied", "", "711848.06", "7.00000000", "rule-specific add-on", "general_average_adjustment.pdf pp.89-90"],
        ["allowance_control", "Pre-fee YAR 1974/1990 subtotal", "admitted principal plus commission plus applicable interest", "", "12541572.04", "", "reconciled", "general_average_adjustment.pdf p.90"],
        ["allowance_control", "Pre-fee YAR 1994 subtotal", "admitted principal plus commission plus applicable interest", "", "12743511.08", "", "reconciled", "general_average_adjustment.pdf p.90"],
        ["allowance_control", "Adjustment fees and expenses", "common final add-on to both rule funds", "", "865990.66", "", "reconciled", "general_average_adjustment.pdf pp.91-92"],
        ["split_voucher", "B5 underwater surveys", "gross invoice divided by timing of surveys", "20866.30", "6955.43", "", "remainder 13910.87; post-refloating portion particular average", "general_average_adjustment.pdf pp.69-70"],
        ["excluded_voucher", "B9 crew-change agency expense", "gross invoice carried wholly to remainder", "2768.33", "0.00", "", "remainder 2768.33; not allowable", "general_average_adjustment.pdf pp.71-72"],
        ["split_voucher", "D10b June 2012 travel", "gross expense split between remainder and admitted general average", "4327.10", "3074.94", "", "remainder 1252.16", "general_average_adjustment.pdf pp.85-86"],
        ["contract_population", "Cargo and containers under YAR 1974/1990", "CMA CGM, ANL, CNC, China Shipping bill forms", "294178269.00", "10332366.09", "77.06371634", "population share and allocated fund", "general_average_adjustment.pdf p.94"],
        ["contract_population", "Cargo and containers under YAR 1994", "Delmas, Hyundai, APL, EMC, MOL, FESCO bill forms", "87555552.00", "3121513.92", "22.93628366", "population share and allocated fund", "general_average_adjustment.pdf p.94"],
        ["security", "Cargo cash-deposit call", "provisional security rather than final adjusted debt", "", "", "8.00000000", "do not treat as final contribution rate", "general_average_adjustment.pdf p.10"],
        ["litigation", "Respondent cargo interests", "approximately 8% that refused payment", "", "800000.00", "", "owners' collection claim dismissed", "final_judgment.pdf paras.20-21, 146"],
        ["authority_status", "First-instance fact finding", "causative unseaworthiness and actionable fault established; collateral theories separately resolved", "", "", "", "owners' contribution claim dismissed", "first_instance_judgment.pdf paras.114-129"],
        ["authority_status", "Intermediate appeal", "two permitted owner grounds failed; one late ground abandoned", "", "", "", "first-instance order left in place", "court_of_appeal_judgment.pdf paras.29-31, 71-76"],
        ["authority_status", "Final appeal", "category distinction and due-diligence arguments rejected", "", "", "", "appeal dismissed; respondent recovery result controlling", "final_judgment.pdf paras.2, 145-146"],
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "record_type",
                "interest_or_population",
                "basis",
                "contributory_value_usd",
                "contribution_or_amount_usd",
                "rate_or_share_percent",
                "review_status",
                "evidence",
            ]
        )
        writer.writerows(rows)


MEMO = """# Technical review of general-average allocation and collection

## Executive position

The issued adjustment is internally arithmetically consistent as a historical quantum
record: its four contributing interests close to USD 503,024,004.00 and its blended
distribution closes to USD 13,453,880.01 at 2.67460000%. The later judgment does not
erase or recalculate that schedule. It changes enforceability: the owners cannot recover
the general-average contribution claimed from the respondent cargo interests because the
causative want of due diligence was actionable fault, and the owners' appeal was dismissed.
Accordingly, retain the adjustment as the account baseline but mark the litigated cargo
claim non-recoverable. Do not infer automatic refunds to paid non-parties or blanket release
of securities from the supplied records alone. (general_average_adjustment.pdf pp.93-95;
final_judgment.pdf paras.21, 145-146)

## Reconstructed capital and distribution

| Interest | Contributory value (USD) | Blended contribution (USD) | Basis |
| --- | ---: | ---: | --- |
| Vessel | 119,614,487.00 | 3,199,209.07 | Sound value 120,000,000.00 less 385,513.00 particular-average casualty repairs |
| Cargo including freight | 367,418,702.00 | 9,826,980.60 | Freight is fully earned/non-returnable and remains embedded in cargo |
| Containers | 14,315,119.00 | 382,872.17 | 5,981 boxes; the two shipper-owned boxes are already carried in cargo |
| Bunkers | 1,675,696.00 | 44,818.17 | Economic-at-risk reconstruction described below |
| **Total** | **503,024,004.00** | **13,453,880.01** | **Closes to the final distribution** |

The single-rule calculations are USD 13,407,562.70 at 2.66539223% under YAR
1974/1990 and USD 13,609,501.74 at 2.70553724% under YAR 1994. The final
2.67460000% is a blended presentation of the apportioned claim, not a substitute for
the contractual rule routing. (general_average_adjustment.pdf pp.93-95)

The 1974/1990 population comprises the CMA CGM, ANL, CNC and China Shipping bill
forms. Its cargo-and-container value is USD 294,178,269.00, representing 77.06371634%
of the combined cargo-and-container base, and it carries USD 10,332,366.09 of the
apportioned fund. The 1994 population comprises Delmas, Hyundai, APL, EMC, MOL and
FESCO. Its corresponding value is USD 87,555,552.00, share 22.93628366%, and fund
USD 3,121,513.92. The two fund portions add to USD 13,453,880.01.
(general_average_adjustment.pdf pp.7, 94)

## Finding register

| Ref | Determination | Evidence |
| --- | --- | --- |
| F01 | Freight must not be added as a separate contributing interest: the bill terms make it fully earned and non-returnable, so it is included in the USD 367,418,702 cargo value. | general_average_adjustment.pdf pp.10, 50 |
| F02 | The equipment population avoids double counting: two shipper-owned containers sit in cargo, while the separate USD 14,315,119 equipment value covers 5,981 other boxes. | general_average_adjustment.pdf pp.10, 50 |
| F03 | The USD 1,675,696 bunker value reconciles as USD 604,854.90 remaining plus USD 1,306,320.40 discharged and not reloaded, less USD 266,214.20 future voyage consumption, plus USD 30,734.90 made good. | general_average_adjustment.pdf p.50 |
| F04 | Contract populations, rather than a preference for the newest rules, control: four named bill families use YAR 1974/1990 and six named bill families use YAR 1994. | general_average_adjustment.pdf pp.7, 94 |
| F05 | The principal allowances are shared between the rule sets, but the adjustment separates the interest treatment before producing the population-weighted final claim. | general_average_adjustment.pdf pp.7-8, 90-94 |
| F06 | The USD 385,513 casualty-repair amount is particular average, deducted from vessel sound value; it is not a refloating sacrifice allowance in the general-average fund. | general_average_adjustment.pdf pp.10, 50 |
| F07 | No vessel sacrifice damage was found in the salvage operations, so no vessel sacrifice amount should be invented or moved into allowances. | general_average_adjustment.pdf p.10 |
| F08 | The reported box damage did not damage its cargo and was limited; the adjusters expressly made no general-average allowance for it. | general_average_adjustment.pdf pp.6, 10 |
| F09 | The salvage payment of USD 9,502,385.22, including bank charges against an all-in USD 9,500,000 settlement, is admitted general-average expenditure. | general_average_adjustment.pdf pp.8, 51 |
| F10 | Quantum and enforceability must remain separate: the issued allocation remains the historical computation, but it does not establish a collectible debt against cargo after the operative fault decision. | general_average_adjustment.pdf pp.93-95; final_judgment.pdf para.21 |
| F11 | The owners are not entitled to recover the respondent cargo interests' contribution because a causative breach of the carriage contract is actionable fault. | final_judgment.pdf paras.21, 28, 146 |
| F12 | The missing danger warning made the pre-voyage passage plan and working chart defective, and that condition rendered the vessel unseaworthy. | final_judgment.pdf paras.11-14, 31, 145-146 |
| F13 | The passage-plan defect was a real and effective cause of the master's decision to leave the buoyed fairway and of the grounding. | final_judgment.pdf paras.15-18 |
| F14 | The due-diligence obligation is non-delegable for work needed to make the vessel seaworthy; competent crew, charts and systems did not discharge it when the entrusted planning work was performed without reasonable care. | final_judgment.pdf paras.29, 32, 144-146 |
| F15 | The navigation-or-management exception cannot answer a causative breach of the prior seaworthiness duty, even though the relevant work involved navigational judgment. | final_judgment.pdf paras.27, 145(i), 145(vii) |
| F16 | The operative result is dismissal of the owners' appeal, preserving dismissal of their contribution claim against the respondent cargo interests. | final_judgment.pdf paras.30, 33, 146 |
| F17 | Keep the payment populations separate: most cargo interests had paid, while about 8% resisted and the litigated demand against respondents was approximately USD 800,000, not the whole USD 9,826,980.60 cargo contribution shown in the adjustment. | final_judgment.pdf paras.19-20; general_average_adjustment.pdf p.95 |
| F18 | The 8% cash-deposit call was provisional security and must not be used as the final debt or rate; the final blended adjustment rate is 2.67460000%. | general_average_adjustment.pdf pp.10, 95 |
| F19 | The supplied records do not determine automatic refunds for cargo interests that already paid, or universal guarantee releases; account terms, settlements, parties, limitation and payment evidence are not shown and require separate review. | final_judgment.pdf paras.20-21, 146 |
| F20 | Operationally, stop collection of the dismissed respondent claim, retain the quantum schedule, and reconcile each cash deposit, bond or guarantee against its account and governing instrument before refund or release. | general_average_adjustment.pdf p.10; final_judgment.pdf paras.20-21, 146 |
| F21 | Section A is not wholly admitted merely because every item concerns salvage: gross USD 10,310,794.05 divides into USD 107,530.81 remainder and USD 10,203,263.24 general average. | general_average_adjustment.pdf pp.89-90 |
| F22 | Section B gross USD 1,158,590.22 divides into USD 16,679.20 remainder and USD 1,141,911.02 general average. | general_average_adjustment.pdf pp.89-90 |
| F23 | Section C gross USD 37,761.14 is carried wholly to general average with no remainder. | general_average_adjustment.pdf pp.89-90 |
| F24 | Section D gross USD 423,848.94 divides into USD 1,252.16 remainder and USD 422,596.78 general average. | general_average_adjustment.pdf pp.89-90 |
| F25 | The four sections close at gross USD 11,930,994.35, remainder USD 125,462.17 and admitted principal USD 11,805,532.18. | general_average_adjustment.pdf pp.89-90 |
| F26 | Voucher B5 must be split by timing: of gross USD 20,866.30, USD 13,910.87 is remainder and USD 6,955.43 enters general average; the post-refloating survey portion is particular average. | general_average_adjustment.pdf pp.69-70 |
| F27 | Voucher B9 of USD 2,768.33 for crew-change and visa agency expense is wholly remainder and contributes zero to general average. | general_average_adjustment.pdf pp.71-72 |
| F28 | Voucher D10b is not wholly admitted or wholly rejected: gross USD 4,327.10 divides into USD 1,252.16 remainder and USD 3,074.94 general average. | general_average_adjustment.pdf pp.85-86 |
| F29 | Rule XX commission is USD 226,130.84 at 2% on the printed USD 11,306,541.09 base, not on the gross or the whole admitted-principal total; the supplied record does not support manufacturing a different base. | general_average_adjustment.pdf pp.89-90 |
| F30 | The interest columns remain separate: 7% Rule XXI interest is stated as USD 509,909.02 for YAR 1974/1990 and USD 711,848.06 for YAR 1994, producing pre-fee subtotals USD 12,541,572.04 and USD 12,743,511.08. | general_average_adjustment.pdf pp.89-90 |
| F31 | The detailed Rule XXI date-and-base calculation is said to be in the adjusters' file and is not supplied, so the two reported interest amounts can be reconciled but not independently re-performed. | general_average_adjustment.pdf pp.89-90 |
| F32 | Common adjustment fees and expenses of USD 865,990.66 are added to both pre-fee subtotals, closing the rule funds at USD 13,407,562.70 and USD 13,609,501.74. | general_average_adjustment.pdf pp.91-92 |
| F33 | The adjusters' statement that payment evidence was seen or confirmed concerns the disbursement accounts examined for the adjustment, except their fees; it is not evidence that every cargo contribution was paid. | general_average_adjustment.pdf p.11 |
| F34 | Security collection status is not contribution-payment status: the record describes about 95% of consignments secured by late July and later all but some low-value consolidated shipments secured, without an account-level cash-payment conclusion. | general_average_adjustment.pdf pp.7, 10 |
| F35 | The 8% deposit call and the approximately 8% resisting cargo population are different measures; neither the approximately USD 800,000 litigated claim nor the USD 9,826,980.60 aggregate cargo contribution can be substituted for the other. | general_average_adjustment.pdf pp.10, 95; final_judgment.pdf para.20 |
| F36 | The adjustment says standard Average Bonds and Guarantees incorporated a Non-Separation-Agreement, but it does not supply an account-level instrument register or terms supporting a blanket release or demand. | general_average_adjustment.pdf p.10 |
| F37 | The adjustment records administration of a dedicated trust account for cash deposits, but supplies no current balance, beneficial entitlement, allocation, release, or refund ledger. | general_average_adjustment.pdf p.91 |
| F38 | Security-collection expenses and adjustment administration remain part of the issued historical allowance ledger; the judgment does not direct their reclassification or a new adjustment. | general_average_adjustment.pdf pp.83-92; final_judgment.pdf para.146 |
| F39 | The approximately USD 800,000 respondent claim and approximately 8% population are procedural aggregates, not an identified account schedule; respondent membership and exact per-account amounts remain unshown. | final_judgment.pdf para.20 |
| F40 | Dismissal of the owners' appeal resolves the litigated recovery claim but the supplied judgment contains no account-level monetary, refund, or security-release order for other interests. | final_judgment.pdf paras.20-21, 146 |
| F41 | The owners' uncharted-shoal account was a party position, not a finding. The trial court instead found that the defective passage plan and omitted warning caused the master's unsafe departure from the fairway and the grounding. | general_average_adjustment.pdf p.6; first_instance_judgment.pdf paras.1-2, 124, 129 |
| F42 | The conventional burden allocation remained operative: cargo had to establish causative unseaworthiness, then the owners had to establish due diligence. Cargo's proposed Volcafe reversal was rejected at trial and not pursued on appeal. | first_instance_judgment.pdf paras.55-57; court_of_appeal_judgment.pdf paras.12, 31 |
| F43 | The trial court did not find that the relevant Notice to Mariners was absent from the vessel and found the separate sounding corrections were already marked; those allegations added no causative fault or unseaworthiness. | first_instance_judgment.pdf paras.116-117 |
| F44 | The absence of official electronic charts was not unseaworthiness in 2011 because no such SOLAS carriage requirement then applied and coverage was limited; any exclusive reliance on the installed display was left as negligent navigation, not an accepted additional seaworthiness defect. | first_instance_judgment.pdf paras.118-120 |
| F45 | The trial court rejected the collateral bridge-team and incompetence theories: no disabling lack of bridge communication was inferred and the experienced master was not found incompetent. | first_instance_judgment.pdf paras.121-122 |
| F46 | The master may have been tired, but fatigue was not shown materially to impair his decisions; on the balance of probabilities the defective passage plan caused the unsafe decision. | first_instance_judgment.pdf paras.123-124 |
| F47 | A contractual-deviation theory was unnecessary to decide and was rejected in any event: the short departure from the fairway was negligent navigation, not a radical change of voyage. | first_instance_judgment.pdf paras.125-128 |
| F48 | The intermediate appeal proceeded on the trial factual platform, which was not challenged. Two owner appeal grounds received permission, while a late third ground was abandoned and was not decided. | court_of_appeal_judgment.pdf paras.3, 29-30 |
| F49 | Of the cargo respondents' alternative grounds, the defective-working-chart route supported affirmance, but the alleged absence of a proper passage-planning system or culture was rejected; the latter is not an additional finding against the owners. | court_of_appeal_judgment.pdf paras.31, 71-72 |
| F50 | The procedural chain has one continuing recovery consequence: the first-instance dismissal of the owners' contribution claim was left in place when both the intermediate and final appeals were dismissed; the successive decisions are not separate payment or refund events. | first_instance_judgment.pdf para.129; court_of_appeal_judgment.pdf para.76; final_judgment.pdf paras.30, 33, 146 |
| F51 | The separate sounding corrections were already marked on the working chart when recorded after the casualty; the trial court did not infer a late addition and found no unseaworthiness on that ground. | first_instance_judgment.pdf para.117 |
| F52 | The experienced master was not found incompetent; the trial court rejected cargo's requested inference from his negligent acts. | first_instance_judgment.pdf para.122 |
| F53 | If the master placed exclusive reliance on the electronic display, that was negligent navigation; it did not convert the rejected electronic-chart carriage allegation into an additional seaworthiness finding. | first_instance_judgment.pdf paras.118-120 |
| F54 | A late third owner ground at the intermediate appeal was abandoned and received no decision. | court_of_appeal_judgment.pdf para.30 |
| F55 | Cargo's proposed Volcafe burden-of-proof challenge was not pursued at the intermediate appeal. | court_of_appeal_judgment.pdf paras.12, 31 |
| F56 | The intermediate court rejected cargo's alternative contention that the trial judgment established a separate failure of passage-planning system or culture. | court_of_appeal_judgment.pdf paras.31, 71 |
| F57 | The two owner grounds for which permission was granted both failed, producing dismissal of the intermediate appeal. | court_of_appeal_judgment.pdf paras.29, 72-76 |
| F58 | The approximately USD 800,000 litigated demand is an aggregate for the resisting respondent population, not the USD 9,826,980.60 cargo contribution in the historical allocation. | first_instance_judgment.pdf para.1; final_judgment.pdf para.20; general_average_adjustment.pdf p.95 |
| F59 | The decision record does not support blanket release of bonds or guarantees for other cargo interests; each instrument and account status remains to be established. | general_average_adjustment.pdf p.10; final_judgment.pdf paras.20-21, 146 |
| F60 | The issued adjustment and schedule should be retained as the historical quantum baseline despite the respondent collection bar. | general_average_adjustment.pdf pp.93-95; final_judgment.pdf paras.21, 146 |
| F61 | Each cash deposit, bond and guarantee requires account-by-account reconciliation to its governing instrument before any refund, release or demand. | general_average_adjustment.pdf pp.9-10; final_judgment.pdf paras.20-21, 146 |
| F62 | Vessel interests lodged salvage security on behalf of cargo so the laden voyage could continue without separate cargo salvage security; that fact does not prove cargo paid its later general-average contribution. | general_average_adjustment.pdf pp.7, 9 |
| F63 | Container interests supplied direct salvage security, a state separate from their general-average contribution and from the cargo security population. | general_average_adjustment.pdf pp.7, 9-10 |
| F64 | The common-safety timeline did not end every allowance at refloating: after refloating on 26 May the vessel remained at a safe anchorage for about two days while discharged bunkers were reloaded, then resumed the voyage on 28 May. | general_average_adjustment.pdf pp.6-7, 75-78 |
| F65 | The adjustment maps salvage to Rule VI, lightening and reshipping to Rule VIII, refuge and detention during bunker reloading to Rule XI, and other direct-consequence expenditure to Rule C or, for YAR 1994, Rule XI(d). | general_average_adjustment.pdf p.9 |
| F66 | Pollution measures began as a consequence of the accident but remained conditional for every refloating attempt because the hull condition was unknown; on that basis the adjuster admitted the entire period rather than excluding it as ordinary pollution response. | general_average_adjustment.pdf p.11 |
| F67 | The same pollution-prevention expenditure is routed differently by contract population: Rule XI(d) under YAR 1994, but Rules C and VI under YAR 1974/1990. | general_average_adjustment.pdf p.11 |
| F68 | Voucher B12 pollution-prevention expenditure of USD 264,705.06 is carried wholly to general average, with no remainder, consistently with the adjuster's causal note. | general_average_adjustment.pdf pp.73-74 |
| F69 | Voucher B6, USD 3,019.42 for reloading containers on the substitute vessel after refloating, is wholly admitted against reloading cost saved on the original vessel; the post-refloating date alone does not exclude it. | general_average_adjustment.pdf pp.69-70 |
| F70 | Voucher B5 applies the opposite post-refloating treatment: gross USD 20,866.30 splits into USD 13,910.87 remainder and USD 6,955.43 admitted because the later underwater survey belongs to the vessel's particular-average claim. | general_average_adjustment.pdf pp.69-70 |
| F71 | Voucher B9 crew-change and visa agency expense of USD 2,768.33 is wholly excluded even though it appears within the China expenditure sequence. | general_average_adjustment.pdf pp.71-72 |
| F72 | The D10 travel heading does not control every sub-trip: May 2011, July 2013 and February 2014 travel is wholly admitted, while June 2012 voucher D10b is split from gross USD 4,327.10 into USD 1,252.16 remainder and USD 3,074.94 admitted. | general_average_adjustment.pdf pp.85-88 |
| F73 | A6a Marseille-meeting travel is itself split: gross USD 15,035.72 divides into USD 5,011.91 remainder and USD 10,023.81 general average. | general_average_adjustment.pdf pp.63-64 |
| F74 | The A6 subitems do not share one treatment: London meetings of USD 3,294.59 and the February 2014 China meeting of USD 5,647.62 are admitted, while the China survey of USD 6,521.27 is wholly remainder. | general_average_adjustment.pdf pp.65-66 |
| F75 | A6 miscellaneous time and expense of USD 24,000 is divided into USD 12,000 remainder and USD 12,000 general average, whereas the USD 51,000 salvage bail fee is wholly admitted. | general_average_adjustment.pdf pp.65-66 |
| F76 | Section C is wholly admitted at USD 37,761.14 despite covering the post-refloating detention period: it combines two days of crew wages and maintenance with bunker and lube-oil consumption during refloating and detention while reloading bunkers. | general_average_adjustment.pdf pp.75-78, 89-90 |
| F77 | Payment and loss classification remain separate: vessel interests paid the salvage settlement that is allowed in general average, while hull underwriters reportedly settled the vessel's particular-average claim and permanent casualty repairs reduce vessel contributory value. | general_average_adjustment.pdf pp.11, 50-51 |
| F78 | The USD 173,591.67 premium for cargo salvage security is wholly admitted in the allowance ledger, but it remains a security cost rather than proof that the secured cargo interests paid their general-average contributions. | general_average_adjustment.pdf pp.65-66 |
| F79 | The bunker value bridge includes fuel discharged but not reloaded, deducts voyage consumption that would have occurred, and adds the bunker amount made good; physical absence at the end of the voyage does not by itself remove that interest from contribution. | general_average_adjustment.pdf p.50 |

## Allowance and value controls

The printed summary must be read across its three accounting columns, not down the
gross list alone. Section A closes at gross USD 10,310,794.05, remainder USD
107,530.81 and general average USD 10,203,263.24; section B at USD 1,158,590.22,
USD 16,679.20 and USD 1,141,911.02; section C at USD 37,761.14, zero and USD
37,761.14; and section D at USD 423,848.94, USD 1,252.16 and USD 422,596.78.
The combined roll-forward is therefore gross USD 11,930,994.35, remainder USD
125,462.17 and admitted principal USD 11,805,532.18. (general_average_adjustment.pdf
pp.89-90)

The next bridge uses the printed Rule XX base of USD 11,306,541.09 and commission
of USD 226,130.84. It does not apply 2% to either the gross ledger or the whole
admitted principal. Rule XXI then contributes USD 509,909.02 in the YAR 1974/1990
column and USD 711,848.06 in the YAR 1994 column, taking the respective pre-fee
subtotals to USD 12,541,572.04 and USD 12,743,511.08. The detailed date-and-base
calculations are identified as being in the adjusters' file and cannot be independently
re-performed from this workspace. The common USD 865,990.66 adjustment fees close
the two funds at USD 13,407,562.70 and USD 13,609,501.74. (general_average_adjustment.pdf
pp.89-92)

Three low-visibility voucher treatments explain part of the remainder column. B5
splits gross USD 20,866.30 into USD 13,910.87 remainder and USD 6,955.43 general
average because the surveys after refloating belong to the vessel's particular-average
claim. B9 crew-change and visa agency expense of USD 2,768.33 is wholly remainder.
D10b June 2012 travel splits gross USD 4,327.10 into USD 1,252.16 remainder and USD
3,074.94 general average. These printed column allocations control over the tempting
assumption that an invoice displayed in Schedule II was wholly admitted.
(general_average_adjustment.pdf pp.69-72, 85-86)

The salvage settlement was USD 9,500,000 all-in and the paid amount including bank
charges was USD 9,502,385.22; this sits in general-average expenditure. By contrast,
the USD 385,513 permanent casualty repairs were settled as particular average and
reduce the vessel's USD 120,000,000 sound value to USD 119,614,487. No vessel
sacrifice damage was confirmed, and the limited damaged container did not produce
cargo damage or a general-average allowance. These are express negative findings,
not missing rows. (general_average_adjustment.pdf pp.8, 10, 50-51)

The bunker calculation follows the property's disposition: USD 604,854.90 remained;
USD 1,306,320.40 was discharged and not reloaded; USD 266,214.20 of hypothetical
remainder-voyage consumption is deducted; and USD 30,734.90 made good is added. This
closes at USD 1,675,696.00. (general_average_adjustment.pdf p.50)

## Authority and conflict register

The owners' description of an uncharted shoal was a pleaded causal account, not a
judicial finding. The first-instance court instead found that the omitted warning about
unreliable depths made the passage plan defective and materially caused the master's
decision to leave the fairway. That factual platform was not challenged on the first
appeal. (general_average_adjustment.pdf p.6; first_instance_judgment.pdf paras.1-2,
124, 129; court_of_appeal_judgment.pdf para.3)

Several pleaded alternatives did not become operative findings. The trial court did not
find that the relevant Notice to Mariners was absent from the vessel, accepted that the
separate sounding corrections were marked, and rejected additional unseaworthiness based
on electronic-chart carriage, bridge management, master incompetence, or fatigue. It also
rejected contractual deviation, treating the temporary fairway departure as negligent
navigation. (first_instance_judgment.pdf paras.116-128)

At the intermediate appeal, two owner grounds were decided and failed; a late third was
abandoned. Cargo's proposed reversal of the conventional burden of proof was not pursued.
The alternative defective-working-chart route supported the result, but the alleged lack
of a proper system or culture was rejected. The trial dismissal, intermediate dismissal,
and final dismissal therefore form one procedural chain preserving the same respondent
collection outcome, not three account transactions. (court_of_appeal_judgment.pdf
paras.12, 29-31, 71-76; final_judgment.pdf paras.30, 33, 146)

## Liability chain and collection status

The required warning about unreliable depths outside the fairway was absent from both
the passage plan and working chart. The master then negligently left the buoyed fairway;
the plan defect was a real and effective cause of that decision and the grounding.
Applying the prudent-owner test, the defect rendered the vessel unseaworthy before the
voyage. Due diligence was not satisfied by delegating the planning work to competent
crew supplied with the necessary materials, because the carrier answers for want of
care in the work of making the vessel seaworthy. The navigation-and-management
exception cannot protect a causative breach of that prior duty. The court therefore
dismissed the owners' appeal. (final_judgment.pdf paras.11-18, 29-32, 144-146)

The judgment describes an approximately USD 13 million general-average claim, most
cargo interests having paid, and an approximately 8% resisting group facing a claim of
about USD 800,000. That procedural claim must not be confused with the adjustment's
USD 9,826,980.60 aggregate cargo contribution. Collection against the respondent group
is barred by the actionable-fault conclusion. (final_judgment.pdf paras.19-21, 146;
general_average_adjustment.pdf p.95)

## Recovery handoff and open items

The original cash-deposit call was 8%, well above the final blended rate of
2.67460000%. A deposit, bond or guarantee is security for a possible liability, not
proof of a final collectible debt. Stop collection of the dismissed respondent claim
and mark it non-recoverable, but retain the issued schedule for account reconciliation.
(general_average_adjustment.pdf pp.9, 95; final_judgment.pdf paras.20-21, 146)

No automatic refund or blanket security-release instruction can be derived for cargo
interests that paid or settled but were not the respondent group described in the
judgment. The workspace does not contain their individual account statements,
settlements, guarantee wording, limitation history, payment reservations or recourse
arrangements. Those matters remain unresolved and require account-by-account review
before money or security is released.

## Evidence-state audit

The adjustment's statement that payment evidence was seen or confirmed concerns the
disbursement accounts submitted and examined, with the adjusters' own fees excepted. It
does not prove that cargo interests paid their eventual contributions. Likewise, the
record that about 95% of consignments had been secured by late July, and later that all
but some low-value consolidated shipments were secured, establishes security status,
not cash settlement. (general_average_adjustment.pdf pp.7, 10-11)

The 8% deposit call is a percentage of contributing value requested as security. The
judgment's approximately 8% is a population of cargo interests said to have refused
payment, associated with an approximately USD 800,000 claim. These coincidentally
similar percentages have different denominators and must not be equated with each
other or with the USD 9,826,980.60 aggregate cargo contribution. The procedural
aggregates also do not identify respondent membership or exact account amounts.
(general_average_adjustment.pdf pp.10, 95; final_judgment.pdf para.20)

Average Bonds and Guarantees are described as standard forms incorporating a
Non-Separation-Agreement, and the adjustment fees describe administration of a
dedicated trust account for cash deposits. The supplied record does not provide a
current instrument register, trust-account balance, beneficial-entitlement ledger, or
account-level release/refund status. Security-collection and adjustment-administration
costs therefore remain in the historical issued ledger; the appellate dismissal does
not itself direct a revised adjustment, blanket refund, or release for other interests.
(general_average_adjustment.pdf pp.10, 83-92; final_judgment.pdf para.146)

Commission reconciliation: the printed base USD 11,306,541.09 × 2% rounds to USD 226,130.82; the adjustment prints USD 226,130.84, a USD 0.02 excess. Preserve the printed bridge pending clarification; do not silently replace the printed amount or manufacture another base (general_average_adjustment.pdf pp.89–90).
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    sources = {name: args.workspace / name for name in SOURCE_HASHES}
    for name, expected in SOURCE_HASHES.items():
        if not sources[name].is_file() or sha256(sources[name]) != expected:
            raise RuntimeError(f"unexpected or missing source record: {name}")

    adjustment = extract_text(sources["general_average_adjustment.pdf"])
    first_instance = extract_text(sources["first_instance_judgment.pdf"])
    intermediate_appeal = extract_text(sources["court_of_appeal_judgment.pdf"])
    judgment = extract_text(sources["final_judgment.pdf"])
    require(
        adjustment,
        [
            "Contributory Value of the Vessel",
            "119.614.487,00",
            "Contributory Value of the Cargo",
            "367.418.702,00",
            "14.315.119,00",
            "1.675.696,00",
            "13.453.880,01",
            "2,67460000",
            "125.462,17",
            "11.805.532,18",
            "11.306.541,09",
            "12.541.572,04",
            "12.743.511,08",
            "865.990,66",
            "Cash Deposits set at 8%",
            "payment of all accounts has been effected",
            "maintaining a dedicated trust account for cash deposits",
            "no sacrifice damages were sustained by the vessel",
        ],
        "general_average_adjustment.pdf",
    )
    require(
        first_instance,
        [
            "Owners say that the cause of the casualty was an uncharted shoal",
            "conventional view as to the burden of proof remains good law",
            "There was no unseaworthiness in this regard",
            "unable to accept that in 2011 the vessel",
            "improbable that he was incompetent",
            "doubt that he was so tired that it materially affected",
            "there was no radical change of voyage",
            "grounding of the vessel was caused by the actionable fault of the Owners",
        ],
        "first_instance_judgment.pdf",
    )
    require(
        intermediate_appeal,
        [
            "essential factual background is set out at [9] to [43] of the judgment and is not challenged on appeal",
            "two grounds of appeal advanced by the Owners",
            "abandoned that ground",
            "argument was not pursued",
            "reject the second ground of the Respondents’ Notice",
            "both grounds of appeal fail and the appeal must be dismissed",
        ],
        "court_of_appeal_judgment.pdf",
    )
    require(
        judgment,
        [
            "not entitled to recover general average contributions",
            "actionable fault",
            "defective passage plan",
            "real and effective cause of the grounding",
            "cannot escape from its responsibilities",
            "I would dismiss the appeal",
        ],
        "final_judgment.pdf",
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "general_average_review.md").write_text(MEMO, encoding="utf-8")
    write_schedule(args.output_dir / "general_average_schedule.csv")
    print(args.output_dir / "general_average_review.md")
    print(args.output_dir / "general_average_schedule.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

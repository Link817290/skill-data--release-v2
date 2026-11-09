---
name: audit-capital-expansion-screen
description: Review capital-intensive manufacturers for expansion quality, financing support, investment efficiency, and profit quality. Use when the analysis must distinguish organic from acquired growth, handle missing evidence explicitly, and support each company-level judgment from structured financial statements.
---

# Capital-Expansion Screen Review

## Scope

Use this skill for an audit worksheet covering capital-intensive listed
companies when expansion has to be judged from the statements rather than from
management narrative. The framework names the ratios; the analyst still has to
define their interpretation and document each company-level judgment.

It is not intended for mature consumer, light-asset, or technology-compounder
screens.

## Evidential restraint

Specific conclusions are useful only when the available evidence supports them.
In this screen, a proxy grade may be more accurate than a causal claim,
`REVIEW` may be more accurate than an inferred zero, and two conflicting readings
may need to remain separate. The worksheet should make those limits visible.

## Organic vs acquisition-driven expansion

The auxiliary indicator is goodwill / net assets. **The tell is the goodwill
*trajectory during the window*, not its level.** Goodwill rises only through
business combinations, so:

- Read each window year's *change* in goodwill, not the endpoint. A jump in any
  window year is a balance-trajectory acquisition signal *for that year*. It
  supports the task's `ACQUISITION_DRIVEN` window classification, but is not
  causal proof of a specific transaction when no binding filing was supplied.
- A high-but-flat goodwill balance is a *historical* acquisition and is
  organic for this window — do not let a large level fool you into
  `ACQUISITION_DRIVEN`.
- Impairment can mask a same-year acquisition (a purchase and a write-down net to a
  flat balance). A year-over-year rise net of impairment still means an acquisition.
- Date the combination from the year-by-year goodwill balances in the window. A
  balance already in place at the window's first year and merely carried forward is
  *not* window-driven. Where the year-over-year change sits at the boundary and the
  balance trajectory cannot date it, the input the call needs is missing: hold the
  cell at `REVIEW` under the three-state discipline of Judgment 4 rather than
  inferring a year.

Cite the source id and fiscal year of every goodwill and net-asset balance you read.

## Construction-in-progress and investment efficiency

Investment efficiency is revenue / fixed assets, and the denominator is the
**ending** fixed-asset balance, never a period average. Construction-in-progress
(CIP) is capital not yet productive and sits outside fixed assets, so a large CIP
makes the ending-denominator ratio read *better* than the deployed asset base
warrants.

Test materiality by consequence, not by a raw cutoff: fold CIP into the
denominator and see whether the efficiency gate flips. Compute revenue / fixed
assets and revenue / (fixed assets + CIP); if they fall on opposite sides of the
efficiency threshold in any window year, CIP distorts that company's efficiency
call. Report both ratios and the affected years. (Efficiency thresholds and the two
profile readings are in `references/formula-profiles.md`.)

## Borrowing and capital expenditure

Strong cash-coverage of interest-bearing debt, a simultaneous borrowing inflow, and
positive capex are co-movement. Co-movement never proves that the borrowing
funded the capital expenditure.

- Only co-movement available → `QUANTITATIVE_PROXY_ONLY`.
- A filing that explicitly binds a specific borrowing / bond issue to a named
  construction project → `CAUSAL_FILING_STATED` (cite the source id).
- A binding input missing → `REVIEW`.

Equity raises and convertible-bond project fundraising are **not** borrowing use;
exclude them from this judgment even when they flow through a "使用募集资金" project
table.

## Three evidence states

- A disclosed number, **including a disclosed 0**, is a fact.
- A **standardized null** reproduces a zero balance for a non-reported line item; it
  is a reproduction convention, not an independently disclosed fact.
- An **absent** field, year or statement is missing evidence and holds the cell at
  `REVIEW`.

Turning an absence into a zero manufactures a conclusion the filings do not support.
A disclosed zero and an absent key look similar and must be called differently.

## Signed profit denominator

When net profit is negative in a scored year, the operating-cash-flow / net-profit
ratio loses its usual meaning because the denominator is negative. The narrative
profile keeps the signed ratio; the strict reading rejects it. These two
treatments **disagree**, and both must be reported — do not pick one silently.

## Irreconcilable readings

The method is read two ways (see `references/formula-profiles.md`). Where the two
readings, or a narrative statement and a reported figure, cannot both be true, state
**both** and why they do not reconcile. Never merge them into one number or choose
one and drop the other.

## Working record and source boundary

Work only from the candidate universe, the structured statements shipped in this
workspace, and the supplied figure — never reconstruct a published table. Attach
source id (the snapshot's `official_audit_source_ids`), fiscal year, scope, unit and
raw value to every material fact. Where the structured mirror is internally
inconsistent, revise the input and everything downstream of it. Hold the historical
cutoff fixed; do not browse. All arithmetic and every conclusion are yours.

## References

- `references/formula-profiles.md` — efficiency/coverage thresholds, the two readings, and the verdict-count check to run before saving
- `references/expansion-and-debt.md` — co-movement vs causal debt purpose
- `references/investment-efficiency.md` — CIP distortion, ending denominator
- `references/acquisition-vs-organic.md` — goodwill trajectory, dating a combination from the window balances
- `references/evidence-and-missing-data.md` — three-state discipline, citation

---
name: review-sec-reserve-disclosures
description: Review an upstream oil and gas filing package for internally inconsistent reserve quantities, unsupported movement classifications, incomplete development-plan or technology disclosures, mismatched engineer scope, and incompatible valuation bases. Use when annual reports, reserve roll-forwards, standardized-measure tables, engineer reports, or investor releases must be reconciled into an evidence-bound exception memo.
---

# Review SEC Reserve Disclosures

## Purpose

Turn a filing package into a defensible exception record. The central discipline is
to distinguish four different questions that are often collapsed:

- Does each displayed bridge add arithmetically?
- Does each movement carry the right economic meaning and sign?
- Do product, geography, development-status, and value layers describe the same event?
- Does the prose support the classification and reporting basis shown in the tables?

A bridge can answer the first question and still fail the other three. Do not treat
a correct ending balance as proof that the movement categories are correct.

This skill supports disclosure review, not subsurface estimation. Do not invent field
volumes, production profiles, cash flows, or legal conclusions that are absent from
the supplied record.

## Start With an Evidence Ledger

Inventory every supplied document before forming conclusions. Record its role, date,
measurement basis, scope, and expected downstream use. Typical roles include:

- issuer annual report and supplemental reserve tables;
- independent engineer opinion or evaluation exhibit;
- earnings release or investor summary;
- acquisition disclosure and property narrative;
- accounting table for discounted future net cash flows.

For each source, note whether it is management's disclosure, an evaluator's estimate,
a definition, or a promotional summary. Those are not interchangeable evidence tiers.
An evaluator exhibit may support quantities and methods within its stated property
scope, while management remains responsible for the issuer-level disclosure.

Keep locators while reading. A useful locator names the document and a section, table,
caption, or distinctive nearby passage. Bare page numbers are fragile in HTML filings;
bare filenames force the reviewer to repeat the search.

For difficult HTML, use the bundled extractor to make a temporary search view:

```bash
python scripts/extract_filing_text.py input.htm --find 'reserve|standardized measure' --context 4
```

The script only exposes source text with stable paragraph numbers. It does not classify
movements or produce review conclusions.

## Build the Quantity Model Before Judging Prose

Create a private movement matrix at the most granular level the package supports.
Useful axes are reporting period, geography, product, reserve class, and development
status. Preserve the source units and printed signs. Treat parentheses as negative and
do not silently turn a dash into zero.

For every roll-forward, calculate an independent closure:

```text
opening balance + signed movements = ending balance
```

Record the residual rather than merely marking pass or fail. Rounding-sized residuals
and category-sized residuals require different treatment.

Then test category semantics. Production and sales ordinarily reduce reserves.
Purchases require an acquired interest. Extensions and discoveries describe additions,
not an unexplained negative plug. Revisions may move either way, but their narrative
should identify the information or economics that changed. A sign/category anomaly is
still an exception when the row has been made to add.

Read [references/movement-category-controls.md](references/movement-category-controls.md)
before reconciling multiple products or periods. It contains the cross-layer tests and
false-positive controls that a single-table tie-out misses.

## Reconcile Across Reporting Layers

Work outward from the granular matrix. Apply the issuer's disclosed equivalence factors
only after retaining native product units. Keep enough precision to explain rounding.
Compare the independently converted sum with the reported equivalent-barrel layer.

Use a dependency chain for each material movement:

```text
product and geography tables
        -> equivalent-unit summary
        -> developed/undeveloped subset
        -> movement narrative
        -> discounted-cash-flow change table
        -> external-facing summary
```

At each arrow, ask whether both magnitude and category survive. Do not compare only
ending totals. A category swap may preserve the total in every layer while changing the
meaning of reserve replacement, organic additions, or acquisition performance.

Check adjacent periods as well as the current period. A prior-period summary can carry
a classification error that affects trend claims even when the current-period bridge is
clean. If a product-layer movement converts to one category while the equivalent-unit
summary records the same magnitude in another, document the swap and preserve the
unchanged ending total.

## Control Downstream Value Claims

Reserve-quantity movements and the standardized measure are related, but not through a
simple volume-times-price formula. Property-specific timing, price differentials,
operating costs, development costs, taxes, and discounting affect the value categories.

When an upstream movement category is unreliable:

1. identify the downstream value categories potentially affected;
2. state whether the ending standardized measure itself is challenged;
3. determine whether the package contains property-level cash-flow support for a
   corrected allocation;
4. if it does not, request a rerun or reconciliation and leave the monetary correction
   unresolved.

Never manufacture a dollar reclassification by applying a portfolio average value per
barrel. That creates false precision and can misstate both timing and tax effects.

## Test Undeveloped-Reserve Support

Separate an issuer's policy statement from evidence about the current population of
undeveloped reserves. A definition of the governing rule, a statement about historical
annual review, or a general risk factor does not by itself demonstrate that every
current location is covered by an adopted development plan.

Look for evidence that the year-end population is scheduled within the required period
from initial booking, that approvals and capital allocation are addressed, and that any
longer-lived exceptions are identified and supported. The usual SEC horizon is five
years, but the key audit object is the location-level aging and plan evidence, not a
sentence repeating the horizon.

If that evidence is missing, do not declare the reserves invalid. Frame a targeted
request for the booking-date roll-forward, current approved plan, expected conversion
date, delay history, and exception rationale. Distinguish an incomplete disclosure from
a proved violation.

## Test Technology Disclosure at the Right Level

Reliable technology review has three layers:

- a definition says what could qualify;
- a data-input list says what information was available;
- an applied-method discussion says what was actually used to establish reasonable
  certainty for material additions or reserve classes.

Only the third directly answers the disclosure question. Engineering exhibits can
provide useful evidence of performance analysis, volumetric work, analogy, simulation,
or other methods within their evaluated scope. They may mitigate an issuer-level gap,
but do not automatically replace management's general discussion in the filing.

Assess whether the applied methods are connected to the material reserve changes and
whether the evaluator's stated scope covers the population being discussed. Avoid a
checklist of technology names divorced from the additions they support.

Read [references/disclosure-boundary-controls.md](references/disclosure-boundary-controls.md)
for the development-plan, engineer-reliance, technology, price, and competing-basis
boundaries.

## Reconcile Independent Engineer Coverage

For each engineer report, capture:

- properties and geography evaluated;
- effective and completion dates;
- gross, net, royalty, and tax treatment;
- reserve categories included or excluded;
- native units and conversion basis;
- whether the work is an estimate, evaluation, review, or audit;
- management-supplied inputs accepted without independent verification.

Recalculate issuer coverage from the engineer summaries using the issuer's conversion
factors. If the rounded sum agrees with the issuer's ending total, clear the ending
quantity only within the reports' stated scopes. Do not upgrade an independent
evaluation into an audit of management's controls or representations.

Differences between reference prices and property-adjusted prices are not automatically
errors. Quality, transportation, location, marketing, and contractual adjustments may
be expected. Clear such an apparent mismatch only when the report identifies the
adjustment basis and holds the resulting assumptions consistently.

## Separate Competing Reserve and Value Bases

Investor materials often place several measures near one another. Before comparing
them, label all basis dimensions:

- proved only versus proved-plus-probable;
- SEC definitions versus another resource-management framework;
- net entitlement versus working interest before royalties;
- constant historical-average pricing versus escalated management assumptions;
- standardized measure versus a non-GAAP discounted value;
- treatment of taxes and abandonment obligations.

Two figures that share a discount rate can still be incomparable. Do not reconcile one
to another unless the package supplies a bridge over reserve class, ownership basis,
price, cost, timing, and tax differences. Preserve issuer-specific qualifications: a
label's usual industry meaning does not override an explicit definition in the source.

## Write the Exception Record

One row should represent one decision-ready matter, not one keyword hit. Make each row
self-contained:

- the proposition being assessed;
- source-bound evidence with quantities and units where available;
- the cross-source analysis;
- the narrow disposition warranted by the record;
- a concrete owner action or clearance rationale.

Use dispositions that communicate whether text or classification must change, the
conclusion needs qualification, the apparent issue is cleared, or evidence is still
needed. Do not let the label carry reasoning that is absent from the row.

In the memo, lead with filing readiness and the matters that can change reported
meaning. Keep cleared false positives visible when they concern a large balance or a
tempting comparison; this prevents another reviewer from reopening them without new
evidence. Cross-reference the register so the memo and working record cannot drift.

## Back-Revision and Stop Conditions

After adding or changing any matter, rerun these checks:

- every quantity relationship uses stated units and signs;
- every conclusion is supported by at least one precise locator;
- every cross-document claim names both sides of the comparison;
- every monetary conclusion respects the available cash-flow detail;
- every engineer conclusion preserves scope and reliance limitations;
- every apparent inconsistency that was cleared states why;
- memo conclusions and register dispositions agree.

Stop and request evidence rather than infer when a correction depends on unavailable
property-level schedules, booking dates, approval records, or cash-flow models. The
review is complete when each material matter has either a supported correction, a
bounded qualification, a documented clearance, or an explicit evidence request.

## Common Failure Modes

- Accepting bridge closure as category validation.
- Checking only the latest period and missing a prior-period category swap.
- Converting gas with a habitual factor instead of the issuer's disclosed factor.
- Using reserve volume to fabricate a standardized-measure reclassification.
- Treating a glossary definition as an applied-technology discussion.
- Treating an engineer report as broader or more independent than its wording permits.
- Calling every price difference an error without testing property adjustments.
- Comparing reserve frameworks because the figures sit in the same release.
- Declaring noncompliance where the record supports only an evidence request.
- Omitting cleared high-risk apparent issues from the final record.

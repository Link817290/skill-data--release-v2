---
name: service-quality-reporting
description: Reconcile contact-quality reviews, operational volume bases and feedback workloads into auditable management reports with correct scopes, exceptions and chart bindings.
---

# Service quality reporting

## Establish the accounting units

Inventory each input table before aggregating. Identify the contact key, employee,
team, supervisor, quality reviewer, analysis reviewer, event date and review date.
Write down what one row represents. Determine whether tables are overlapping
snapshots or independent feeds by comparing actual record keys and dates.
Repeated employee names can be different contacts; overlapping snapshots can
repeat the same contact. Do not solve either problem by deduplicating names.

## Preserve the adopted score and exception state

Inspect both formulas and stored results. Distinguish finalized outcomes from
incomplete scoring inputs and from ordinary non-applicable items. A manually
adopted exception can remain valid even when an automatic denominator is missing.
Find the governing reporting policy before recomputing historic scores. Avoid
refreshing external links that belong to an unrelated personnel register.

## Aggregate on explicit dimensions

For each metric, name its population, date dimension, subject, numerator,
denominator and unit. Compute rates from counts before rounding. Do not average
group percentages when contact-weighted attainment is required. Bind operational
bases to team identifiers and their stated scope; never align unrelated tables
by row position. Keep unknown denominator provenance visible.

When comparing periods, join on stable team identity. Reorder only after joining.
Verify that the report's current-period comparison agrees with its current-period
ranking, while the earlier-period values use only their own records.

## Keep feedback status and work performed separate

Validity of customer feedback is not the same as whether an analyst performed
the review. Follow the requested population for cause distributions and the
requested reviewer/date for workload. Do not substitute customer event time for
analysis time. Reconcile cause subtotals with all analyzed cases and preserve
authoritative categories unless the assignment calls for a fresh classification.

## Ground escalations

Link each serious incident to its actual contact, employee, team, score and
observed failure. Separate factual observations, risk implications and proposed
actions. Recommend checks or coaching that address the observed failure; do not
claim that a correction, approval or verification has already happened.

## Close the workbook

Cross-check record counts across overlapping views, by-team metrics against
independently grouped records, feedback totals against the case ledger, and QA
totals against the constituent work streams. Keep diagnostic calculations outside
the formally adopted tables if they use different assumptions.

Create native charts from the final tables. Check category labels, series ranges,
unit formats and period bindings after sorting or inserting rows. Exclude helper
columns and blank series. Reopen the saved workbook and verify the actual numeric
values or formula caches, not only the script that wrote it.

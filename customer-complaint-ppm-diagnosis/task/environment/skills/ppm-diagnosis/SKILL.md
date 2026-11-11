---
name: ppm-diagnosis
description: Diagnose complaint-rate statistics by reconciling counts, exposure denominators, reported rates and period scope.
---

# Complaint-rate diagnosis

Use this method when monthly or product statistics must become a diagnosis
workbook. Follow the task's public output contract for filenames and layout.

## Establish the population

Identify periods, product groups, sales or exposure counts, complaint counts,
reported rates and summary cells from the source labels. Preserve the distinction
between a missing observation and an observed zero. Determine whether the groups
are mutually exclusive before adding their counts.

Read [references/ppm-arithmetic.md](references/ppm-arithmetic.md) before calculating
rates or reconciling an existing rate column. Prefer explicit counts and their
matching denominators to reconstruction from a rounded rate. Preserve both the
reported value and the recomputed value when they disagree, and locate the source
of the discrepancy without modifying the input.

## Aggregate with the correct denominator

Read [references/product-decomposition.md](references/product-decomposition.md)
when comparing products or combining periods. Match each product's complaints to
that product's sales. A shared denominator is valid only when the source defines
that statistic as a contribution to the overall rate.

Reconcile group sales and complaints to the overall totals over the same period.
Record gaps, overlaps and unreconciled differences. Do not force agreement by
changing counts or silently excluding inconvenient rows.

## Interpret and close

Read [references/trend-reading.md](references/trend-reading.md) when describing
movement or priorities. Separate complaint volume, complaint rate and severity.
An unsupported causal explanation must remain unresolved, even when an arithmetic
pattern is clear.

Reopen the workbook and check that every displayed total, share and comparison
uses the same adopted scope and that important discrepancies remain visible.
Identify the actual input workbook; never copy metadata from an unavailable report.

## Boundary and stopping checks

Keep the unit of counting explicit: complaints are not automatically defective
units, and sales exposure does not prove production-cohort alignment. Do not
infer deduplication rules from an aggregate total. If the input does not define
these relationships, preserve that limitation instead of silently redefining
the statistic.

For a justified follow-up, select the observed high-rate or high-burden cases
and retain a comparable low-rate period as a contrast. State what additional
case classification, impact, ownership and closure evidence would distinguish
possible explanations. A proposed investigation is not a completed action.

Stop an affected calculation when its numerator, denominator or population
membership is unresolved. A familiar product label, a formatted rate or an
unavailable benchmark cannot replace the missing evidence. Retain independently
supported results and identify the exact scope of the unresolved conclusion.

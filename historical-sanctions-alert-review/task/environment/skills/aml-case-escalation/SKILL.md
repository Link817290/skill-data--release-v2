---
name: aml-case-escalation
description: Review grouped transaction records for AML escalation by preserving case provenance, avoiding double counting, testing activity patterns cautiously, and documenting evidence gaps and next actions. Use for correspondent-banking lookbacks, transaction-monitoring cases, and mixed individual or aggregate payment records.
---

# AML case escalation

## Work from case-bound facts

1. Start from the supplied output template and write completed cases as you go.
2. Group rows by the stable case or filing identifier before interpreting activity. Never borrow a transaction from another group because it resembles the pattern.
3. Record each row's grain: individual transfer, aggregate over a period, subtotal, or unknown.
4. Build directed edges with `source row | originator | beneficiary | date or range | count | amount | grain`.
5. Evaluate patterns, limitations, and next actions at the case level.
6. Derive queue-level controls from the finished case table and validate all affected-record sets.

Sanctions and AML are parallel tracks. Import only verified party, date, geography, and legal-state facts. A true sanctions match does not prove illicit activity; a false or pre-effective match does not make the transactions ordinary.

## Preserve record grain

A date range is not a component value date. A blank count is unknown, not one. Before adding values, compare case identifiers, parties, direction, periods, counts, and source rows. If two aggregates may overlap or disjointness is not stated, do not present their sum as exposure. Describe the observed rows and request transaction-level identifiers.

## Test patterns without overstating them

- Reciprocal or flow-through activity: compare direction, timing, parties, and amounts. Treat bank-level reciprocity as a review lead unless customer, account, payment-message, and source-of-funds evidence links the flows.
- Bursts or repeated payments: describe count, concentration, counterparties, and window using only disjoint records. Escalate when the supported combination warrants review; do not invent a purpose.
- Threshold-looking amounts: do not call structuring without an applicable threshold, currency, common customer or account, meaningful timing, and relevant transaction type. Request those facts.
- Large or round values: treat them as context, not proof by themselves.

Use calibrated conclusions: `warrants enhanced review`, `is consistent with`, `cannot establish`, or `is inconclusive pending`. Avoid `proves laundering`, `definitely suspicious`, and `definitely clean` unless direct supplied evidence supports that strength.

## Write a complete case rationale

For every case, include:

1. the stable case identifier and case-owned source rows;
2. the observed activity in neutral language;
3. why the combination matters;
4. the inference limit or plausible missing context;
5. the current outcome; and
6. the smallest information request that would change or finalize it.

Useful requests include underlying transaction IDs, component value dates, payment messages, ordering-customer and beneficiary identifiers, account linkage, currency, purpose, invoices, customer profile, and source of funds. Phrase absence as `not supplied`, not `does not exist`.

## Close queue-level controls

Each control must name the full affected-case set, common observation, inference limit, current action, and resolving evidence. Compare the queue along separate axes:

- possible overlap or double counting;
- institution-level opposite-direction flows;
- repeated small-payment patterns versus superficially round but unrelated values;
- AML outcomes that must remain independent of sanctions dispositions.

The same case may enter several controls because these are different dependencies. Do not merge them into one adverse label. Reconcile each control back to case-level rows and remove extra or missing identifiers.

## Final checks

Reject cross-case row mixing, unsupported sums, customer linkage inferred from banks alone, structuring without threshold support, prior-alert status used as proof, and sanctions outcomes copied into AML conclusions. Confirm every template entry is nonempty, source references identify files and rows, the executive summary matches case decisions, and the saved deliverable parses as valid JSON.

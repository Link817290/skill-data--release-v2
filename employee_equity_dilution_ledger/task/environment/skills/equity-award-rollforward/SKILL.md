---
name: equity-award-rollforward
description: Reconstruct employee equity award populations from filing disclosures, normalize units and award states, and close a source-bound roll-forward before building an analysis workbook.
---

# Equity award roll-forward

Use this skill when a filing presents equity awards in several tables (for example, an annual-note roll-forward, an equity-plan summary, and an executive compensation table). The objective is a defensible population ledger, not a transcription dump.

## 1. Establish the source hierarchy

1. Identify the reporting date, fiscal period, and whether each table is an aggregate disclosure, a plan-capacity disclosure, or a named-person disclosure.
2. Treat a table's own unit label as binding. Keep exact shares separate from values reported in millions; record the scale explicitly in the input sheet.
3. Prefer the table that describes an event population for event counts, and use the plan-summary table for capacity and maximum-issuance facts. Do not silently replace an aggregate number with a named-person subtotal.
4. Record a short source locator in the workbook (document name plus page, section, or HTML heading) so a reviewer can re-open the supplied material.

## 2. Normalize award states

1. Use distinct state columns for beginning balance, grants, exercises or settlements, vesting, forfeitures, expirations, and ending balance. A negative movement should remain negative in the ledger even when the filing prints parentheses.
2. Keep award classes separate: options, time-based RSUs, and performance-based units have different share and dilution semantics.
3. Preserve target units and maximum eligible units as separate facts for performance awards. A maximum-payout footnote is not a second grant and must not be added twice.
4. Keep stock-plan capacity separate from outstanding awards. Available-for-future-issuance is not an unvested balance.

## 3. Close the roll-forward

1. Calculate `begin + grants + other additions - exercises/vests - forfeitures - expirations` for every class and compare it with the disclosed ending balance.
2. When the filing gives both a detailed named-person table and an aggregate table, calculate a residual population explicitly. Label it as a reconciliation residual rather than presenting it as a person.
3. Flag unexplained differences, scale mismatches, and date mismatches in a Checks sheet. A zero residual is evidence; a blank check is not.
4. Keep formulas in the workbook for roll-forward arithmetic and link them to the Inputs and ledger sheets. Hard-coded totals are acceptable only for copied source facts, never for derived balances.

## 4. Evidence and review controls

- Read the PDF table visually or with a layout-preserving extractor before trusting a text stream; column order can change when a table spans pages.
- Check that footnotes about net exercise, tax withholding, divestitures, and performance multipliers are carried into Notes or assumptions.
- Recompute each ending balance independently from the ledger and compare it with the source. Use a visible PASS/FAIL status and an absolute difference.
- Do not infer a missing award class from a generic phrase such as “equity awards.” If a class is not quantified, record the omission and do not manufacture a number.

## 5. Reusable workflow

1. Inventory the supplied files and extract only the relevant table regions.
2. Build an input register with raw values, units, dates, and locators.
3. Populate event rows and derive ending balances with formulas.
4. Reconcile aggregate activity to named-person activity and retain the residual.
5. Run the roll-forward controls before handing the workbook to the dilution analyst.

The bundled `scripts/check_rollforward.py` can be run against a user-prepared CSV to report arithmetic differences. It is a checker only and does not fill the ledger.

The skill does not choose company-specific thresholds or supply answer values. It supplies the reasoning discipline needed to discover them from the supplied materials.

For the compact capture checklist used while reading crowded tables, see `references/filing-table-controls.md`.

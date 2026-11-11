---
name: dilution-ledger-controls
description: Convert an equity award ledger into a transparent potential-dilution and exercise analysis with treasury-stock logic, performance-award scenarios, and workbook-level controls.
---

# Dilution and exercise ledger controls

Use this skill after award populations have been normalized. It keeps dilution mechanics, cash proceeds, and plan-capacity usage on separate evidence-backed paths.

## 1. Define the denominator and valuation date

1. Select the disclosed share denominator that matches the requested period and write its unit scale next to the value.
2. Select the market price for the same valuation date from the supplied material. Do not combine a closing price from one date with an award balance from another without labelling the scenario.
3. Keep a scenario row for the base case and, when performance awards have a disclosed payout range, a separate maximum case. Do not overwrite the base population with the maximum.

## 2. Apply instrument-specific dilution logic

1. For options and similar rights, include incremental shares only when the market price exceeds the exercise price. Use the treasury-stock approach: gross shares less the shares that could be repurchased with exercise proceeds.
2. For full-value awards such as time-based RSUs, treat the unvested shares as potential shares when the scenario assumes vesting.
3. For performance units, multiply target units by the disclosed maximum or performance factor only in the maximum scenario. Keep target and maximum columns visible.
4. Do not apply an exercise price to RSUs or PSUs; the weighted-average option exercise price in a plan table does not describe full-value awards.

## 3. Reconcile exercises and proceeds

1. Sum named-person option exercises from the proxy table and compare that subtotal with the aggregate option-exercise count in the annual note.
2. Carry the residual as an “other employees / unassigned aggregate” row. Do not force the named-person subtotal to equal the aggregate when the source populations differ.
3. Keep shares acquired, value realized, cash proceeds, and intrinsic value as different measures. Net exercise and tax withholding can make issued shares differ from gross exercise events.
4. Add a check that the ledger subtotal plus residual equals the aggregate disclosure, with a visible tolerance and status.

## 4. Model plan-pool usage

1. Start with the disclosed available balance at the reporting date.
2. Apply the plan's share-counting multipliers to grants or awards as described in the supplied plan footnote. A multiplier is a pool-consumption rule, not a dilution factor.
3. Track options/SSARs, full-value awards, and cash-only awards separately when the plan distinguishes their pool treatment.
4. Do not treat canceled or forfeited awards as automatically available unless the plan text explicitly returns them to the pool; record the rule in assumptions.

## 5. Build the workbook and controls

- Put raw facts on Inputs, event rows on the ledger sheets, and formula-driven outputs on Dilution_Summary.
- Every derived metric should point to an input or ledger cell on another sheet. Use formulas that a reviewer can inspect, not a pasted scalar.
- Show both share counts and dilution percentages, with units in the header. Include checks for option roll-forward, RSU roll-forward, PSU roll-forward, exercise reconciliation, and denominator consistency.
- Make the workbook readable without the source files: include source locators and notes, but do not copy whole filing pages into the workbook.

## 6. Review before delivery

1. Recalculate using an independent hand calculation or a small script.
2. Inspect formulas for accidental text values, hard-coded answer constants, and references to the wrong year.
3. Confirm that target and maximum scenarios are not added together and that the base denominator is not diluted twice.
4. Confirm all controls show PASS (or an explicitly explained non-applicable state) and that the workbook opens cleanly.

The bundled `scripts/audit_workbook_formulas.py` reports formula and cross-sheet-reference coverage for a user-supplied workbook; it does not calculate or populate any result.

This skill provides reusable mechanics and review checks. It does not contain task-specific source values or a completed answer.

For a compact treasury-stock and pool-capacity reference, see `references/treasury-stock-and-pool.md`.

---
name: xlsx-formula-audit
description: Audit an engineering review workbook for formula lineage, cross-sheet closure, unit visibility, controlled findings and delivery integrity.
---

# XLSX formula audit

## Trigger and boundary

Use this skill when the requested engineering review must be delivered as a usable Excel workbook. Apply it after the engineering calculations have been drafted and again before delivery. It checks the workbook as an artifact; it does not solve the member, validate a code clause, or replace a domain review.

## Business steps

1. **Map the workbook contract.** Enumerate sheets, identify the input/evidence, action, flexure, shear, finding and summary sections, and record the intended data flow. Treat a sheet with only pasted results as an output, not as a calculation section.
2. **Inspect formula lineage.** For each result cell, verify that a formula is present and that it references the appropriate input or upstream calculation sheet. Check for accidental external links, hidden constants, circular references, and formulas that point at a label instead of a numeric cell.
3. **Audit units and state.** Confirm that values have unit labels and that formulas make conversions visible. Check that factored/unfactored, nominal/design, required/provided and flexural/shear states are not merged in one unlabeled column.
4. **Audit finding controls.** Confirm that every calculation branch has a finding id, controlled status, source locator, calculation reference and rationale. Ensure a superseded branch is not overwritten by the branch that replaced it and that a check whose dependency is unresolved is not forced into a binary status.
5. **Run closure and usability checks.** Recount evidence rows and findings, compare the summary disposition with the register, recalculate with a spreadsheet engine when available, and inspect for broken formulas or unreadable sheets. Keep the original source unchanged.
6. **Package the deliverable.** Save only the requested workbook at the exact path, remove scratch exports from the deliverable directory, and perform one final read-back of formulas and values. If a check cannot be recalculated, disclose the limitation in the workbook rather than claiming a pass.

## Formula and layout rules

- Inputs may be hard-coded only in the evidence/input section and must have source locators. Derived action, capacity, ratio and status-support cells should be formulas or clearly marked professional judgments with a calculation reference.
- Prefer direct cell references across sheets to duplicated constants. A formula that repeats a number from the source without linking the input row is not traceable.
- Use a stable header row and controlled status vocabulary, but accept equivalent names and ordering when the semantic roles are clear.
- Preserve source precision in an evidence column and use a separate rounded display column. Do not alter the raw HTML material to make formulas easier to read.
- Avoid macros, external workbook links, volatile web functions, and hidden worksheets. The workbook must open offline.

## Dependencies and revision triggers

The contract map precedes formula inspection. Unit/state auditing follows lineage because a formula's meaning depends on its operands. Findings and summary closure follow calculations. If any input row, formula, or sheet is changed after the first audit, rerun lineage and closure checks; a cosmetic edit that changes a referenced coordinate is not cosmetic.

## Artifact contract

The delivered workbook contains visible input evidence, formula-bearing calculation sections, and a finding register whose rows can be followed back to both a source locator and a calculation row. It must remain usable when opened without network access and must contain no external link dependencies.

## Failure branches

- If formulas are not recalculated by the available engine, keep formulas and add a visible `recalculation note`; do not replace them with copied values.
- If a user-created sheet has an ambiguous status, preserve the text and map it to a controlled leading status only in the verifier-facing status column.
- If a formula references an external file, flag it for repair and do not treat the cached number as evidence of correctness.

## Tooling

Use the bundled `scripts/check_formula_lineage.py` for a read-only scan of formulas, cross-sheet references and external links. It reports structure only and never computes the engineering result or inserts a status. Consult `references/status-vocabulary.md` when normalizing a qualified status and `references/workbook-closure.md` for the final read-back checklist.

## Closing check

Before handoff, open the workbook in formula view and value view, confirm that every required scope has at least one calculation and one finding, confirm that the summary is reconciled, and confirm that the workbook path and filename match the instruction.

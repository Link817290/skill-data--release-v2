---
name: calculation-book-closure
description: Close a technical calculation-book review into an auditable Excel handoff. Use when conclusions must be traced to original report evidence, cross-table relationships must be reconciled, unresolved inputs must stay open, and workbook structure and formulas need final quality control.
---

# Calculation-book closure

Use this capability to turn a technical review into a defensible Excel handoff. It covers evidence traceability, cross-table consistency, unresolved-input handling, and final workbook quality.

## 1. Establish an evidence working copy

Inventory the received files without altering them. For a PDF with a searchable text layer, use `pdfinfo` to confirm its page count and `pdftotext -layout` to create a temporary working copy outside the materials directory. Search that temporary copy for section headings, member names, table captions, and governing-limit language, then retain the PDF page or printed page marker with each extracted observation.

Use page rendering only for a targeted table whose row or merged-column alignment remains ambiguous after text extraction. Never substitute a hand-prepared excerpt for the original report, and delete temporary crops or extraction files from the final handoff.

## 2. Define the review universe

Create a check register before drafting conclusions. Give every check a stable `check_id`, a source locator, a subject/member, the observed value, the governing criterion, and one status from the contract. Include both positive checks and checks whose required input is absent.

The register is a coverage control: it prevents a favorable table from hiding a missing member or an unreviewed load case. Do not add checks solely because a familiar code normally contains them; they must be anchored in the supplied report or in an explicit review requirement.

## 3. Close relationships across the report

Compare repeated facts that should agree:

- member IDs and section dimensions between narrative and result tables;
- material/environment limits and the member category to which they are applied;
- reported subtotals and recomputed signed totals;
- required steel values and the locations/areas of the bar marks;
- a narrative “satisfied” claim and the worst row in its supporting table.

When a repeated value differs, retain both observations and identify which one is authoritative for the check. If the report does not resolve the conflict, use `REVIEW` instead of silently choosing the convenient value.

## 4. Preserve absence and uncertainty

Use a missing-value code in the workbook that is visibly different from numeric zero. A blank `required_area_mm2` is evidence that the demand was not disclosed, not evidence that demand is zero. The same distinction applies to dashes in serviceability or stability columns.

Use `REVIEW` for a conclusion blocked by a missing binding input, and explain what would close it. Do not convert every uncertainty into FAIL, and do not use caution to avoid a check whose values are available.

## 5. Build the Excel handoff

The workbook should have:

- a `Review` sheet with one row per check and stable headers;
- a `Readme` sheet describing status meanings and units without embedding an answer key;
- formulas for arithmetic and bar-area intermediates where applicable;
- frozen header, filters, wrapped evidence text, and sensible column widths;
- no hidden answer sheets, external links, or macros.

Use a formula cell for a derived subtotal or area, and a separate status cell for the professional judgment. This keeps the mechanical calculation inspectable without making the spreadsheet itself a solver.

## 6. Perform closure checks

Before delivery, verify that every in-scope row has exactly one status, a source locator, and an evidence note. Check that all source locators point into the supplied report and that units are present for numeric observations. Confirm that a `REVIEW` row names the missing field rather than merely saying “unclear.”

Close the approval layer separately from row coverage. State one overall disposition, group open issues without erasing their affected checks, and link every blocker to the absent input or verification record that would resolve it. Reconcile that disposition against favorable narrative conclusions in the report and against every unresolved row in the workbook.

`tools/workbook_schema_check.py` checks these structural properties using caller-provided status and locator values. It never compares against a project answer or decides whether a row is correct.

## 7. Keep alternative solutions valid

A reviewer may use a different sheet order, translated descriptions, or a different rounding display. The stable contract is the check ID, normalized status, numeric meaning, and traceable source evidence. Do not force a particular sentence or row order when the underlying claim is clear.

## 8. Common traps

- omitting unresolved rows because they are inconvenient;
- using a note as a substitute for a status;
- mixing source identifiers and translated labels in the same key column;
- putting formulas only in a hidden sheet;
- claiming complete coverage while silently dropping a table or member;
- overwriting or renaming the received calculation material.

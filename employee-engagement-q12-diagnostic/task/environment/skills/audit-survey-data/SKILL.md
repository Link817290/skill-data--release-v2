---
name: audit-survey-data
description: Audit survey spreadsheets when multiple files, periods, exports, identifiers, mappings, or eligibility rules must be reconciled into a traceable respondent-level dataset.
---

# Survey data audit

Inspect the supplied files before analyzing results. Determine what one row represents and which fields establish lineage, identity, period and response content.

Translate any supplied requirement or parameter tables into an evidence checklist before computing. For each requirement, identify the input fields, analysis population, output table and reconciliation that will prove completion.

## Inventory inputs

List each workbook and sheet, its row unit, period, identifiers and relevant columns. Confirm question and answer mappings from supplied dictionaries rather than from labels alone.

Check key uniqueness, missing fields, type consistency and cross-file coverage before joining anything.

## Reconcile records

Preserve source file and source row for every imported record. Identify duplicates only from supported keys and consistency checks.

Keep physical rows separate from the logical respondent population. Record deterministic inclusion decisions and their reasons.

Treat unsupported quality filters as sensitivity flags, not silent deletions.

## Normalize responses

Apply only supplied question crosswalks and scale maps. Retain original values beside normalized values.

Do not infer item order, score direction, identity equivalence or historical attributes from similar-looking codes.

## Close the ledger

Reconcile source rows to logical responses and each downstream population. Flag unexplained gains, losses, duplicates or unmapped values instead of forcing closure.

Before delivery, reopen the produced workbooks and check that every checklist item can be located from a result table back to its population, mapping and source lineage.

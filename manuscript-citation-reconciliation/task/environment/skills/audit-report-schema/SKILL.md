---
name: audit-report-schema
description: Validate a structured JSON audit report for per-file coverage, traceable discrepancy records, explicit empty directions, and closed review fields.
allowed-tools: Read Write Edit Bash
license: MIT
---

# Audit Report Schema

## Purpose

Use this final formatting layer after the evidence work is complete. It keeps a multi-document report machine-readable without hiding an empty result or mixing findings from separate files. The schema is a delivery contract, not a shortcut to deciding which entries are correct.

## Required shape

The top-level object has:

- `report_version`: a non-empty string;
- `manuscripts`: a non-empty array, one object per supplied DOCX;
- `summary`: an object with integer totals.

Each manuscript object has `file`, `bibliography_count`, `cited_labels`, `unmatched_references`, `unmatched_citations`, `citation_occurrences`, `ignored_bracket_expressions`, and `boundary`. `cited_labels` is a sorted integer array. The occurrence arrays retain exact paragraph-level source evidence and may be empty only when the body has no bracket expressions. `boundary` records integer `bibliography_heading_paragraph_index` and `bibliography_end_paragraph_index` values.

An unmatched-reference record has `reference_number`, exact `reference_text`, an `evidence` object containing integer `bibliography_paragraph_index`, and `issue`; use `bibliography_entry_not_cited_in_body` for its issue. An unmatched-citation record has `citation_label` and `issue`; use `body_citation_has_no_bibliography_entry` for its issue. Every unmatched record also has a `review` object with string fields `status`, `action`, and `basis`, a `compare_files` string array, and a `peer_evidence` array. A reference review additionally carries `identity_evidence.local` with normalized `author` and `title` strings and `identity_evidence.peers` for its listed peers. A reference peer item has `file`, integer `reference_number`, integer `bibliography_paragraph_index`, boolean `cited_in_body`, and `match_type` (`exact_text` or `author_title_identity`). A citation peer item has `file`, `citation_label`, `citation_paragraph_indices`, and `match_type`. Use `peer_evidence: []` when the decision has no peer. The review object records the cross-file decision without replacing the local evidence. Keep the controlled review values from the reconciliation skill; do not substitute a narrative synonym. Do not add a prose explanation outside the JSON document.

## Consistency checks

The report should satisfy these self-referential invariants:

1. File names are unique and correspond to supplied material files.
2. Every reference number is an integer in the local bibliography range.
3. Every citation label is an integer.
4. The summary totals equal the lengths of the per-file discrepancy arrays.
5. No discrepancy direction is silently omitted; an empty direction is represented by `[]`.
6. Reference text is evidence copied from the source, not a normalized paraphrase.
7. Every `evidence.bibliography_paragraph_index` points to the paragraph containing that exact entry in its own DOCX.
8. Every accepted or rejected bracket expression is represented once with its exact source paragraph and literal, and the two boundary indexes identify the section used for the scan.

## Alternative formatting

Whitespace, key order, and Unicode escaping may vary. Numbers and controlled strings are semantic. A different top-level ordering or an additional non-semantic note is acceptable only if the required fields remain unambiguous and the note does not replace evidence.

`references/report_shape_checklist.md` is a compact pre-delivery checklist. `scripts/validate_report_shape.py` checks structural invariants and can be run against a report plus a materials directory; it does not decide citation membership.

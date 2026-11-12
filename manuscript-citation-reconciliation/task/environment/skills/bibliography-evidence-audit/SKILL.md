---
name: bibliography-evidence-audit
description: Audit a document's back-matter bibliography as an ordered evidence list, bind findings to exact supplied entries, and reconcile repeated entries across revisions.
allowed-tools: Read Write Edit Bash
license: MIT
---

# Bibliography Evidence Audit

## Purpose

Use this method to turn a bibliography section into a reproducible, ordered evidence register. The method is intentionally narrower than literature search: it does not verify whether a paper exists, correct author metadata, or add sources. It only establishes which entries are present in the supplied manuscript and how they are numbered for comparison with body labels.

## Establishing the entry list

Locate the exact bibliography heading at the back of the document. The first non-empty paragraph after that heading is entry 1, the next is entry 2, and so on until the next back-matter heading. Do not infer numbering from author names, publication years, or alphabetical order. Retain the exact entry string, including Chinese punctuation, capitalization, brackets for publication type, and trailing punctuation.

If an entry wraps visually but remains one paragraph in the DOCX XML, keep it as one entry. If one entry has been split across multiple paragraphs, record the boundary decision and join only when the source structure makes the continuation unambiguous. A heading, acknowledgement, or project statement is not an entry and must terminate the list.

## Binding findings

Each finding must point to one file and one ordinal. For an absent body use, report the ordinal and the original entry text; the absence is established by the independent citation-label set, not by a title search. For a body label with no entry, report the integer label and do not fabricate a reference text. Keep the two issue values distinct so downstream readers can tell which side of the relation failed.
For every uncited bibliography finding, retain the zero-based DOCX paragraph index of the source paragraph in an `evidence.bibliography_paragraph_index` field. The index is a location anchor, not a replacement for the verbatim entry text.

## Cross-file discipline

The same title can occur in multiple manuscript revisions. It remains a separate evidence item in each file. Never deduplicate across files, and do not assume that a later revision repairs an earlier one. The report is a per-file audit of the materials supplied for this run. A peer evidence item is an audit trail, not a replacement for the local verbatim entry.

## Quality controls

- Count non-empty bibliography entries and compare that count with the highest body label before writing the report.
- Verify that every reported reference number is within `1..bibliography_count`.
- Verify that every `reference_text` is copied from the extracted bibliography list, not reconstructed from memory.
- Keep empty discrepancy directions in the report.
- Re-run the scan after any boundary adjustment; stale counts are evidence of a broken audit trail.

## Comparing a revision set

When several revisions are supplied, build two indexes from each ordered entry. The first is an exact-text index. The second is a conservative work-identity index made from the author block and title after Unicode case/spacing/punctuation normalization; do not match on a title fragment alone, and do not merge entries when the author block or title disagrees. An identity match is a useful lead when a revision changes capitalization, entry type, venue wording, or other metadata, but the local verbatim entry remains the evidence.

For an uncited entry, first check exact peers, then conservative identity peers. Record the other files containing the exact entry or the identity-matched variant and whether those copies are cited. For every peer that drives the decision, preserve a `peer_evidence` item with the exact `.docx` filename, that peer's local reference number, its zero-based bibliography paragraph index, `cited_in_body`, and `match_type` (`exact_text` or `author_title_identity`). A file name without its `.docx` suffix is not an evidence anchor. Use an empty peer list only when no exact or identity peer exists. Classify the evidence using the controlled values below. These values are part of the report contract, not free-form prose:

| Classification | `status` | `compare_files` | `action` | `basis` |
| --- | --- | --- | --- | --- |
| no peer copy | `version_specific` | all peer files containing the exact text (there are none) | `verify_version_scope` | `entry_absent_from_other_revisions` |
| a cited peer copy exists | `resolved_in_other_revision` | every peer containing the exact text | `check_revision_transfer` | `same_entry_cited_in_other_revision` |
| peer copies exist but all are uncited | `persistent_gap` | every peer containing the exact text | `escalate_editorial_decision` | `same_entry_uncited_in_all_revisions` |
| no exact peer, but a cited identity-matched variant exists | `variant_in_other_revision` | every identity-matched peer | `verify_metadata_transfer` | `same_work_with_normalized_author_title_match` |
| no exact peer, but uncited identity-matched variants exist | `persistent_variant_gap` | every identity-matched peer | `escalate_editorial_decision` | `same_work_uncited_in_all_revisions` |

For a body label that exceeds the local bibliography count, use `status=out_of_range_label`, compare only peers whose body label set contains that integer, `action=verify_numbering_or_missing_entry`, and `basis=body_label_has_no_local_bibliography_entry`. Exclude the anchor file from every `compare_files` array. This comparison is supplemental to the local ordinal finding; it never merges or renumbers entries.

For every unmatched bibliography review, expose the exact normalized author and title strings used for the identity decision in `identity_evidence.local`. For each listed peer, repeat its file, local reference number, normalized author and title strings, and match type under `identity_evidence.peers`. Empty peer arrays remain explicit; do not infer identity from a title fragment alone.

`references/reference_section_boundaries.md` records the boundary cautions used by this skill. Read it when a document contains more than one heading-like line or a closing section.

`scripts/index_bibliography_entries.py` emits an ordered intermediate list from paragraph JSON. It performs no citation comparison and never edits the DOCX.

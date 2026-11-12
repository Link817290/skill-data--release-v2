---
name: citation-set-reconciliation
description: Reconcile bracketed numeric citation labels in manuscript body text with an ordered bibliography set, including grouped labels and both directional gaps.
allowed-tools: Read Write Edit Bash
license: MIT
---

# Citation-Set Reconciliation

## Purpose

Use this method after paragraph text has been extracted. It separates two questions that are often conflated: which labels occur in the manuscript body, and which ordinal positions exist in the bibliography. The comparison is set-based and directional. A bibliography item can be absent from the body even when every body label has a valid range, and a body label can be out of range even when the bibliography is long.

## Scope discipline

Define the body boundary and bibliography boundary before scanning. Exclude the bibliography itself from the body-label scan; otherwise the labels printed in a bibliography can falsely make every item look cited. Exclude table-of-contents lines and examples outside the manuscript body unless the task explicitly includes them. Keep each file separate and retain the exact source paragraph or entry text alongside any finding.

## Label grammar

The ordinary forms are a single integer such as `[7]`, a comma group such as `[7,8,11]`, and a numeric range such as `[7-10]`. Full-width square brackets and Chinese comma punctuation may carry the same meaning. Expand a range only when both endpoints are numeric and the document's citation convention clearly uses ranges; otherwise retain the literal group for manual review. Do not interpret mathematical intervals, page ranges, array indices, or prose that merely contains brackets as citations.

Normalize only for comparison:

- trim surrounding whitespace;
- convert full-width brackets and separators to their ASCII equivalents;
- expand numeric groups into integer labels;
- deduplicate labels while retaining occurrence locations separately if needed.

Never rewrite the original bracketed string in the evidence field. The supplied report contract stores normalized integer labels; preserve source wording only in the reference evidence field.

## Directional reconciliation

Let `C` be the set of labels found in body prose and let `B` be the ordinal set from the non-empty bibliography entries. The two discrepancy directions are:

- `B - C`: an ordered bibliography entry has no corresponding body label;
- `C - B`: a body label has no corresponding bibliography entry.

The sets are an intermediate calculation. The final report must bind every member back to its file and exact reference text or citation label. An empty direction is a valid result and must be reported as an empty list rather than omitted.

## Evidence requirements

For an uncited bibliography entry, retain its ordinal number, exact non-empty entry text, and the controlled issue value used by the task. For an unmatched body label, retain the label and the issue value. If paragraph locations are available, include them as supplemental evidence, but do not invent page numbers from a DOCX layout.

Create a complete occurrence register for the body interval. Each accepted numeric bracket must retain its zero-based paragraph index, exact bracket literal, expanded integer labels, and complete source paragraph text. Also retain every bracket expression rejected by the numeric grammar with its paragraph index, literal, complete paragraph text, and the controlled reason `non_numeric_expression`. This rejected register is evidence that mathematical or other bracketed notation was not silently counted as a citation.

When comparing revisions, keep exact-text matches separate from conservative identity matches. For an identity candidate, normalize Unicode case, spacing, and punctuation only within the author block and title; require both to agree before treating a changed venue, entry type, or capitalization as the same work. Keep the local entry text and paragraph index unchanged, and mark a cited identity variant with the variant review status rather than calling it an exact peer.

## Revision-set review

For each directional gap, add a review decision after the local set difference is fixed. Keep the current file as the anchor and list only other supplied files relevant to the comparison. The review keys are `status`, `compare_files`, `action`, `basis`, and `peer_evidence`; each decision field must be concrete, with `compare_files` and `peer_evidence` arrays. For an unmatched bibliography item, each peer evidence item must carry the exact `.docx` filename, peer reference number, zero-based bibliography paragraph index, whether that peer label occurs in the peer body, and `match_type`. Do not replace a filename with a stem or an ordinal with a global number.

Use this controlled decision table so that equivalent audits produce the same machine-readable result:

| Local gap | Evidence in peer files | `status` | `compare_files` | `action` | `basis` |
| --- | --- | --- | --- | --- | --- |
| Uncited bibliography entry | Exact entry text occurs in no peer file | `version_specific` | `[]` | `verify_version_scope` | `entry_absent_from_other_revisions` |
| Uncited bibliography entry | Exact entry text occurs in one or more peers and at least one peer copy is cited | `resolved_in_other_revision` | all peers containing that exact text | `check_revision_transfer` | `same_entry_cited_in_other_revision` |
| Uncited bibliography entry | Exact entry text occurs in peers, but no copy is cited | `persistent_gap` | all peers containing that exact text | `escalate_editorial_decision` | `same_entry_uncited_in_all_revisions` |
| Body label outside the local bibliography | Peer body sets may contain the same integer | `out_of_range_label` | peers whose body set contains that integer | `verify_numbering_or_missing_entry` | `body_label_has_no_local_bibliography_entry` |

For a reference gap, `compare_files` is the set of peer files containing the exact entry, regardless of whether their copy is cited. For an out-of-range label, it is the set of peer files where the integer occurs in body text. Never include the anchor file itself. The review decision supplements, and never replaces, the local directional finding. If no peer can be established, emit `peer_evidence: []` rather than an inferred record.

## Mechanical aid

`references/citation_label_grammar.md` contains a compact checklist for distinguishing citations from nearby bracketed notation. `scripts/scan_citation_labels.py` reads extracted paragraph JSON and returns label occurrences for a caller-supplied paragraph interval. It does not know a task's answer and does not compare against a bibliography.

## Common failure modes

- scanning the whole document, which counts bibliography labels as body citations;
- treating every bracket containing digits as a citation;
- collapsing the two directions into one `missing` bucket;
- renumbering references by title or author rather than by their supplied order;
- silently dropping a file whose text extraction failed;
- reporting a label without the exact file context.

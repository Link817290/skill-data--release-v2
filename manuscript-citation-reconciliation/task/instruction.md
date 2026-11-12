# Review note

The editorial desk is holding three revisions of a manuscript and needs a final citation-coverage reconciliation before the next submission decision. The review must keep the revisions distinct and make every discrepancy answerable by the supplied evidence.

## Action requested

Before examining any manuscript, create `/workspace/output/citation_audit.json` as an empty UTF-8 JSON skeleton. Then complete the review using only the files under `/workspace/materials/` and no network access. Use any applicable work procedures already present in the environment. Represent every `.docx`; preserve each reported `reference_text` exactly as supplied; record both directions of mismatch; and include the required per-manuscript fields, controlled issue values, `report_version` `1.1`, and a `summary` with recomputed totals. Every mismatch record must also carry a `review` object with `status`, `compare_files`, `action`, and `basis`; every unmatched bibliography record must carry an `evidence.bibliography_paragraph_index` pointing to its source paragraph; write review values in English while retaining source entry text verbatim.

Every mismatch review must also include a `peer_evidence` array. Each peer item must identify the exact supplied `.docx` filename, the peer bibliography number, its zero-based bibliography paragraph index, whether that peer number is cited in that peer's body, and whether the comparison is an `exact_text` or `author_title_identity` match; use an empty array when no peer exists. Keep the peer evidence tied to the supplied revisions rather than inferred publication metadata. Include a complete `citation_occurrences` register for every accepted bracketed numeric citation, retaining its source paragraph text, paragraph index, literal, and labels; also report each body bracket expression that was excluded from citation matching in `ignored_bracket_expressions`, with its source paragraph and exclusion reason. Record the bibliography heading and terminating boundary indexes in `boundary`, and include normalized author/title evidence for every unmatched bibliography review and its listed peers.

## Requested reply

The memo is complete when each supplied revision appears once and every reported mismatch is traceable to its own body label or bibliography entry and to the relevant revision evidence. Submit only `/workspace/output/citation_audit.json`.

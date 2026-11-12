# Scoring Rubric

This rubric is derived from the supplied manuscript revision bundle and from the submitted `citation_audit.json`. The verifier independently re-parses every supplied `.docx` at scoring time with `tests/material_parser.py` and derives the expected body-citation labels, bibliography entries and directional set differences from the document body and back matter; it does not read a prewritten answer key. Scoring evaluates substance — which discrepancies the report finds, which evidence it binds them to, and which cross-file review decision it reaches — and not record order, JSON whitespace or key order.

## Score Form

```text
strict = max(0, positive_earned - deduction_total)
         positive_earned = sum over the four positive items of (weight * completion)
         deduction_total = sum over distinct damage roots of the largest applicable
                           deduction amount for that root
```

Weights and deduction amounts are read from `tests/scoring_params.json`. Each
item's completion is the fraction its check reports, between 0 and 1:
`tests/ledger_map.json` binds each P item to one component of the detail printed
by `tests/report_checks.py`, and `tests/validator.py` clamps it into `[0, 1]`
before settling the score. A binary lenient lens is reported next to strict.

Credit is file-local. A value counts only on the manuscript whose `file` it is reported under: correct tokens carried in a different file's record satisfy nothing. Set-valued checks are scored on recall and precision together, so padding a report with extra records lowers the score rather than raising it.

If the submitted JSON is invalid, a required top-level or per-manuscript field is absent, a record is malformed, or the report does not cover exactly the supplied `.docx` files, every item completion is 0 and the strict score is 0.

## Scoring Dimensions

Each item is one scored proposition. Weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| --- | --- | --- | --- | --- | --- |
| P03 | Source extraction fidelity | The citation occurrence register: each `citation_occurrences` record reproduces the paragraph index, the bracket literal, the ordered numeric labels it expands to, and the source paragraph text | The supplied `.docx` body paragraphs and `citation_occurrences` | 0.30 | Source location |
| P06 | Discrepancy detection | Both directional set differences across every manuscript: each expected `(file, number or label, issue)` record appears once, with `bibliography_entry_not_cited_in_body` and `body_citation_has_no_bibliography_entry` kept apart | `unmatched_references` and `unmatched_citations` over all manuscripts | 0.30 | Relation |
| P07 | Evidence binding | Each matched uncited-reference finding carries the supplied bibliography entry as `reference_text`; a verbatim entry takes full credit for that record and a whitespace-only variant takes 0.8, scored against the count of expected reference findings | The supplied bibliography entries and `reference_text` | 0.15 | Invariant |
| P08 | Cross-file review decision | For each expected discrepancy, compare `status`, sorted `compare_files`, `action`, `basis`, and sorted `peer_evidence`; `identity_evidence` is checked by D03/D04 | The supplied revisions and each finding’s `review` | 0.25 | Cross-file relation |

Partial credit is the rule. P08 is the fraction of expected review decisions that match. P03 and P06 multiply recall by precision over their record sets, so both omissions and invented records cost credit; where nothing is expected, an empty set scores 1 and any submitted record scores 0. P07 is a proportion over the expected reference findings, so a report that binds most of them correctly earns proportionally.

### Why these weights and calculations

- **P03 = 0.30.** The occurrence register is the primary provenance layer: if the
  paragraph, literal, or expanded labels are wrong, a reviewer cannot reproduce
  the later set comparison. It therefore receives the largest single weight.
  Recall and precision are multiplied because an audit that omits source events
  and one that invents events are both materially incomplete; the product gives
  partial credit only when both coverage and restraint are present.
- **P06 = 0.30.** The two directional discrepancies are the decision-facing
  result of the reconciliation. The same recall-times-precision calculation is
  used over `(file, number-or-label, issue)` keys so moving a correct finding to
  a different revision, duplicating it, or adding an unsupported finding cannot
  receive full credit. Its weight matches P03 because detection is as important
  as the evidence register that supports it.
- **P07 = 0.15.** Exact bibliography text is an evidence-binding invariant, but
  it is narrower than discovering the discrepancy or locating its source. Each
  matched reference therefore contributes proportionally, with a whitespace-only
  serialization variant retaining partial credit and an edited citation losing
  that record's credit.
- **P08 = 0.25.** Cross-revision status, peer locations, and action determine
  whether the finding is actionable rather than merely mechanically detected.
  The fraction of expected review decisions that match is used because each
  discrepancy is an independent editorial decision; one bad decision should not
  erase otherwise correct review work, and one correct decision should not hide
  omissions elsewhere.

The weights sum to 1.0 by design. They express the relative operational harm of
lost provenance, missed or invented discrepancies, weak evidence binding, and
unactionable cross-revision conclusions; they are not a target score or a cap.

### Accepted equivalent expressions

- Container names prescribed by the task — `citation_occurrences`, `ignored_bracket_expressions`, `boundary` — are required as written. The key carrying a record's source paragraph text is resolved by alias: `paragraph_text`, `source_paragraph_text`, `source_paragraph`, `paragraph` or `text`. The key carrying an exclusion reason is `reason` or `exclusion_reason`, and any non-empty reason string passes the structural check.
- Source paragraph text in `citation_occurrences` is compared after collapsing runs of whitespace and trimming the ends (for example a leading tab from the docx run); the words must still be verbatim.
- `labels` may be a list of integers, a list of digit strings (`["1", "2"]`) or one digit string with separators (`"1, 2"`). Any other form is read as a non-matching record, not a malformed report.
- A `reference_text` that keeps the source paragraph's own leading or trailing whitespace counts as verbatim; the inner text must match byte for byte. Unicode escaping and equivalent JSON serialization are accepted, but paraphrase, correction of punctuation, or recall from memory is not.
- Normalized author and title strings in `identity_evidence.local` are compared on letters and digits only, so case, spacing and punctuation of the normal form do not decide D03 or D04. For an entry with no publication-type bracket (`[J]`, `[C]`, ...), a title that ends at the first sentence stop is accepted as that entry's title.
- Manuscript order, record order, JSON key order and insignificant whitespace may vary. Empty directions must still be present as arrays.

## Deductions

Each independent damage root contributes one additive amount. Repeating the
same manifestation does not compound it, and no deduction imposes a score cap.

| Item | Error | Damage instances | Amount | Rationale |
| --- | --- | --- | --- | --- |
| D01 | `cited_labels` contains a label the body-prose scan does not produce — a bracket lifted from a table cell | one per manuscript carrying the error | 0.03 | This also reduces P03/P06, so only the separate handoff harm is deducted |
| D02 | A reported `reference_text` on a shared reference finding is not the supplied bibliography entry verbatim (edge whitespace aside) | one per manuscript carrying the error | 0.10 | The task asks for each reported `reference_text` preserved exactly as supplied |
| D03 | The normalized author block in `review.identity_evidence.local` is a strict prefix of the supplied author block, the trailing `et al` dropped | one per manuscript carrying the error | 0.10 | A truncated author block manufactures peer identity matches the supplied entries do not support |
| D04 | The normalized local author or title is neither the supplied value nor a prefix truncation of the author block — a truncated title, or the author/title split taken at the wrong point | one per manuscript carrying the error | 0.10 | An identity block not derived from the supplied entry cannot ground a review decision |
| D05 | A quotation reported under a revision — a `citation_occurrences` or `ignored_bracket_expressions` source paragraph, or a `reference_text` — is absent from every paragraph of that revision yet appears verbatim in another supplied revision | one per manuscript carrying the error | 0.20 | A citation is only evidence if the quoted text is in the record it cites; text lifted from a sibling revision is fabricated provenance |
| D06 | `report_version` is not `1.1`, or a required `summary` total is missing or disagrees with the report's own `manuscripts` array | one per report | 0.10 | The task names the version and requires recomputed totals |
| D07 | `cited_labels` omits a label the body-prose scan does produce | one per manuscript carrying the error | 0.05 | Dropping real citations manufactures uncited-entry findings |
| D08 | A reported unmatched reference gives the wrong `evidence.bibliography_paragraph_index` | one per manuscript with any wrong shared-reference index | 0.08 | Source location must bind the finding to the supplied bibliography |
| D09 | `ignored_bracket_expressions` differs from the bracket exclusions derived from the supplied body | one per manuscript with a differing exclusion set | 0.08 | The report must distinguish excluded bracket expressions from numeric body citations |
| D10 | Bibliography heading or end paragraph index is wrong | one per manuscript with a wrong boundary tuple | 0.08 | The audit must delimit the bibliography in each supplied revision |

Interactions with the scored items:

- Deductions are evaluated only on a report that passes the structural gate; a report that fails it already scores 0.
- D02, D03, D04 and D08 read only reference findings whose `(file, reference_number)` key the report and the derived report share. A finding the report never makes is not charged here; it is measured by P06.
- D03 and D04 are mutually exclusive on a given field: a shortened author block that is a prefix of the supplied one charges D03, and any other departure charges D04. A manuscript can raise both when different records fail differently.
- D05 is charged on provenance only, and deliberately narrowly. A quote that is verbatim nowhere in the materials (a paraphrase, or an edited quote) is **not** charged here; a quote that is verbatim in the revision it is reported under but sits under the wrong paragraph index is **not** charged here; an omitted quote is **not** charged here. Those are measured by P03, P07 and P06 where they bear on scored records. Strings shorter than 20 characters are ignored, because short strings collide across revisions and carry no provenance.
- D06 also charges omission of any of the three required summary totals. The public instruction requires a recomputed summary, and the schema names `manuscript_count`, `unmatched_reference_count`, and `unmatched_citation_count`; omitting a total makes the editorial handoff incomplete rather than merely concise.
- D08 charges an incorrect index only on findings present in both reports; D09 and D10 each charge at most once per manuscript.
- D01 and D07 can both fire on one manuscript when the label set both invents and omits labels; they are separate instances.
- An affirmative error charged here also costs positive credit — a non-verbatim `reference_text` loses its P07 share — because the two readings measure different things.

## Automatic Failure

There is no automatic failure for formatting. The structural gate covers invalid
JSON, missing required fields or summary totals, wrong bibliography counts,
malformed records, out-of-range references and incomplete file coverage.
Everything else uses additive root deductions. There is no score cap, positive
floor or pass threshold.

## Lenient Lens

The binary lenient score is 1 iff positive_earned > 0.50, P03 and P06 are
each at least 0.50, and none of D01, D03, D04, D05, D06 or D10 fires. The
structural gate separately requires exact bibliography counts and all three
summary totals. This auxiliary lens does not alter strict.

## Reference and source integrity

`task/tests/ground_truth.json` is a human-review illustration only. Runtime scoring independently derives expectations from the SHA-bound `tests/materials` originals through material_parser.build_report; it never consumes this prewritten report. The original task manifests retain their ground_truth metadata declaration; this is not a runtime scoring input. The manifests and solver materials remain unchanged. Existing rollout statistics are historical and have not been reclassified with the revised lenient policy.

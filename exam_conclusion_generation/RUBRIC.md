# Scoring Summary

Formal scoring uses three dimensions:

| Dimension | Weight | Meaning |
|---|---:|---|
| A Finding identification | 45% | Whether the same underlying finding is identified; one-to-one matching, false negatives and false positives both enter the F1 denominator. |
| B Standard terminology | 35% | After an A-level match, whether the same professional conclusion is expressed faithfully in standard clinical wording. |
| C Qualifier fidelity | 20% | Whether location, laterality, quantity, degree, characteristics, certainty, and status are faithfully preserved. |

Total score: `0.45A + 0.35B + 0.20C`, multiplied by source-file integrity.

Finding identity receives 45% because identifying the correct abnormality is
the prerequisite clinical decision and controls both omissions and false
positives. Standard terminology receives 35% because a downstream report must
communicate the identified finding in usable professional language. Qualifier
fidelity receives 20% because laterality, degree, quantity, certainty, and
status materially refine a correct finding but cannot compensate for selecting
the wrong finding. The percentages state relative clinical responsibility; the
rubric does not claim that nearby alternative splits are inherently invalid.

Every hit in all three dimensions is weighted by **evidence precision** — the fraction of the cited detail rows that actually support that conclusion, `|cited ∩ gold| / |cited|`. Citing the one row that carries the finding earns full credit; padding a citation with an entire case's rows earns a small fraction of it. Recall is deliberately not penalised: a gold conclusion supported by several rows does not require the model to cite all of them. This prices whether the evidence trail is honest, not whether it is exhaustive.

Case-level closure, summary-status consistency, deliverable structure, and case coverage are reported as diagnostics in `reward_detail.json` and are not part of the reward.

## Machine-scoring details

Within each dimension, macro and micro F1 are blended 5:2 — macro is the mean of per-case F1 over cases that carry gold conclusions, micro is the global F1. Matching is a maximum one-to-one assignment per case; an A-level hit requires the cited rows to intersect that conclusion's gold evidence. B and C admit conservative orthographic normalization and declared `fidelity_aliases`. An unresolved expression may earn B/C credit only after the evidence-bound semantic check below; broad recognition aliases alone do not establish terminology or qualifier fidelity.

`source_integrity` is a multiplier over the whole score, verifying the workspace inputs against `task/tests/source_manifest.json`. Modifying, deleting, or moving an input file reduces the total proportionally.

Reported as diagnostics in `reward_detail.json`, outside the reward: case-level closure, summary-status consistency, normal-case handling, cross-sheet consistency, auditability, structure, evidence case-ownership, and duplicate rows.


## Semantic Equivalence And Completion

The source detail rows are authoritative. The evaluator-only reconstruction
rules are neither actor input nor evidence of an unprovided doctor review.
Finding identity, terminology, and qualifier fidelity are judged separately:
A accepts the same observed finding despite wording differences; B requires a
medically standard name supported by the source; C preserves material semantic
qualifiers that belong in a concise conclusion name. Measurements, dimensions,
echo descriptions, and other evidence details remain in the cited source rows
and need not be repeated in the conclusion-name column.

The semantic judge receives only same-case, evidence-overlapping candidate and
source units. It cannot add findings, repair citations, or infer a diagnosis from
external knowledge. Each decision binds to the candidate conclusion and source
rows. Wrong laterality, negation, different findings, or unsupported diagnostic
meaning receive no credit.

Lenient reward requires the complete workbook contract, same-case evidence for
every conclusion, no abnormal conclusions in the four normal cases, coverage of
all abnormal cases, and case-summary status consistent with the conclusion rows.
It is independent of strict-score thresholds and exact reference recall.
Required semantic-service failure returns evaluator error 2 and publishes no
numeric score.

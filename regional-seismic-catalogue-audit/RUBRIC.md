# Scoring Rubric

The report is an evidence-bound scientific register. The scorer evaluates the
source inventory, normalized event rows, recomputable statistics, identity
reconciliation, comparisons, and the conclusions that the report publishes.
Key names and JSON nesting may vary when the scorer can resolve the same
meaning through the documented schema tolerance.

## Score form

```text
strict = positive_earned * retention
positive_earned = sum(weight[P] * completion[P])
completion[P] = item_fidelity * screening_gate * observation_gate
                 * status_gate * event_precision
retention = product of the smallest deduction coefficient in each damage instance
```

The weights and deduction coefficients are in
`task/tests/scoring_params.json`; they sum to one and are applied directly.
There is no score cap or target-floor adjustment. A defect loses the evidence it
fails and, where appropriate, applies the stated multiplicative deduction; it
does not receive an arbitrary hard threshold. `reward` aliases strict.
`reward_lenient` is an independent binary delivery lens and never changes
strict.

## Positive items

| Item | Dimension | Evidence checked | Weight | Why this weight |
|---|---|---|---:|---|
| P01 | Manifest | Three supplied HTML names and count | 0.05 | Source custody is necessary, but the detailed rows carry most scientific content. |
| P02 | Source structure | Page metadata, table descriptors, and every raw event row | 0.10 | A row or table omitted at ingestion cannot be recovered by later arithmetic. |
| P03 | Event normalization | Source-linked time, place, coordinates, magnitude, quality and raw cells | 0.15 | Normalized observations are the primary factual substrate for all derived results. |
| P04 | Sequence statistics | Counts, bins, b estimate, primary, time indicators, spatial/temporal diagnostics and classifications | 0.20 | These are the task's principal scientific calculations and are independently recomputable. |
| P05 | Identity reconciliation | Duplicate groups, all occurrences, counts, and a canonical member of each group | 0.10 | Cross-page duplicates affect aggregate totals and must remain auditable without deleting rows. |
| P06 | Evidence binding | Primary row, included keys, and source-row pointers resolve in the report inventory | 0.06 | A conclusion without a resolvable row is not reviewable, but this is narrower than the calculations themselves. |
| P07 | Comparative audit | Page signatures, class counts, and every unordered pair | 0.08 | Comparison is useful closure over page-level conclusions, with less scope than per-event extraction. |
| P08 | Aggregate closure | Counts and status/classification rollups recompute from detailed records | 0.10 | Closure catches copied or contradictory summaries without making summaries outweigh observations. |
| P09 | Record-status distribution | Aggregate status counts agree with page statuses | 0.04 | Status is operationally useful, but the same evidence is already checked at page level. |
| P10 | Published verdicts | Overall, comparative, and reconciliation statuses | 0.05 | These are the reader-facing conclusions and deserve independent visibility. |
| P11 | Record verdicts | Each page status is supported by its rows | 0.02 | This guards unsafe release language without duplicating row normalization. |
| P12 | Event verdicts | Each event quality state agrees with the source values | 0.03 | Incorrect inclusion/exclusion can bias statistics, but the observation gate also reflects it. |
| P13 | Completeness verdict | Each page states whether its completeness bin is defined | 0.01 | The status is now explicitly required by the instruction; the numeric bin and statistics carry the weight. |
| P14 | b-value verdict | Each page states whether its b estimate is defined | 0.01 | This exposes the evidence-floor/denominator outcome without over-weighting a state label. |

The distribution gives the largest share to source-linked observations and the
statistics derived from them. P01-P04 are therefore not diagnostic-only: each
has an independent completion item. P09-P14 are deliberately smaller because
they restate conclusions already constrained by the detailed evidence, while
still preventing an answer from hiding an unsupported state.

## Gates and schema tolerance

Each completion is multiplied by three fidelity gates. A gate is
`0.2 + 0.8 * fidelity`, preserving partial credit while making systematic
observation or verdict errors visible across the whole report. Event precision
is the matched submitted-event fraction, so fabricated extras cannot retain
full credit.

The scorer accepts equivalent field names, nesting, event-key recipes, seconds
or milliseconds, and one constant timezone offset. It resolves events and
duplicate occurrences through the report's own raw-row inventory. A canonical
occurrence is a navigation choice: any occurrence that belongs to its declared
duplicate group is valid; the scorer does not force the Golden row. Reports
must still declare a deterministic choice in their evidence fields so a second
analyst can reproduce it.

Timestamps are compared at the source precision. These pages print whole
seconds, so the fixed tolerance is at most 1,000 ms after a single constant
timezone offset is applied; epoch magnitude cannot widen this window. Numeric
coordinates, magnitudes and counts retain the ordinary relative tolerance.

The screening rule is exactly `regional-screen-v1`: completeness bin, b
estimate, primary, dominance, primary-time fraction and later-event count are
computed over quality-supported rows, then the four branches are tested in the
published order. Spatial compactness is a diagnostic only because the supplied
rule does not publish a spatial cut; it cannot silently turn a regional screen
into a physical aftershock claim.

## Deductions

| Item | Error | Instances | Coefficient | Rationale |
|---|---|---:|---:|---|
| D01 | Supplied catalogue HTML is missing or hash differs | 1 | 0.10 | Conclusions cannot be tied to the issued source pages. |
| D02 | Report is missing/unparseable or schema version is not `1.0` | 1 | 0.10 | No reviewable deliverable exists. |
| D03 | A page publishes a b estimate different from `regional-screen-v1` | up to 3 pages | 0.90 | The quantitative rule was applied to the wrong set or formula. |
| D04 | A normalized coordinate or magnitude is absent from that event's own raw cells | up to 3 pages | 0.70 | The report repaired or invented a source value. |

These are multiplicative deductions, independent of positive completion. D03
uses a fixed `1e-3 * max(1, |b|)` output-rounding tolerance; D04 checks only
events that publish their raw cells. A negative statement such as “spatial
compactness is not used by the operational rule” is not a physical-sequence
claim and does not trigger a deduction.

## Lenient delivery lens

`reward_lenient = 1` only when the report is readable, source hashes match,
schema version is `1.0`, all three pages and their event inventories are
present, required completeness and b-value states are published, aggregate
counts close, and no D01-D04 damage instance fires. It is a binary usability
check, independent of strict's continuous value; it does not cap or rescale
strict.

The Golden report is generated by the bundled reference solution and must score
`reward_strict = 1.0` and `reward_lenient = 1.0`.

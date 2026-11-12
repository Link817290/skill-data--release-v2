# Scoring Rubric

Scorer version: `5.0.0`. The required artifact is
`/workspace/output/review_report.md`. This is a mixed evaluation: program code verifies
closed numerical and structural facts, while an evidence-bound model judge assesses
professional equivalence and conclusion meaning. The same evaluator is used for both skill
conditions.

## Evidence boundary

`03_原始材料.xlsx` is the only supplied authority. It supports numerical calculations,
formula locations, source annotations and historical comparisons. It does not include an
approved protocol, approved analytical method, formal run-acceptance aggregation rule,
minimum valid-NC-set rule, approved CV acceptance rule or formal MPC inclusion rule.
Consequently, Run19 through Run54 must remain formally `PENDING`. Element comparisons and
source statuses may be stated as observations but cannot be promoted to formal PASS/FAIL.

## Strict score

The strict score is continuous on `[0,1]`:

```text
strict = clamp(
    0.08 * deterministic_global_values
  + 0.12 * deterministic_system_values
  + 0.10 * deterministic_batch_inventory
  + 0.05 * deterministic_formula_counts
  + 0.15 * semantic_metric_identity_and_input_binding
  + 0.16 * semantic_formal_rule_sufficiency
  + 0.10 * semantic_conclusion_traceability
  + 0.06 * semantic_formula_audit_quality
  + 0.09 * semantic_calculation_chain_and_evidence_boundary
  + 0.045 * semantic_source_discrepancy_diagnosis
  + 0.045 * semantic_historical_impact_boundary
  - itemized_source_misattribution
  - verified_inventory_error,
  0, 1)
```

The weights sum to 1.00. Numerical results and run inventory carry 30% because they are
closed workbook facts; program-verified audit quantities carry another 5%. Metric identity and evidence binding carry 15% because a
correct number attached to the wrong population is not a reproducible result. Formal-rule
sufficiency carries 16% because unsupported batch disposition is the largest compliance
risk in this task. Traceability carries 10% and semantic formula-audit quality carries 6%; calculation-chain quality
carries 9%; discrepancy diagnosis and historical-impact boundaries each carry 4.5%.
These smaller dimensions distinguish deeper review without allowing one finding to dominate
the full report.

The two deductions are itemized source-integrity losses. A batch whose cited source
cells actually belong to another batch deducts 0.02 once for that claimed batch, capped
at 0.15 across the report; this is large enough to make repeated misbinding visible
without erasing independently correct calculations. A materially wrong formula-cell
inventory deducts 0.02 once because it is a local audit-scope error rather than a new
batch disposition. Ambiguous cross-batch references are reported but are not deducted.
The final clamp only enforces the public `[0,1]` score range; it is not a pass threshold.

The semantic judge maps equivalent metric expressions to canonical identities and binds an
exact candidate quotation. Program code then verifies the quoted number against the frozen
workbook-derived target. The model does not decide numerical correctness. Formula syntax,
cell/range syntax, artifact files and hashes are likewise deterministic.

### Semantic criteria

- **Metric identity and input binding:** all five global and six system results must be
  identifiable, directionally correct, tied to their own input populations and supported by
  appropriate formulas/intermediate statistics and workbook locations. Chinese/English
  equivalents, abbreviations and cross-table bindings are accepted.
- **Formal-rule sufficiency:** source annotations, element comparisons and formal objective
  disposition remain distinct. Invented minimum NC sets, CV limits, MPC scope or batch
  aggregation rules receive no credit.
- **Conclusion traceability:** every material numerical, source-status, discrepancy and
  run-specific conclusion has an appropriate worksheet plus cell/range citation. A sheet
  name alone is not cell traceability.
- **Formula-audit quality:** each of replicate mean, sample SD, replicate CV, SIR and
  Mean(NCOD) needs a checked quantity, calculation basis, reconciliation result and source
  scope. Equivalent names and combined rows are accepted. A keyword or count alone is not
  an audit, and a bounded audit does not prove every eligibility decision.
- **Calculation chain and evidence boundary:** inputs, direction, n, df, t, mean, sample SD,
  rounding/provenance and arithmetic-versus-approval boundary remain coherent.
- **Source discrepancy diagnosis:** direct numerical contrast with identity, both values,
  precise locations and a defensible source-priority conclusion earns credit without a
  prescribed discrepancy phrase.
- **Historical impact boundary:** the four verified old-to-current SCPF comparison changes
  and TCPF impact scope are reported without turning sample comparisons into batch statuses
  or altering unaffected global/system values.

Negated, hypothetical, unconfirmed or materially contradicted claims receive no semantic
credit. Candidate quotations are validated against the submitted artifact. The judge cannot
repair one claim by pooling unrelated fragments.

## Lenient score

Lenient scoring is an independent binary usability lens, not a strict-score threshold.
It is `1` only when every direct requirement holds: readable Markdown; all seven template
sections; all eleven core metrics mapped to candidate statements; all 36 Run19-Run54 rows
listed; all 36 formal dispositions recorded as PENDING; a worksheet cell/range reference
on every run row; no invented formal rule; and no material internal contradiction. If any
requirement fails, lenient is `0`. No percentage of the strict score, semantic score, batch
inventory or other numeric quality score controls this result.

## Runtime settlement

A missing or unreadable candidate is a measured candidate failure and receives zero.
Semantic cache misses in replay mode, missing judge configuration, provider failures,
invalid responses and protocol errors are evaluator failures: `test.sh` exits nonzero,
writes an `UNMEASURED` detail, and emits no numeric reward files. The packaged replay applies
only to the byte-exact Golden request; new artifacts can always be evaluated in fresh mode.

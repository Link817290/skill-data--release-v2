# Scoring rubric

Version-transition direction is substantive: `no signal to signal` is `GAINED`,
while `signal to no signal` is `LOST`. The two directions are never synonyms.
Canonical enum values and accurate full-phrase equivalents receive identical credit.

The deliverable is `/workspace/faers_adjudication.json`. A condition-blind validator reads the same artifact in both experimental conditions. Structural, numeric, source-integrity, and source-binding checks are deterministic; wording-only evidence concepts use the packaged request-bound `gpt-5.6-sol` judge. The scorer does not inspect trajectories, skill availability, prose style, JSON key order, or the executor's intermediate method.

```text
strict =
    0.02 * population_reconciliation
  + 0.08 * disproportionality_analysis
  + 0.03 * signal_synthesis
  + 0.15 * version_driver_audit
  + 0.32 * retained_case_causality
  + 0.26 * longitudinal_revision
  + 0.02 * source_integrity
  + 0.04 * exact_coverage
  + 0.04 * table_closure
  + 0.04 * evidence_traceability

lenient = source_integrity * (
    0.40 * contract_coverage
  + 0.30 * table_closure
  + 0.30 * evidence_traceability)
reward = strict
```

The golden artifact scores `1.0000` under both lenses. Semantic judge requests are replayable from `task/tests/golden_replay/` in the offline verifier; fresh scoring uses the standard `LLM_JUDGE_*` environment variables. `reward` and `reward.txt` are compatibility aliases for the continuous strict score; there is no pass threshold.

## Capability dimensions

### Population reconciliation and state closure, 0.02

- **Capability:** construct one deterministic retained-version ledger across periods while preserving all submissions as a separate sensitivity population.
- **Professional reason:** follow-ups describe changing states of a case, not independent patients; a locally correct quarterly deduplication can still create a globally wrong population.
- **Anchors:** identifiers, version relations, receipt dates, partition invariants, and counts recomputed from the supplied header table.
- **Verifier signal:** retained, rejected, period, reporter, and cross-stratum counts agree with the source-derived ledger and close to their parent populations.
- **Attention role:** attend to version ordering and missing reporter values; connect retained report identifiers to their source periods; ignore file order.
- **Accepted variation:** different field names, ordering, nesting, or implementation are accepted when the same populations and invariants are represented.
- **Common failure:** deduplicate inside each period, compare versions lexically, or drop blank reporter codes.

### Disproportionality table construction, 0.08

- **Capability:** form Boolean drug and event memberships and recompute complete tables inside eleven distinct populations per candidate.
- **Professional reason:** a correct formula applied to contaminated child joins or a borrowed denominator produces plausible but invalid signal estimates.
- **Anchors:** source identifiers, whole-component ingredient relations, exact event relations, four-cell conservation, and numeric derivations defined by the analysis contract.
- **Verifier signal:** the four cells, estimable RORs, lower limits, and signal calls are checked independently for canonical, all-submission, healthcare-professional, period, and period-by-reporter populations.
- **Attention role:** connect retained headers to version-specific drug and reaction rows; ignore non-primary roles, partial ingredient matches, and duplicate child rows.
- **Accepted variation:** nested or flat table representations and ordinary numeric rounding are accepted; zero-cell estimates may use any clear non-estimable representation.
- **Common failure:** mix case and submission units, reuse a canonical exposed count in a subgroup, or drop sparse strata.

### Cross-view signal synthesis, 0.03

- **Capability:** reconcile apparently conflicting population results without substituting an adjusted point estimate for a decision rule.
- **Professional reason:** a candidate may flip after follow-up reconciliation or concentrate in one reporting channel while retaining a large adjusted estimate.
- **Anchors:** numeric derivation of the common odds ratio, endpoint signal statuses, and relation-based policy outcomes.
- **Verifier signal:** the adjusted estimate, reconciliation effect, and disposition agree with the independently anchored tables for each candidate.
- **Attention role:** connect the canonical, all-submission, reporter, period, and stratum results; ignore the tempting shortcut of ranking by the largest point estimate.
- **Accepted variation:** equivalent status wording is normalized; narrative explanation is optional and never string-matched.
- **Common failure:** average stratum odds ratios, infer a version effect from the sign of a count change, or escalate from the adjusted estimate alone.

### Version-driver audit, 0.15

- **Capability:** close a candidate-level census over every multi-submission case, distinguish state changes from pair-membership changes, and preserve the complete submitted-state history for the selected risk-stratified reviews.
- **Professional reason:** a reconciliation effect is not auditable from endpoint counts alone; exposure or event changes can move comparator cells even when pair membership never changes, and a transient state can disappear again in the retained version.
- **Anchors:** candidate and case identifiers, numeric report versions, version-specific drug roles and reaction membership, source locations, and adjacent-state relations.
- **Verifier signal:** exact census counts are scored for every candidate. For every requested detailed review, per-version identity and pair state, exposure and event booleans, material addition or removal classes, unique versions, and resolvable source bindings are scored. The census contributes 30% and detailed reviews contribute 70% of this dimension.
- **Attention role:** attend to all versions when closing the census; connect exposure and event deltas to pair states; inspect all versions of each selected review; ignore aggregate count differences as proof of a specific driver.
- **Accepted variation:** a flat register, pair-nested histories, or another JSON organization is accepted when candidate and case identifiers recover the same census and state histories; change classes may use equivalent phrases.
- **Common failure:** equate every state change with pair gain or loss, compare only earliest and retained states, omit zero-count candidate summaries, or omit exposure-only and event-only cell drivers.

### Retained-case causal calibration, 0.32

- **Capability:** apply a qualitative causality standard to sparse structured reports while preserving evidence scope and missingness.
- **Professional reason:** drug-level withdrawal fields, case-level recurrence markers, partial dates, and multiple suspect courses are easy to over-attribute to one named product-event pair.
- **Anchors:** source-row locations plus expert judgment records for chronology, withdrawal, re-exposure, alternatives, and the category ceiling.
- **Verifier signal:** component statuses, final category, required evidence concepts, and resolvable source bindings are scored per requested case.
- **Attention role:** attend to the target product course and target reaction; connect therapy sequence to drug sequence; ignore severity, signal strength, reporter profession, and suspect coding as causal proof.
- **Accepted variation:** professionally equivalent evidence-code wording and any JSON organization are accepted. Rationales are not compared to golden prose.
- **Common failure:** pad partial dates, turn blanks into negative evidence, or upgrade a case-level recurrence marker into event-specific proof.

### Longitudinal evidence revision, 0.26

- **Capability:** compare each submitted state before relying on the retained state and revise earlier conclusions when follow-up evidence changes scope or assessability.
- **Professional reason:** later submissions can add an event, remove it, change the drug role, revise onset chronology, or add apparently supportive fields without repairing the binding missing fact.
- **Anchors:** version identifiers, pair membership relations, field-level changes, source locations, and expert judgment records for their effect on assessment.
- **Verifier signal:** per-version pair states, retained/rejected identifiers, material change concepts, assessment impact, and source bindings are checked per requested history.
- **Attention role:** connect versions through case identifiers and compare like-for-like product courses; ignore version number as a proxy for stronger evidence.
- **Accepted variation:** change concepts may be written as codes or concise phrases, in any order; extra non-conflicting observations are allowed.
- **Common failure:** inspect only the retained version, count both versions as cases, or call every added field a strengthened causal relationship.

## Strict scoring details

Each business dimension is a mean of per-field or per-review checks, so partial professional work receives proportional credit. Counts must be exact. Finite statistics use a relative-or-absolute tolerance for normal rounding. Controlled statuses are normalized through professional aliases. A qualitative row earns evidence credit only for concepts supported by its bound source packet; generic claims of thoroughness do not count.

The additional strict terms measure delivery quality independently: `source_integrity` verifies that the protected source extracts are present and unchanged; `exact_coverage` verifies that every requested pair, census row, driver review, retained case, and longitudinal review is represented once; `table_closure` verifies non-negative four-cell tables and population totals; and `evidence_traceability` verifies source bindings for driver, case, and longitudinal evidence. These are additive quality contributions. They do not cap a correct business result, and a duplicate version row loses its own identity/coverage credit rather than zeroing an otherwise valid review.

## Lenient completion lens

The lenient score is an additive completion lens over the same artifact:

- `contract_coverage`: requested pair, candidate-census, detailed version-review, retained-case, and longitudinal identifiers represented exactly once, plus method and limitations present;
- `table_closure`: requested four-cell tables that are numeric, non-negative, and sum to their stated population;
- `evidence_traceability`: requested driver histories and qualitative reviews carrying source references that resolve to the supplied case or report identifier.

The three rates have separate weights so a missing section, an open table, or an unbound history loses its own contribution without multiplying away unrelated completed work. This lens deliberately ignores whether the ROR, signal call, causality category, change interpretation, or disposition matches the calibrated reference. A complete but analytically wrong review can therefore have high lenient compliance and low strict capability.

`limitations` is complete when the supplied list is non-empty. The task requires a limitations section but does not prescribe particular words; professional limitations are evaluated in the substantive review dimensions rather than by a keyword list.

## Skill-attributable profile

With the methods applied, the artifact retains separate populations, closes every subgroup, reconciles the full version-driver census with selected state histories, binds each qualitative claim to version-specific rows, and revises conclusions when follow-up evidence changes. A competent ad hoc artifact is expected to calculate the obvious pooled tables but to leak rejected versions into child joins, equate state changes with pair changes, scope withdrawal or recurrence too broadly, and describe only the retained version. The scored differences are state-history closure, cross-view table integrity, evidence-scope calibration, and longitudinal revision; naming and format are not differences.

## Robustness and limits

The verifier is exercised against synonym rewrites, reordered and renamed structures, cheap-pass shells, numeric stuffing, source dumping, and a method-conformant alternate layout. Source rows are read-only and source identifiers, not agent assertions, establish traceability. The package evaluates disciplined reasoning over the supplied extract; it does not establish incidence, comparative product risk, or clinical causation, and it does not claim that one disproportionality method is a universal signal standard.

## Normalization and source provenance

Confidence-bound aliases include lower_95/lower_95_ci/ror025. Version lists may be
keyed by primaryid. Citations may be nested per evidence or keyed/bound per version,
but must still identify the actual table and row (or table plus report identifier).
A bare unrelated identifier is not evidence for all source tables. Lenient uses the
four-factor continuous formula above; merely emitting IDs and empty shells earns no
traceability or table-closure credit. Source-file integrity is verified separately.

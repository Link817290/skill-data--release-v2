---
name: analyze-disproportionality-sensitivity
description: Calculate and reconcile case-level reporting odds ratios, sparse subgroup analyses, Mantel-Haenszel common odds ratios, and policy dispositions in spontaneous-report screening. Use when drug-event signals must be tested across alternate populations without confusing disproportionality with incidence or causality.
---

# Analyze disproportionality sensitivity

This method is independent of local filenames and output schema. First map the supplied records to an observation universe, exposure membership, event membership, and requested strata; stop if those roles are ambiguous.

Start only after a population ledger exists. Every cell, subgroup, and sensitivity must point to an explicit universe; otherwise identical formulas can answer different questions.

## Convert relational rows to case sets

Build exposure and event membership as Boolean sets within each universe.

For exposure:

1. Filter the drug role before matching the ingredient.
2. Split a multi-ingredient field only on its documented delimiter.
3. Normalize case and surrounding whitespace.
4. Compare whole components against the supplied mapping contract.
5. Collapse repeated matching rows to one exposed membership per observation.

Do not use brand-name substrings, infer salts or formulations, or let a secondary suspect inherit the role of another drug in the same case.

For events, use exact preferred-term equality unless the task supplies a grouping. Collapse duplicate reaction rows. A case with several reactions contributes once to each applicable event set, not once for every drug-reaction Cartesian combination.

## Build and close each table

For exposure set `E`, event set `R`, and universe `U`, form:

```text
a = size(E intersect R)
b = size(E minus R)
c = size(R minus E)
d = size(U) - a - b - c
```

Verify non-negativity, integer type, and `a + b + c + d = size(U)` before calculating an estimate. Keep observation identifiers behind each cell so a surprising delta can be traced to cases.

For nonzero cells, calculate the reporting odds ratio as `(a*d)/(b*c)`. For an ordinary two-sided log-Wald interval, use the reciprocal-cell standard error and the quantile specified by the analysis contract. Apply no continuity correction unless the contract explicitly requires one. If a required cell is zero, mark the individual table unassessable instead of changing estimators silently.

Apply the task's minimum-count and interval rule after the table and interval close. A large point estimate does not override a sparse co-report count, and an adequate count does not override an interval that crosses the null.

## Keep sensitivities symmetric

Recompute all four cells inside every alternate universe. Do not carry the canonical exposed count into a subgroup while recomputing only the comparator cells.

Useful sensitivity families answer different failure modes:

- canonical latest-case versus all submitted versions tests follow-up duplication;
- reporter subsets test channel concentration;
- source-period partitions test temporal concentration;
- role restrictions test suspect attribution;
- alternate reference sets test masking and competition.

Name each result by both universe and exposure rule. A label such as “quarter result” is insufficient if it could mean an independent quarterly snapshot or a partition of the canonical universe.

When comparing signal calls, derive the transition label from the two actual calls. Do not infer it from the sign of a count delta or a rounded point estimate.

## Calculate a stratified common ROR

Use a Mantel-Haenszel common odds ratio when the contract requests adjustment across mutually exclusive strata. For each stratum `i`, let `n_i` be the sum of its four cells:

```text
common OR = sum(a_i*d_i/n_i) / sum(b_i*c_i/n_i)
```

The strata must partition the parent universe. A sparse stratum with a zero cell still contributes through the formula and should not be discarded merely because its own odds ratio is undefined. Mark the common estimate unassessable only if its aggregate numerator or denominator is zero, or if the strata do not close.

Never average stratum-specific odds ratios. Arithmetic, geometric, or sample-size-weighted averages are not the Mantel-Haenszel estimator and behave badly around sparse or undefined strata.

Treat the common estimate as an adjustment summary, not as proof of homogeneity. Inspect the individual stratum tables for direction changes and concentration even when no formal heterogeneity test is requested.

## Synthesize without substituting judgment

Create a dependency matrix before assigning a business disposition. Put the canonical call, version sensitivity, reporter sensitivity, period sensitivity, and adjusted estimate in separate columns. Evaluate the supplied decision policy literally from those upstream fields.

Do not upgrade a failed minimum-count call because an adjusted point estimate is large. Do not downgrade a canonical result merely because one sparse subgroup is unassessable unless the policy says that missing subgroup evidence is disqualifying. Preserve the distinction between:

- no signal under a defined rule;
- an unassessable estimate;
- a signal that lacks robustness;
- a signal that meets the escalation policy.

Disproportionality is a hypothesis-generation property of reports. It does not estimate incidence, compare treatment risks, or establish that a product caused an individual event.

## Validate claimed table math

Use `scripts/check_table_math.py` after writing a scratch JSON containing agent-supplied cells and claimed estimates:

```bash
python3 scripts/check_table_math.py --input claimed_tables.json
```

The checker reports closure and formula agreement only. It does not read source data, select observations, apply signal thresholds, or write a deliverable. Failed checks require fixing the case sets or claims, not relaxing tolerance.

## Close the analysis

Before delivery, verify:

- every requested pair appears once in every requested analysis family;
- every table closes to its named universe;
- subgroup sizes close to their parent and missing buckets were retained;
- the common estimator was built from stratum cells rather than rounded stratum odds ratios;
- version transition labels agree with their endpoint calls;
- final dispositions agree with the supplied policy;
- limitations separate reporting association from incidence and causation.

Stop if the ingredient mapping is incomplete, an observation belongs to multiple supposedly exclusive strata, the canonical ledger is unresolved, or the formula requires a denominator that is zero.

## Check comparison direction explicitly

Write down which state is the starting point and which is the destination before
naming a transition. Recompute the two calls under their own population contracts,
then check the transition against that ordered pair. Reversing the comparison
must reverse a directional transition; a count increase alone does not define it.
Preserve an unassessable call as such unless the supplied policy explicitly maps
it to another state. Use the requested transition vocabulary only after this check.

---
name: analyze-repeated-surveys
description: Compare repeated surveys and build auditable measurement-quality, small-domain, panel-composition, multiplicity, and sensitivity evidence when item versions, respondent composition, weights, linked respondents, or replicate designs affect interpretation.
---

# Repeated survey analysis

Define each estimate before calculating it. Tie every result to a period, respondent population, item family, weighting stage and unit.

Read supplied requirement, parameter, benchmark and variance-design tables together. Treat them as the analysis contract. Discover constants and families from those inputs rather than embedding assumptions.

After the two workbooks are written, run
`python /app/environment/skills/analyze-repeated-surveys/scripts/check_release.py <workspace>`.
It checks only structure — that both files exist and differ, that the per-item and
per-replicate tables are as long as their grain implies, and that published estimates carry
the labels needed to check them. It reads none of the source data and says nothing about
whether a value is right.

## Frame the analysis

Select only items and scales that the supplied mapping supports. Keep full-instrument descriptions separate from a declared comparable family.

Calculate respondent-level scores before aggregation. Preserve the exact weight used for every included respondent. Keep unadjusted, adjusted and repeated-person estimates distinct.

### The estimator chain

Score each respondent first, then aggregate — never the reverse:

- Respondent score: `y_i = mean(canonical item scores over the declared item set)`.
- Weighted estimate: `theta = sum_i(w_i * y_i) / sum_i(w_i)`, where `w_i` is the weight for the stage and population that estimate is defined on. An estimate quoted without naming its weighting stage cannot be checked.

Where the contract asks for calibration to known population margins, rake iteratively: within
each category `c` of a target dimension, scale `w_i <- w_i * target_share_c / current_weighted_share_c`.
One full pass over every target dimension is one iteration; repeat until the shares converge.
Report whether convergence was reached, per period and per replicate.

Report the weight diagnostics alongside, since a calibrated weight set is not self-evidently
sound:

- dispersion `CV = population_sd(w) / mean(w)`, over the same population as the published weights;
- effective sample size `ESS = (sum_i w_i)^2 / sum_i(w_i^2)`;
- design effect `DEFF = n / ESS`.

Both ESS and DEFF are reported per period, not pooled.

### Uncertainty from matched replicates

Where a replicate design is supplied, uncertainty comes from the replicates, not from a
textbook standard error:

`V = (G-1)/G * sum_g((theta_g - mean_g(theta_g))^2)`, `SE = sqrt(V)`, with `G` the number of
distinct groups in the supplied design.

Centre the interval on the **full-sample** estimate rather than the replicate mean:
`full_sample_theta +/- 1.96 * SE` for a normal approximation. The replicate mean is a
by-product of the variance computation, not the published point estimate.

When matched replicate groups are supplied, delete the same group from every linked period and rerun every affected upstream step. Record retained sample sizes, estimates, convergence and failure state for every group.

## Release a complete measurement-quality chain

Use one declared item family and one eligible respondent population consistently through the chain.

1. Compute weighted item means, item variances and total-score variance with the same weights and moment convention.
2. Compute weighted Cronbach alpha as `k/(k-1) * (1 - sum_j Var_w(item_j) / Var_w(sum_j item_j))`.
   Take weighted variances with `sum(w)` as the denominator, and hold the same respondent
   population across every term — mixing populations between the numerator and denominator
   produces a number that looks plausible and means nothing.
3. For every item, recompute alpha after deleting that item. Report the deleted item and remaining item count.
4. Corrected item-total correlation: `Corr_w(item_j, sum of the declared items excluding item_j)`.
   The total must exclude the focal item; leaving it in inflates every correlation.
5. For every replicate group, rebuild required weights, then recompute both period alphas and their difference.
6. With `G` valid matched replicates, use `V = (G-1)/G * sum((theta_g - mean(theta_g))^2)` and report the replicate center, SE and interval around the full-sample change.

Publish separate tables for period alphas, item-deletion diagnostics, replicate alphas and change uncertainty. A pair of alpha values alone is not a release chain.

## Stabilize small-domain decisions

Build the released domain family from the supplied eligibility and disclosure rules before inspecting effects. Do not change family membership to favor a result.

1. Compute each eligible domain's direct period estimates and change from the declared full-sample weights and item family.
2. Recompute each direct domain change inside every matched replicate and derive its replicate-centered SE.
3. Publish the complete `G x D` ledger for `G` replicate groups and `D` released domains. Downstream stabilization is unsupported without this ledger.
4. When the contract requests an empirical common prior, estimate its dispersion from the released direct changes and use the declared overall change as its center.
5. Compute `lambda_d = tau2/(tau2 + SE_d^2)` and `EB_d = center + lambda_d * (direct_d - center)`. Publish the common prior quantities and each domain's sampling variance, shrinkage factor and stabilized estimate.
6. For simultaneous inference, compute one maximum standardized deviation per replicate across
   the whole released family: `T_g = max_d sqrt(G-1) * abs((theta_dg - mean_g(theta_dg))/SE_d)`.
   The common critical value is the empirical quantile of the `T_g` distribution at the level
   the contract states — an empirical quantile of the replicates, not a normal or t table.
   Take it as an order statistic: the smallest observed `T_g` at or below which the stated share
   of replicates falls. Do not interpolate between neighbouring replicates — that invents a
   critical value no replicate produced, and because one shared value scales every interval in
   the family, the whole released family moves with it.
7. Form simultaneous intervals around the full-sample direct estimates unless the contract explicitly defines another center.

Verify that every released domain appears in every replicate, all domains use the same prior and simultaneous critical value, shrinkage factors stay in their admissible range, and intervals use the declared family rather than separate pointwise cutoffs.

Keep direct estimates, stabilized estimates, simultaneous intervals and business thresholds in separate columns. Treat stabilization as descriptive risk reduction, not causal evidence.

## Separate panel, composition and item-family evidence

Construct a strict repeated-person panel only from identity links authorized for that purpose and exactly one adopted response per person and period. Compute change at the person level. Use the sample SD of person changes for paired uncertainty; do not apply cross-sectional calibration weights unless the design explicitly requests them.

Report panel and nonpanel counts and estimates in each period to expose selection. Do not describe nonpanel records from different periods as the same people.

When decomposing a cross-sectional change into repeat and nonrepeat cohorts, use a symmetric midpoint decomposition:

- within component: `sum_c mean(period shares for c) * change in cohort mean_c`;
- composition component: `sum_c change in cohort share_c * mean(period cohort means for c)`.

Publish cohort counts, shares, means, both components and a reconciliation error. Use the same population, item family, unit and weighting state on both sides of the identity.

For a declared item family, recompute every item's period estimates and change inside every matched replicate. Derive replicate-centered SEs, two-sided p-values and one multiplicity adjustment over the complete family. For Benjamini-Hochberg:

0. Per item, `z = full_sample_change / replicate_SE` and `p = 2 * (1 - Phi(abs(z)))`, computed
   only where the replicate SE is defined.
1. Sort valid p-values ascending.
2. Compute `p * m / rank`, with `m` the size of the complete declared family.
3. Enforce monotonicity from the largest rank backward.
4. Cap adjusted values at one and restore original item order.

Publish item role, both period estimates, change, SE, test statistic, raw p-value, adjusted value and business flags separately. Do not filter the family before adjustment.

## Propagate sensitivity and boundaries

Run every sensitivity requested by the input contract across its population, item-family and weighting choices. Carry changes through direction labels, priority classes and management conclusions; explain reversals rather than selecting a preferred scenario.

Before delivery, verify these dependency closures:

- measurement results use the declared full and replicate weights;
- every released domain has direct, replicate, stabilized and simultaneous evidence;
- panel membership obeys identity permission and period uniqueness;
- decomposition components reconcile to their stated total;
- multiplicity uses the complete declared family;
- sensitivity and disclosure rules reach both tables and narrative conclusions.

Separate management thresholds from uncertainty. Avoid causal, official response-rate or external-benchmark claims unless supplied evidence supports them.

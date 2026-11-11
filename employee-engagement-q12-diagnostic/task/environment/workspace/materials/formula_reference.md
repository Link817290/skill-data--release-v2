# Formula and calibration-population reference

This file supplies the formula definitions referenced by `analysis_requirements.xlsx`. It is common task material in both the with-skill and no-skill conditions.

## Calibration population

`POP-01` and `ID-01` require submission-date employment checks but do not explicitly state whether a canonical survey response submitted outside the recorded employment interval remains in the calibration frame. Two interpretations are therefore permitted, provided one is applied consistently to response weights and every downstream estimate:

1. **Survey-frame profile:** retain every canonical, calibration-adopted response and use its survey-side frame bands.
2. **Employment-valid profile:** exclude the 13 canonical responses whose submission date is outside the recorded employment interval before calibration.

The cleaning ledger must identify the adopted profile. Mixing weights from one profile with trends, replicates, reliability, organization or sensitivity results from the other is not permitted.

## Calibration and diagnostics

- Within category `c`, update `w_i <- w_i * target_share_c / current_weighted_share_c`.
- Iterate all supplied target dimensions until the supplied convergence rule is met; either target-dimension cycle order is valid when the final margins and weights converge.
- `CV = population_sd(w) / mean(w)`.
- `ESS = (sum_i w_i)^2 / sum_i(w_i^2)`.
- `DEFF = n / ESS`.

## Matched delete-group uncertainty

For `G` valid matched replicate groups:

- `V = (G-1)/G * sum_g((theta_g - mean_g(theta_g))^2)`.
- `SE = sqrt(V)`.
- A normal interval is `full_sample_theta +/- 1.96 * SE`; the replicate mean is the variance center, not the published point estimate.

Each replicate deletes the same supplied group from both waves and reruns every affected calibration and estimate.

## Reliability

- Weighted alpha: `k/(k-1) * (1 - sum_j Var_w(item_j) / Var_w(sum_j item_j))`.
- Weighted variances use `sum(w)` as denominator over one consistent population.
- Corrected item-total correlation is the weighted correlation between the focal item and the declared total excluding that focal item.

## Small-domain stabilization and simultaneous intervals

- `lambda_d = tau2 / (tau2 + SE_d^2)`.
- `EB_d = center + lambda_d * (direct_d - center)`.
- Per replicate, `T_g = max_d sqrt(G-1) * abs((theta_dg - mean_g(theta_dg))/SE_d)`.
- The common maximum-t critical value is the supplied-level empirical order statistic of the replicate `T_g` values, without interpolation.

## Panel decomposition and multiplicity

- Symmetric within component: `sum_c mean(period shares_c) * change(cohort mean_c)`.
- Symmetric composition component: `sum_c change(cohort share_c) * mean(period cohort means_c)`.
- For each item, `z = full_sample_change / replicate_SE` and `p = 2 * (1 - Phi(abs(z)))` where SE is defined.
- Benjamini-Hochberg uses `p * m / rank`, backward monotonicity, a cap at one and restoration of original item order over the complete declared family.

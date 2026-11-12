# Manufacturing Time Workbook Scoring

The required deliverable is `standard_time.xlsx`. Original worksheet names, populated input/interface cells, merged ranges and row/column layout must be preserved. External workbook links, macros and private-path formulas are invalid. Invalid or missing deliverables score zero in both profiles.

The verifier independently derives all 195 requested results from `inputs.xlsx`. It recalculates the submitted workbook in LibreOffice under baseline and changed observations, separate ratings/allowances, batch/crew changes, demand/hours/processing changes, crew invariance, and nonzero-observation/crew interaction scenarios. Every full-workbook cell decision is binary across all scenarios.

Strict also measures individual calculation operations with verified prerequisite values. Separate worksheet copies preserve the submitted operation while supplying correct upstream results. Minimum aggregation applies to each prerequisite chain; the arithmetic mean across records or stations is the partial-credit scale (increments of 1/20 or 1/5).

| Positive Owner | Weight | Source Calculation And Coverage |
|---|---:|---|
| `statistics` | 0.20 | Measurement V/W/X/Y/Z, population deviation, nonnegative lower limit, inclusive screening; minimum per row, mean over 20 rows |
| `adjusted_time` | 0.05 | Measurement AF/AH: supplied rating, measurement allowance and batch divisor; minimum per row, mean over 20 rows |
| `station_normalization` | 0.05 | Measurement AI=AH/E; mean over 20 rows |
| `station_cycle` | 0.20 | Planning L matching the same station's handling record and O=L+N; minimum per station, mean over five stations |
| `capacity` | 0.40 | Planning Q=O*(1+P)/I and R=3600/Q; minimum per station, mean over five stations |
| `ratio_numerator` | 0.05 | Planning S numerator L+N, tested by processing-time edits at fixed handling time/activity basis; mean over five stations |
| `resources` | 0.05 | Planning V=C2/R/U and X=2*V/T, without rounding; minimum per station, mean over five stations |

Capacity carries 40% because the standard time and hourly capacity directly
drive equipment demand and staffing, so an upstream cycle error propagates to
the production decision. Measurement statistics and station cycle each carry
20%: the first controls which observations enter the standard and the second
connects those observations to each station's executable cycle. The four 5%
owners isolate narrower transformations whose failures remain professionally
visible without outweighing the end-to-end throughput chain. The weights follow
calculation dependency and downstream operational impact, not a desired score.

Planning S must use the disclosed complete-cycle expression `(L+N)/(K+M)` and have no dependency on crew J. Its numerator is measured by the positive `ratio_numerator` owner. Its denominator operation is covered exclusively by `D_ACTIVITY_BASIS`; it does not also lose positive denominator credit. Tests measure inverse response to K/M changes, J invariance, and absolute normalization with zero handling time. This catches extra L/J factors, reversed signs and arbitrary scale factors while allowing equivalent Excel expressions.

Each failed station contributes one independent instance with exponent 1/5. The sole retention coefficient is 0.3. For k failed stations, retention is `0.3 ** (k/5)`. One failed station retains approximately 0.7860 and five retain 0.3. Numerator and activity-basis errors are distinct operations with distinct evidence.

`strict = sum(weight * measured_completion) * retention`. Parameters are read from `scoring_params.json`; model and condition identities are never read. All seven positive owners have nonzero weights. Every requested cell is covered; S has separately measured numerator and denominator operations. A numerator failure loses its measured positive credit once. `D_ACTIVITY_BASIS` is reserved for a distinct denominator-causality failure and therefore does not duplicate the numerator loss.

Lenient is the conjunction of six independent binary minimum-usability decisions. It does not threshold or transform strict scores. The original plant has measurement crew E=1, planning crew J=1 and planning allowance P=0. These source conditions, rather than the complete strict generalization envelope, define minimum operational usability:

| Must-Have | Binary Evidence |
|---|---|
| Native integrity | Required workbook, original inputs/layout and external-link/macro guard pass |
| Numeric business outputs | All 195 requested outputs remain finite and nonnegative in all seven full-workbook scenarios |
| Measurement and piece time | Every row's screened Z, normal AF and per-piece AH remains correct in all seven scenarios; AI is correct at the source crew in baseline, changed observations and demand/processing scenarios |
| Conservative station cycle | Every station's L matches its own handling record; O lies in [L+N, K+L+M+N], in every scenario |
| Coherent production resources | In all scenarios with source planning allowance P=0: Q=O/I, R=3600/Q, V=C2/R/U and X=2*V/T, using the candidate's own upstream values; batch, demand, operating-hours, assignment and crew edits therefore remain tested |
| Original activity basis | Every S uses K+M, responds inversely to K/M, is invariant to J and normalizes correctly at zero handling time; S lies in [N/(K+M), (K+L+M+N)/(K+M)] in all scenarios |

The conservative intervals are constructed from named source components, with no fitted percentage tolerance. O cannot omit handling or fixed automatic time; it may conservatively include the additional K/M activity, so capacity, machine demand and staffing must consistently propagate that same O. For minimum usability, S must stay within the named source-component bounds and retain the correct K+M denominator behavior; the disclosed complete-cycle numerator is measured continuously in strict. Actual staffing still uses the supplied assignment T and multiplier 2. Hidden nonzero-P allowance conventions and AI behavior under changed measurement crew remain strict quality requirements. Diagnostic statistics still have complete strict coverage. Constants fail changed-observation and resource causes; missing deliverables fail native integrity. Detailed values and source-component bounds are recorded in `reward_detail.json`.

Recalculation/tool failures are scoring errors: the verifier exits nonzero and marks `system_error`. The artifact score uses no LLM.

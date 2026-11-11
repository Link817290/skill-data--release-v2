# Scoring

| Section | Points | Evidence |
| --- | ---: | --- |
| A | 5 | Source rows, logical population, identity use |
| B | 30 | Calibration weights and replicate variance |
| C | 15 | Reliability chain |
| D | 30 | Organization estimates and simultaneous intervals |
| E | 15 | Panel, decomposition, multiplicity, sensitivity |
| F | 5 | Files, recalculation, privacy |

`strict = awarded points / 100`, after dependency gates and privacy caps.

`lenient = 1` only when both workbooks are present and distinct, the physical
and logical populations reconcile, identity use is purpose-limited, response
weights and action evidence are present, boundaries are stated, privacy passes, and the
calibrated-trend section earns at least `0.30` of its available evidence. The last check
is the quality floor: a structurally complete workbook that does not substantiate even a
basic cross-wave calibrated trend is not a usable diagnostic. It reuses strict section B
evidence, so lenient is not independent of strict.

This allocation emphasizes exact workbook values that can be independently
recomputed. Incomplete advanced chains remain dependency-gated and cannot earn
their reserved points.

## Owner contract

`task/tests/scoring_params.json` stores the same six owners and required fields; `validator.py` rejects incomplete owner coverage or a point total other than 100 before settlement.

| Owner | What is evaluated and professional importance | Why this weight | Prerequisites and calculation | Missing versus wrong |
| --- | --- | --- | --- | --- |
| A · 5 | Source ledger, logical population and purpose-limited identity; every estimate needs a reproducible noninflated population | Compact prerequisite audit because later owners verify substantive statistics and severe misuse has explicit limits | Additive A1-A3 over source mapping, population and identity state | Missing audit fields lose components; duplicate inflation or identity misuse is an affirmative error |
| B · 30 | Calibration weights, diagnostics, company anchor trend and matched-replicate uncertainty; this is the primary engagement conclusion | Core owner and upstream basis for C-D-E | Five numeric groups, exact material recomputation and dependency release limits under one permitted population profile | Missing weights restrict release; wrong weights or mixed profiles fail exact/downstream checks |
| C · 15 | Weighted alpha, delete-item alpha, corrected correlations and replicate reliability; action requires coherent measurement | Material but subordinate to primary trend and organization action | Continuous reliability-chain evidence under calibration and replicate prerequisites | Missing chain elements reduce release; wrong values receive no keyword/table-presence fallback |
| D · 30 | Organization direct change, replicate SE, stabilization, simultaneous intervals and interpretation; prioritization must separate signal from noise | Equal to B because organization action is the main management use and has small-domain risk | Continuous direct/advanced evidence with a dependency release limit | Missing advanced evidence limits release; wrong estimates, SEs or intervals fail exact checks |
| E · 15 | Strict panel, symmetric decomposition, multiplicity, sensitivity and disclosure boundaries; prevents composition and causal overclaim | Important triangulation without outweighing primary and organization decisions | Five evidence groups with authorized links, full item family, replicates and scenarios | Missing tables lose coverage; wrong membership, decomposition, p/q or conclusions fail checks |
| F · 5 | Two distinct files, recalculation navigation and privacy; output must be usable and safe | Delivery quality is compact; privacy separately has a justified zero limit | Additive file/navigation/privacy checks plus missing/identical/disclosure limits | Missing files trigger delivery limits; direct identifier disclosure is an explicit zero error |

The section weights follow the task's diagnostic responsibilities and professional risk. Direct results retain partial credit; advanced C-D-E release is continuously limited by the weakest substantive prerequisite. The global limits distinguish unusable releases (missing/identical files, wrong population or identity use, missing reproducible weights/uncertainty, privacy disclosure) from ordinary partial completion. They are not applied by keyword.

Numeric, formula, population and table evidence is program-scored. Open diagnostic
meaning is not: D5 organization actions and the E6 causality, response-rate and
small-sample boundaries require a source-bound LLM decision with exact candidate
and source-fact quotes. Keyword-complete but false or generic prose receives zero
for those owners. The semantic decisions enter the same strict items and lenient
must-do checks. Judge failure is UNMEASURED, never business zero.

## Public numeric policy

All points, prerequisite thresholds, release floors and global limits are public coarse-grained professional policy. They are operational severity bands, not uniquely scientific constants. Their basis is the diagnostic duty, plausible professional harm and remaining usable value of correctly completed work.

Severity and remaining value are applied as follows:

- **Critical decision:** B and D. A wrong or unreproducible calibrated trend or organization release can misdirect management action. Correct audit-only or direct-estimate work retains value, while dependent advanced release is withheld.
- **Material measurement/triangulation:** C and E. Correct independent components retain proportional value; incomplete prerequisites restrict only the dependent chain.
- **High prerequisite:** A. Population and identity defects can invalidate multiple analyses, but independently verifiable downstream values are not charged again merely for repeating the same root defect.
- **Delivery and privacy:** F. Distinct usable files retain delivery value. Direct identifier disclosure leaves no releasable value and therefore has a zero limit.

Dependency release uses the weakest substantive prerequisite once. B uses coarse release levels 3, 18 or 30 depending on reproducible final weights and matched replicates. C, D and E interpolate from their public floors (2, 11 and 3) to their full section values according to the weakest prerequisite completion ratio. This preserves direct or otherwise independent work while preventing unsupported advanced conclusions from receiving release credit.

Global limits represent one root release defect each: missing deliverables retain at most 50, identical workbooks 20, wrong logical population or identity misuse 30, and privacy disclosure 0. The same root cause is not charged again for every affected table or narrative statement. If the defect already restricts dependent C-D-E work, repeated downstream manifestations do not create new independent penalties.

Missing and wrong are distinct. Missing evidence receives zero or partial item completion and may withhold dependent release. An affirmative wrong population, unauthorized identity use, wrong calibration weights, fabricated uncertainty or direct privacy disclosure invokes the corresponding error treatment. Unknown infrastructure state is not converted into a business error.


## Calibration evidence contract

B1's 10 points comprise 4 points for final weights in the cleaning ledger and
6 points for the primary trend after the analysis workbook correctly applies
those weights. B2's 4 points independently verify, for each wave, the weight
sum, sample count, extrema, ESS, design effect, margin error and both stage
iteration counts. Weights appearing only in `cleaned_samples.xlsx` cannot earn
analysis-release credit. The rubric totals 100 points. Formula definitions and
the calibration-population boundary come from the public
`formula_reference.md`; weights, analysis and evidence are independently
recomputed from the supplied materials.

### Equivalent calibration implementations

The materials specify two calibration-margin families but do not fix their
visit order within each iteration. B2 therefore validates both stage counts
against one complete reproducible path: organization margins followed by
`frame_band`, or the reverse order. Counts from different paths cannot be
spliced together. The two diagnostic counts earn credit only when the final
response weights independently recompute and both counts belong to the same
reproducible path. A different valid visit order is not penalized; wrong
weights, invented counts and omitted counts receive no credit.

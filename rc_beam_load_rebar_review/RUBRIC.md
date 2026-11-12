# Scoring Rubric

This rubric evaluates the submitted review workbook against the supplied beam
materials — the article `beam_design_article.html` and the load-combination
excerpt `load_combinations_excerpt.pdf` — and against the workbook's own
arithmetic. Scoring is deterministic and content-driven: it reads numbers,
relations, source anchors and controlled verdicts. Tab names, column order,
row-label vocabulary, unit system, sentence style and formula style are not
scored. Numerical relations remain deterministic; source-bound semantic review judges only the actual explanatory rationale in P11.

## Score Form

```text
strict = positive_earned * retention
         positive_earned = sum over the nine positive items of (weight * completion)
         retention       = product over damage instances of the smallest
                           coefficient among the deduction items in that instance
```

Weights and coefficients are read from `tests/scoring_params.json`. Each item's
completion is the fraction of its own checks the workbook satisfies (0 to 1); a
coverage shortfall scales the item rather than triggering a deduction. Each
deduction item fires once per damage instance, and instances multiply. A
workbook that cannot be opened returns completion 0 for every item.

A separate lenient 0/1 lens is reported next to the strict score (see below).
`reward` is the strict score.

## Scoring Dimensions

Nine positive items. Weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| P02 | Gravity combination derivation | A populated combination row that references the evidence sheet, carries the span term, and reproduces the factored midspan moment `Mu_reported` and the shear demand at the shear depth `Vu_reported` within one per cent | Supplied article; PDF excerpt | 0.14 | Numeric derivation |
| P03 | Combination factors | `dead_factor` and `live_factor` match the factors stated in the supplied excerpt | PDF excerpt | 0.05 | Evidence binding |
| P04 | Flexural equilibrium chain | The flexure sheet is formula-driven with at least one cross-sheet reference, solves the neutral-axis depth `c_solution` within two per cent, and closes force equilibrium to within one per cent of the tension force | Supplied article | 0.02 | Numeric derivation |
| P05 | Reported flexural capacity | Recomputed capacities agree with `Mn_reported` and `phiMn_reported` within three per cent | Supplied article | 0.13 | Numeric derivation |
| P07 | Shear candidates preserved | A populated, formula-driven shear sheet that keeps all three concrete-shear candidates and identifies the governing one | Supplied article | 0.1 | Engineering judgment |
| P08 | Recomputed shear capacities | `Vs_trial_reported`, `Vs_adopted_reported`, `Vn_adopted_reported` and an independent `Vn_max_reported` are reproduced within three per cent. Formula 15 is evaluated as `phi (Vc + 8 sqrt(fc') bw d)`; the article's printed 105.04 kip is retained as `Vn_max_source_reported` and may be flagged as an omitted-`Vc` arithmetic error rather than copied as the review result. | Supplied article, Formula 15 | 0.14 | Numeric derivation |
| P09 | Spacing relations | `s_trial` exceeds `smax_reported`, `s_adopted` does not, and the adopted steel-shear contribution covers what the demand requires | Supplied article | 0.14 | Engineering judgment |
| P10 | Finding verdicts | Of the nine checks `LC-01`, `FX-01`, `FX-02`, `FX-03`, `SH-01`, `SH-02`, `SH-03`, `SH-04`, `SH-05`, the share whose published status is the one the workbook's own inputs support and whose written sentence does not say the opposite; then scaled by the share of the open verdicts (`SH-02`, `SH-04`) the review keeps | Workbook's own recomputed relations | 0.14 | Multi-step reasoning |
| P11 | Register close-out columns | Share of finding-register rows carrying a controlled status together with a non-empty source locator and rationale | Submitted workbook | 0.14 | Domain communication |

The weights split the engineering review into load/flexure derivation (34%),
shear derivation and spacing judgment (38%), and controlled finding close-out
(28%). Shear carries the largest share because the supplied article contains
three competing concrete-shear candidates, an adopted stirrup contribution,
two spacing comparisons and a disputed section-capacity expression that must be
kept distinct. Flexure remains substantial because demand, equilibrium and
capacity form one traceable chain. The register receives 28% because correct
calculations are not a usable review until their verdict, source and rationale
are closed out. These are capability shares, not a target-score adjustment.

Partial credit is the rule: P02-P05 and P07-P09 are the mean of the individual
checks listed for them, and P10 and P11 the fraction of the checks or register
rows that qualify. P02-P05 and P07-P09 are additionally scaled by the share of
their scope's checks — load, flexure, shear — whose verdict the workbook does not
reverse.

### Accepted equivalent expressions

- The evidence ledger may sit on any tab that reads as an input or evidence
  register; its value, unit, state, locator and quote columns are found from the
  header row.
- A quantity may be named by its engineering symbol (`d'`, `f'c`, `A's`) or by a
  written quantity name rather than a field key, and a number may be declared in
  any unit the row itself states, which the scorer converts before comparing.
- Register rows are recognised by what they are about, not by the reference
  finding ids or exact wording, and may sit on the finding register or on the
  closing page.
- Controlled statuses accept leading professional qualifiers: `PASS` also as
  accepted, conforming or verified; `FAIL` also as rejected or non-conforming;
  `REVIEW` also as hold, open, pending, unresolved or not verifiable. A register
  that declares its own controlled vocabulary on a legend row scores the same.
- A single stated yield strength serves for both flexural and shear
  reinforcement.
- A verdict published as a formula is read as the value the cell resolves to,
  not as the first controlled token in the formula text.
- None of this relaxes a number, a relation or a verdict.

### Verdict coherence

A check's verdict is stated in three places: the register status, the
calculation sheet, and the sentence printed beside the status. Where they
disagree, the review has no verdict for that check, and moving one of them is
not cheaper than moving all three. A sentence that says nothing decidable costs
nothing; a comparison is read only where the sentence names what is being
compared against, because exceeding a cap and exceeding a demand are opposite
results. The two open verdicts — the trial spacing that exceeds the maximum
spacing, and the two effective-depth conventions — are what the review exists to
produce, so reversing one costs the items that own it as well as the deduction.

## Deductions

Each damage instance multiplies the score by its coefficient.

| Item | Error | Damage instances | Coefficient | Rationale |
| D01 | The workbook's resolved inputs are not this beam: fewer than four of the independently readable source anchors are reproduced | once | 0.1 | Nothing in the workbook is bound to the supplied materials |
| D02 | A published status contradicts the relation the workbook's own inputs establish | one per check, `LC-01` excepted | 0.8 | The register states a conclusion its own numbers refute |
| D05 | A published status contradicts the calculation sheet that shows the same arithmetic | one per check | 0.9 | Two reviews in one workbook; neither can be relied on |
| D06 | The closing disposition is not defensible: no declared disposition covers an open item, or the closing page never mentions an open status | one per condition, at most two | 0.7 | The close-out does not account for the exceptions the review leaves behind |
| D07 | An open verdict (`SH-02` or `SH-04`) is reversed | one per open check | 0.9 | The exceptions are the substance of an independent review |
| D10 | A formula links to another workbook or fetches a URL | one per formula cell | 0.7 | The deliverable must be usable offline and bound to the supplied materials |

A deduction is charged only where the row is bound to the check by its own
quantities, its own finding id, or the check's terms in its own label, and only
where the workbook's own recomputation supports the same verdict as the supplied
materials. `LC-01` is credited but never charged, because a register that
answers it splits it into an arithmetic row and a scope row.

Interactions with the dimensions:

- A reversed verdict also reduces the proportional factor on every positive item
  in that scope: `LC-01` scales P02 and P03, the `FX` checks scale P04 and P05,
  and the `SH` checks scale P07-P09.
- A reversed open verdict additionally reduces P10 through the open-verdict
  share, on top of D07.

## Automatic Failure

There is no automatic failure for formatting. A workbook that cannot be opened
or parsed earns no completion on any item and scores 0. Everything else is a
completion fraction or a multiplicative deduction.

## Lenient Lens

The lenient lens is 1 only when the workbook binds this beam, reproduces the
factored actions and flexural capacities, retains all three shear candidates,
uses the complete Formula 15 expression including `Vc`, closes the resulting
section-capacity verdict against `Vu`, and keeps both open verdicts intact.
These are independent must-have checks; lenient does not cap or rescale the
continuous strict score. Otherwise it is 0.

### Formula 15 source correction

The supplied article displays `Vu <= phi (Vc + 8 sqrt(fc') bw d)` but prints
`105.04 kip`, which is the value of the second term alone after applying `phi`.
An independent review must preserve that printed value for traceability and
also show the governing `Vc` candidate in the recomputation. The corrected
ceiling is therefore `phi (Vc_governing + 8 sqrt(fc') bw d)`, approximately
`138.73 kip` for the supplied beam. This separates a source arithmetic error
from the engineering result while allowing the review to identify and explain
the discrepancy.

## Worksheet repair: public verdict and rationale

Published register statuses are preserved independently from calculation-sheet statuses.
An agreeing calculation never overwrites a wrong public status. D05 records each actual
register-versus-calculation contradiction at its declared coefficient (0.9); absence alone
is not a contradiction. P11 requires a meaningful source-bound explanatory reason, not a
Finding_ID. Header normalization excludes ID/code/key columns from rationale columns.
Required rationale adjudication uses environment configuration and exact submitted spans;
service/schema errors exit 2 without a score. Numerical tolerances remain unchanged.

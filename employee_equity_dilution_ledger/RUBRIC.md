# Scoring Rubric

The deliverable is `/workspace/employee_equity_dilution_ledger.xlsx`, built only from the annual report and proxy statement supplied under `/workspace/materials`. This rubric is derived from those filing materials and the reference workbook. Scoring evaluates the substance of the ledger — the figures, the reconciliations, the cited sources and the interpretive decisions — not sheet names, column order or wording. Numeric/formula/structure owners are programmatic; open-ended interpretation, source limitation, polarity and equivalent explanations require the source-bound semantic gate. Gate failure is UNMEASURED.

## Score Form

```text
strict = positive_earned * retention
         positive_earned = sum over the nine positive items of (weight * completion)
         retention       = product over damage instances of the smallest
                           coefficient among the deduction items in that instance
```

Weights and coefficients are read from `tests/scoring_params.json`. Each item's completion is the share of the reference cells it stands for that the workbook carries (0 to 1); an item is credited cell by cell, so a partly complete ledger earns a partial share. A separate lenient 0/1 contract lens is reported next to the strict score (see below).

## Scoring Dimensions

Each item is one positive item. Weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| --- | --- | --- | --- | --- | --- |
| R01 | Option ledger movements | The full-value pool multiplier and aggregate options exercised appear as inputs, and the option class carries its beginning balance, exercises, forfeitures and expirations | Annual report, stock option activity and Equity Incentive Program | 0.05 | Source extraction |
| R03 | Full-value grants, ending balances and the reconciliation control | RSU and PSU grants and ending balances, plus a control line stating that the named subtotal plus the residual equals the aggregate | Annual report activity tables; workbook controls | 0.05 | Ledger reconciliation |
| R04 | Diluted-share denominator | A disclosed, date-consistent share denominator carried into both scenarios: either the basic weighted-average share count or the year-end outstanding count when the workbook identifies and consistently applies that point-in-time basis | Annual report, earnings-per-share note and year-end balance sheet | 0.16 | Dilution modelling |
| R06 | Residual population and option increment | The residual "other employees / unassigned" exercise figure, and the treasury-stock option incremental shares reported on both scenario sides | Proxy, Option Exercises and Stock Vested; annual report aggregate | 0.06 | Dilution modelling |
| R10 | Available future capacity | The disclosed available future pool is reported in the dilution summary on both scenario sides, as capacity rather than dilution | Annual report, Equity Incentive Program | 0.15 | Plan capacity |
| R13 | Exercise-value locators | Cash proceeds and intrinsic value are cited to the annual report's option exercise information | Annual report, option exercise information | 0.05 | Evidence citation |
| R14 | Full-value forfeitures | RSU and PSU forfeitures carried on the award ledger | Annual report, RSU and performance-unit activity | 0.16 | Ledger reconciliation |
| R15 | Judgment-log evidence locators | The performance-unit maximum decision and the pool-multiplier-versus-dilution decision each cite the Equity Compensation Plans footnote | Annual report, Equity Compensation Plans footnote | 0.22 | Interpretive judgment |
| R16 | Plan maximum and option moneyness | The plan table's maximum outstanding securities cited to the plan footnote, and a note that only in-the-money options contribute to the treasury-stock increment | Annual report, equity compensation plan footnote | 0.10 | Dilution modelling |

## Per-owner rationale and settlement contract

Weights reflect source coverage, reconciliation propagation and dilution decision
importance. Completion is the fraction of bound units. Missing
and wrong units lose positive completion; only enumerated adopted inversions or
structural harms receive a multiplicative deduction.

| Owner | Evaluates | Importance / relative weight | Preconditions | Calculation | Missing vs wrong |
|---|---|---|---|---|---|
| R01 (0.05) | Option movements and pool inputs | Basic extraction block | Input and option rows identifiable | Mean bound-unit completion | Missing/wrong units lose fractions |
| R03 (0.05) | RSU/PSU grants, endings and control | Basic roll-forward closure | Award ledger/control present | Mean bound-unit completion | Missing/wrong loses fractions; disclosed omissions may trigger D06 |
| R04 (0.16) | Basic denominator in both scenarios | High propagation to every dilution result | Input/base/max columns bound | Mean of three units | Missing/wrong loses fractions |
| R06 (0.06) | Other-employee residual and option increment | Required bridge from named subset to company aggregate | Subtotal/residual/aggregate present | Mean bound-unit completion | Missing/wrong loses fractions; asserted census may trigger D03 |
| R10 (0.15) | Future capacity on both sides | High plan-capacity decision value | Capacity row/scenarios bound | Mean of two; exact 13,059,834 or disclosed rounded 13.1m accepted | Missing/wrong loses fractions; multiplier inversion may trigger D04 |
| R13 (0.05) | Exercise-value locators | Evidence quality, not core amount | Exercise facts present | Mean locator completion | Missing or wrong citation loses fraction; external source may trigger D07 |
| R14 (0.16) | RSU/PSU forfeitures | High roll-forward propagation | Award rows bound | Mean bound-unit completion | Missing/wrong loses fractions and may trigger D06 |
| R15 (0.22) | PSU/max and multiplier judgment evidence | Highest interpretive double-count/capacity risk | Judgment text, locator, arithmetic direction | Mean decision/locator completion | Missing or wrong judgment loses fractions; stated inverse may trigger D02/D04 |
| R16 (0.10) | Plan maximum locator and moneyness | Material plan/TSM boundary | Plan footnote/formula note | Mean of two prose units | Missing or wrong note loses fractions; outside source may trigger D07 |

Partial credit is awarded per reference cell within each item, so an item with six cells moves in sixths. A figure counts when it appears on a row that names the reference's row label or that carries the reference's column header — a figure sitting somewhere else in the workbook does not answer for it. Formula cells are evaluated rather than read from a cached value, so a workbook that computes its figures scores the same as one that writes them out.

### Accepted equivalent expressions

- Labels are matched on their significant words, so at least half the reference label's words must be present. `Exercises / vests` is met by "Exercised", "Vested" or "Exercises and vests"; `Ending (formula)` by "Ending balance" or "Closing"; `Other employees / unassigned aggregate` by "Other employees", "Non-NEO" or "Residual"; `Base / target` and `Maximum / upside` by "Target"/"Base case" and "Max"/"Upside".
- Sheet titles count towards a row's label words, so a class-per-sheet layout reads the same as a class-per-row ledger.
- Figures match within the larger of 0.03 and one tenth of a percent of the reference value. Accounting parentheses, Unicode minus signs, en- and em-dashes, thousands separators, currency symbols and percent signs are normalised, and a movement presented as a negative counts as the same movement.
- Prose lines are matched on their content words, so "Beginning + movements = ending" is met by "Beginning balance plus movements equals the ending balance", and "Only in-the-money options contribute" by "Only options in the money are included".
- Locator phrases are matched the same way: "Annual report, Equity Compensation Plans footnote" is met by "Equity Compensation Plans footnote of the annual report" and similar phrasings.

## Deductions

Each damage instance multiplies the score by its coefficient.

| Item | Error | Damage instances | Coefficient | Rationale |
| --- | --- | --- | --- | --- |
| D01 | One or more of the required sheets — source inputs, award roll-forward, exercise/vesting ledger, dilution summary, control checks — is absent | once, however many are missing | 0.1 | The workbook does not present a traceable ledger |
| D02 | The PSU maximum is stated as additional to the target population rather than as an alternative scenario | once | 0.6 | The same units are counted twice |
| D03 | Named-officer exercises are asserted to be the whole population, with no reconciliation residual | once | 0.5 | The proxy table is a disclosed subset, not a census |
| D04 | The plan's share-counting multiplier is described as a dilution factor | once | 0.8 | Plan capacity is confused with the diluted share count |
| D05 | Shares withheld for tax are re-entered as a new issuance | once | 0.8 | An issuance the filing never reports is added to the option ledger |
| D06 | A disclosed fact every ledger must carry is missing from the workbook: one of 28 reference figures (source inputs, option/RSU/PSU beginning balances, grants, exercises or vests, forfeitures, expirations, weighted-average prices, ending balances) or one of the five named officers | once per missing unit, bounded retention | 0.85 | The ledger does not cover the award classes and exercise population the brief requires |
| D07 | A text cell cites a source outside `/workspace` (a data vendor such as Bloomberg or FactSet, a web address, a press release, analyst or broker research), unless the cell negates it | once | 0.5 | The brief allows only the supplied materials |
| D08 | A text cell is written in Chinese, Japanese or Korean script | once | 0.5 | The workbook must be in English |
| D09 | The workbook does not state the reporting date 31 December 2024, or carries no share or no dollar unit | once | 0.3 | The disclosed units and dates are not preserved |
| D10 | The scored workbook is not named `employee_equity_dilution_ledger.xlsx` | once | 0.1 | The deliverable is not at the path the brief names |
| D11 | No formula in the workbook refers to another sheet | once | 0.3 | The dilution analysis is not formula-driven with cross-sheet references |

Interactions with the dimensions:

- D06 figures are read anywhere in the workbook, in shares, thousands or millions (prices and multipliers as written), with formula cells evaluated; a name counts when it appears in any text cell. A complete ledger carries all 33 units, so D06 charges only a ledger that has lost part of its content. Repeated omissions use a bounded retention floor so one bookkeeping gap cannot erase otherwise correct work.
- D02 through D05 charge what the workbook states in its own sentences. A row is read for an issue only when its text names that issue; the row's own title cell and any citation cell are read as headings and citations, not as claims, and the stance is taken from the remaining sentences.
- A clause in the irrealis mood — "adding both would double count", "recognising both would count the same award twice" — names an outcome being ruled out. It can support the defensible direction but never establishes the inverted one.
- A workbook that is silent on an issue, or wrong about it in some other way, is charged nothing: only the stated inversion is a damage instance.
- The deductions do not by themselves remove item credit. A missing sheet costs the items whose cells lived on it, and the D01 coefficient then applies to whatever credit the rest of the workbook earned.

## Numeric policy, severity and remaining value

Weights and retention coefficients are public coarse-grained policy, not uniquely
scientific constants. They reflect source coverage, propagation and professional
consequence. Missing and
wrong bound units both lose positive fractions. A coefficient applies only to a
distinct additional harm; lower coefficients are more severe and preserve less
otherwise correct value.

Severity bands are D01/D10 **critical operational contract** (`0.10`), D09/D11
**high usability** (`0.30`), D03/D07/D08 **high population/evidence/language**
(`0.50`), D02 **material double count** (`0.60`), D04/D05 **bounded
interpretive duplication** (`0.80`), and each D06 missing give-away unit
**incremental completeness** (`0.85`, with the documented floor). D02–D05 can
coexist with lost owner credit because the coefficient prices an additional
adopted inversion. One causal mistake is charged once even if repeated; unrelated
mistakes multiply. This preserves unaffected owner value and prevents same-root
double charging.

Lenient is unchanged by these numeric policy values because it uses must-do
completion and D01/D06 occurrence, not a strict threshold.

## Automatic Failure

There is no automatic failure. A workbook that cannot be opened or parsed earns no item credit and scores 0; every other error is a partial-credit shortfall or a multiplicative deduction.

## Lenient Lens

A 0/1 must-do lens is reported next to the strict score, settled from the same ledger. It is 1 only when R01, R03, R04 and R06 are each complete (completion 1.0) and neither D01 (a required sheet missing) nor D06 (a give-away unit missing) is charged; otherwise 0. A workbook that cannot be parsed scores 0 on both lenses.

# Scoring Rubric

This rubric is applied to the three deliverables in `/workspace/output/` — `inspection_report.json`, `repaired_plan.dxf` and `repair_memo.md` — read against the two supplied criteria documents `legacy_airfield_criteria.pdf` and `current_airfield_criteria.pdf`. Scoring evaluates applicability judgment, the substance of the inspection conclusions, evidence binding, and the measured geometry of the repaired drawing. It does not reward prose similarity to a reference answer, a particular JSON field vocabulary, or a particular sheet layout.

## Score Form

```text
strict = positive_earned * retention
         positive_earned = sum over the positive items of (weight * completion)
         retention       = product over damage instances of the smallest
                           coefficient among the deduction items in that instance
```

Weights and coefficients are read from `tests/scoring_params.json`. Each dimension's completion is the share of that dimension's own checks the submission satisfies, clipped to 0 to 1; `P05` carries internal sub-weights that are described with the dimension below. Strict and binary lenient are both reported; `reward` aliases strict. Lenient requires P02/P06/P09 complete and no D03/D04 damage. P09 must preserve the evidence-bound unresolved land-use finding.

Semantic equivalence is adjudicated by the configured source-bound LLM judge (`gpt-5.6-sol` by default), with exact candidate spans required as evidence. The judge evaluates the adopted meaning, negation, attribution, scope, and equivalent professional wording; it does not award credit for a keyword list. Deterministic checks remain responsible for source-file hashes, numeric tolerances, PDF locators, required deliverables, and parsed DXF geometry.

Three dimensions — repaired geometry, `P03` evidence traceability and `P05` cross-deliverable closure — are scored on citations, parsed coordinates and repeated nouns, none of which carry a disposition direction. Their completions are therefore multiplied by `1 - conclusion_reversal_rate`, a continuous factor measuring how systematically the report affirmatively states the opposite of the required call. The rate is the larger of two independently measured families: flipped categorical claims, and retain/repair dispositions stated against the direction the record's own numbers support. Each family is measured only once it has at least three filled slots, so an incomplete or merely wrong submission is not touched by it.

## Scoring Dimensions

The transition surface listed in current_airfield_criteria.pdf Table 4-7 item 14 is a vertical/profile matter. Because the task supplies a plan-view record without profile or elevation evidence, a correct submission records an explicit scope hold and does not invent a plan-view polygon for it.

Eight positive items; the weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| P01 | Applicability and control | Seven decisions: the service and facility branch carried with both per-end CHAPI guide angles; the conditional table remark scoped to another facility class excluded; the current document resolved as controlling and the legacy document as the inspected baseline; the two approach ends separated as differing conditions; the east normal-CHAPI case resolved onto the service-specific figure as a repair; the west non-standard end identified as requiring an adjustment whose input the record does not supply; and the west boundary held rather than inferred | `inspection_report.json` against both criteria PDFs | 0.05 | Domain judgment |
| P02 | Findings retained as compliant | Four of the twelve findings: the helipad pad size, the primary surface size and centering, the clear-zone length from the primary-surface edge on each reciprocal end, and the APZ I length continuing from the clear zone — each carried as a distinct, source-bound record stating a retain disposition | `inspection_report.json` against both criteria PDFs | 0.05 | Domain judgment |
| P03 | Evidence traceability | Seven bindings: the document-control call; the clear-zone change, the APZ change and the east CHAPI change each bound to both the legacy and the current locator; the west adjustment hold; the terminal-elevation conflict bound to both of its conflicting locations; and the unresolved plan-view limit | The findings records in `inspection_report.json` | 0.23 | Evidence discipline |
| P04 | Repaired geometry | The measured geometry of `repaired_plan.dxf`: the expected controlling polygons (helipad, primary surface, clear zone, APZ I, east CHAPI clearance surface) present, centered at (0, 0) with east on +X, at the repaired dimensions; scaled by the conclusion-reversal factor like the other undirected items | `repaired_plan.dxf` | 0.05 | Applied calculation |
| P05 | Cross-deliverable closure | Four checks: the report's dimensional basis agrees with the measured drawing and its west handling; the memo carries every basis value and distinguishes retained from repaired items across the reciprocal ends; the west design hold and its conflicting terminal elevations reach the memo with no mirrored polygon claimed; and the open grade, elevation and obstacle limits reach the memo | `inspection_report.json`, `repaired_plan.dxf` and `repair_memo.md` together | 0.05 | Multi-step reasoning/self-checking |
| P06 | Findings repaired as nonconforming | Three of the twelve findings: the clear-zone envelope changing from a constant legacy width to a flared start and end width, the APZ I envelope changing the same way, and the east CHAPI clearance surface replacing the legacy slope, length and terminal width with the normal-condition values — each a distinct, source-bound record stating a repair disposition and carrying both the legacy and the current numbers | `inspection_report.json` against both criteria PDFs | 0.14 | Domain judgment |
| P07 | Findings held, excluded or left unresolved | Six of the thirteen findings: the west non-standard CHAPI design hold with its guide angle and missing input; the terminal-elevation conflict held for clarification; the asymmetric per-end geometry disposition; APZ II excluded on a rotary-wing basis; transitional surface H held because the plan-view packet lacks profile/elevation evidence; and the plan-view grade, elevation and obstacle limits left unresolved pending survey | `inspection_report.json` against both criteria PDFs | 0.21 | Domain judgment |
| P09 | Land-use limitation carried open | One sentence of the report carries property or land-use control as something that cannot be established from the supplied record, without closing it positively | `inspection_report.json` | 0.22 | Evidence discipline |

### Partial credit

`P01`, `P02`, `P03`, `P06` and `P07` award their weight in proportion to the checks independently satisfied, so each supported decision or finding earns credit on its own. `P09` is a single statement and scores 0 or 1.

`P05` distributes its own weight as two fifths for the report-to-drawing basis agreement and one fifth each for the three memo checks.

### Accepted equivalent expressions

- A retain disposition is read from `retain`, `no change`, `unchanged`, `keep`, `kept`, `conforms`, or a clause that carries the item `forward`. A repair disposition is read from `repair`, `nonconform`, `replace`, `revis`, `correct`, `deficien`, `supersed` or `substitut`. A record that carries both, or neither, states no direction and does not fill a directional slot.
- JSON field names are dropped before any decision pattern is applied, so renaming keys costs nothing and a key named after a requirement cannot by itself supply a conclusion the submission never wrote.
- A decision cue preceded by a negator within the same clause (`no`, `not`, `never`, `without`, `none`, `rather than`, `instead of`, `need not`, `does not`) states the opposite and does not earn the credit reserved for asserting it. An instruction-style phrase that tells the reader not to infer, mirror, draw, add, choose or certify something is itself the correct claim and is not read as negation of the surrounding decision.
- A resolvable location inside a cited PDF may be a printed page, table, figure, note, section, item, paragraph or appendix reference; naming the file alone is a bibliography and does not close a decision.
- Numeric agreement uses a tolerance of `0.08 m` for dimensional values, and `0.011` for the reference values read from single statements. Level notations differing only in separators or in a degree sign are normalised before matching.
- Geometry is compared by parsed coordinates. Entity order, color, linetype and layer-naming variation do not affect substantive geometry credit; angular alignment on the centerline uses the same `0.08 m` offset tolerance about the X axis.

### Distinctness

Each of the thirteen findings must be a separate record in the report. A record already claimed by one finding cannot be claimed again, so a single omnibus paragraph that mentions every condition closes one finding, not thirteen. The dimensional-basis block, which lists every value at once and cites nothing, does not satisfy the per-item finding searches because those require a source-bound record.

## Deductions

Each damage instance multiplies the score by its coefficient. Every item below fires at most once per submission.

| Item | Error | Damage instances | Coefficient | Rationale |
| D01 | A locked criteria PDF is missing from the workspace or its hash does not match `tests/ground_truth.json` | once | 0.6 | The inspection was not carried out against the supplied record |
| D02 | The conflicting terminal-elevation values are settled on one value instead of held for clarification | once | 0.6 | Silently choosing between two conflicting source values manufactures a design input |
| D03 | The east normal-CHAPI controlling surface is left unsettled — referred to an authority for its applicability or dimensions, drawn at another facility class's terminal width, or offered as two rival polygons with no selection | once | 0.6 | The one end the supplied record fully dimensions is not delivered as controlling geometry |
| D04 | A mirrored west normal-CHAPI clearance surface is drawn | once | 0.6 | Geometry is asserted at the end whose dimensional dependency is open |

Interactions with the dimensions:

- `D01` zeroes the reported dimension scores, but the ledger completions are computed regardless, so the charge is the coefficient rather than a silent total loss.
- `D03` is not covered by the reversal factor, which has no east-surface family.
- An east-surface sentence that merely excludes an inapplicable branch, or that discusses the west end only, does not trigger `D03`.

## Automatic Failure

There is no automatic failure for formatting alone, but a missing or empty required deliverable (`inspection_report.json`, `repaired_plan.dxf` or `repair_memo.md`) sets every positive completion to 0 (required-deliverable gate). A submission with an unreadable `inspection_report.json` earns no report-based completion; an unreadable `repaired_plan.dxf` earns nothing for the checks read from the drawing. All other errors are multiplicative deductions rather than score caps, and the final score is the product of earned credit and retention.

2026-10-24: P09 and east-authority holds use mandatory evidence-bound semantic adjudication. Candidate-positive property closure is rejected even if it also uses a pending keyword; east hold synonyms are understood in context. Required service failures abort scoring. Source PDFs and offline wheels are size/SHA checked; wheel ZIP CRC is validated before installation.

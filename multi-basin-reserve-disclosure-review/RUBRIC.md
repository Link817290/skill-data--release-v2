# Scoring Rubric

The scored submission is `/workspace/output/reserve_disclosure_review.md` together with
`/workspace/output/reserve_disclosure_register.csv`. Scoring evaluates the review
conclusions the supplied filing package actually supports — the classification call, the
cross-table relationship, the evidence binding, the disposition boundary, and the usable
action. It does not require reproducing the reference wording, column labels, row order,
or section order.

## Score Form

```text
strict = max(0, positive_earned - deduction_total)
         positive_earned = sum over P01-P11 of (weight * completion)
         deduction_total = sum over root-deduplicated damage amounts
```

Weights and deduction amounts are read from `tests/scoring_params.json`.

For `P01`-`P10`, completion is the credit earned on the single register row that best
supports that matter, clamped to the range 0 to 1:

```text
completion          = judgement_credit + support_credit * local_support_scale
local_support_scale = dimension_judgement_credit / dimension_judgement_capacity
```

`P11` directly measures end-to-end evidence closure and is not scaled by an
unrelated dimension.
Credit is row-local: tokens scattered across unrelated rows do not combine into a finding.

A lenient lens is reported next to the strict score (see below). Both scores lie between
0 and 1, neither is folded into the other, and no pass threshold is defined. `reward.txt`
carries the strict score for consumers that require a single scalar.

## Scoring Dimensions

Each expert matter is one positive item. Weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| --- | --- | --- | --- | ---: | --- |
| P01 | PUD bridge contradiction | Reproduces the proved-undeveloped bridge (6,193 / 15,670 / 2,698 / 377 / 24,128 MBoe), states the conflict between the parenthesized extension/discovery movement and the 0.4 MMBoe Canada additions narrative, keeps the ending balance unchallenged, and asks for a movement schedule instead of merely reversing a sign | `annual_report.html` — Proved Undeveloped Reserves table and the adjacent extensions narrative | 0.12 | Cross-table reasoning |
| P02 | Current product-to-BOE propagation | Converts the Canada oil (93) MBbl, gas 234 MMcf and NGL 40 MBbl movements at the disclosed 6:1 factor to the (14) MBoe summary amount, explains that agreement across tables propagates the printed classification rather than validating a negative discovery, and leaves the corrected split unresolved pending a property-level schedule | `annual_report.html` — Reserve Information product tables and Total Reserves table | 0.12 | Unit conversion / classification judgment |
| P03 | Comparative-period category swap | Converts the comparative oil 93 and 810 MBbl, gas 3,219 MMcf and NGL 505 MBbl extensions to 1,944.5 → 1,945 MBoe, identifies the purchase/extension swap against a zero-purchase product table, preserves the comparative ending quantity, and reopens trend or replacement statements built on the affected categories | `annual_report.html` — comparative Reserve Information product and Total Reserves tables | 0.10 | Cross-table reasoning |
| P04 | Standardized-measure dependency | Connects the unreliable quantity categories to the $8.318 million extension and $144.956 million revision lines in the standardized-measure change table, explains that the dollar allocation is not derivable from volumes without property timing, costs, taxes and discounting, and asks for a property-level rerun or bridge rather than a prorate | `annual_report.html` — Changes in Standardized Measure of Discounted Future Net Cash Flows | 0.08 | Scope control |
| P05 | PUD plan-population support | Separates the annual-review and five-year booking-policy text from evidence covering the complete current PUD population including acquired locations, stops short of concluding a violation, and requests booking dates, aging, an adopted and approved plan, conversion timing, delays and exceptions | `annual_report.html` — Proved Undeveloped Reserves and reserve-policy text | 0.08 | Evidence-bound restraint |
| P06 | Applied-technology discussion | Distinguishes a reliable-technology definition, input list and control narrative from a discussion of technologies actually applied; names the engineer methods (performance, volumetric, analogy, reservoir modeling) as partial scope-limited support; identifies the issuer-level gap and proposes a discussion tied to material additions | `annual_report.html` — Controls over Reserve Estimates; `engineer_egypt.html`, `engineer_gabon.html`, `engineer_cote_divoire.html` — methods paragraphs | 0.08 | Domain communication |
| P07 | Significant purchase narrative | Compares the 16,465 MBoe current purchase tied to the Svenska acquisition with the 18,496 MBoe comparative purchase and the TransGlobe transaction, keeps narrative completeness separate from the comparative category error, and proposes a period / geography / transaction explanation or cross-reference | `annual_report.html` — Total Reserves table and acquisition descriptions | 0.12 | Narrative consistency |
| P08 | Engineer ending-balance clearance | Reconciles the four engineer totals (9,448.1, 11,063.1 and 15,251.6 MBbl, 6,551.3 MMcf, 8,126 MBoe) to the issuer's 45,018 MBoe ending proved reserves using the disclosed 5.8:1 gas factor, preserves evaluation scope and management-input reliance, and states that ending-balance agreement does not clear movement labels | `engineer_egypt.html`, `engineer_gabon.html`, `engineer_canada.html`, `engineer_cote_divoire.html` — total proved sections | 0.08 | Multi-source reconciliation |
| P09 | Property-price clearance | Clears the $70.81 reference versus $69.12 property oil price difference using the stated quality, transportation and market-differential adjustments and the constant-price treatment, rather than forcing the two prices to match | `engineer_canada.html` — pricing paragraph and tables | 0.08 | Domain judgment |
| P10 | Competing reserve/value bases | Separates 45.0 MMBOE SEC proved with a $379.4 million standardized measure from 96.1 MMBOE 2P working-interest reserves before royalties with $686.6 million PV-10, using reserve class, framework, royalty, pricing, cost and non-GAAP qualifiers; does not manufacture a reconciliation and does not overwrite the source's own income-tax definition | `earnings_release.html` — Year-End Reserves, PV-10 Value and Probable Reserves, WI CPR Reserves | 0.06 | Framework separation |
| P11 | Evidence and artifact closure | Register rows are substantive and source-located, memo conclusions cross-reference register identifiers, and the filing-readiness conclusion covers required corrections, cleared apparent issues and unresolved evidence needs without asserting the package is ready as filed | Both deliverables | 0.08 | File handling / artifact closure |

The weights follow disclosure consequence and the amount of independent
professional reasoning each matter controls. P01, P02 and P07 receive 0.12 each
because they govern the principal movement contradictions or a material
acquisition narrative and therefore affect both the table and management's
explanation. P03 receives 0.10 because the comparative category swap is a
closed cross-table error with direct trend consequences. P04-P06, P08, P09 and
P11 receive 0.08 each: they are material scope, evidence, clearance and closure
owners, but none alone changes both the principal movement bridge and its
narrative. P10 receives 0.06 because it prevents an invalid comparison between
different reserve frameworks while remaining analytically separate from the
issuer's primary SEC movement correction. These are relative professional-risk
weights; they are not pass thresholds, and each owner still awards continuous
credit for its own completed sub-items.

### Partial credit

Each `P01`-`P10` dimension is built from sub-items whose weights sum to 1 within the
dimension:

- one **fact** sub-item (0.20 to 0.35, absent where the matter carries no figures) for
  reproducing the disclosed quantities, entities and units;
- three or four **judgement** sub-items (0.10 to 0.30 each) for the relationship, the
  conclusion, the boundary the conclusion must not cross, and the proposed action;
- one **evidence** sub-item (0.10) for naming the supplied file or files together with a
  section, table, exhibit or comparable locator.

Every dimension carries an anchor set of figures — or, for `P05` and `P06`, the specific
policy horizon and method facts. The judgement and evidence sub-items are conditional on
the whole anchor set appearing in the row, so perturbed figures or wording alone cannot
buy judgement credit. The fact sub-item is not conditional on the anchor set.

`P11` is scored on the register and memo as a whole: `0.30` substantive rows, `0.25`
evidence-bearing rows, `0.25` share of register identifiers cross-referenced by the memo,
and `0.20` for a readiness conclusion that names corrections, clearances and open evidence
needs and does not assert the package requires no correction.

### Direction and accepted equivalents

A dimension is zeroed when the row asserts the inverse of the supported conclusion — for
example that arithmetic closure validates the negative extension category, that the printed
categories are already correct, or that no correction is required. Direction is read by
polarity, not by phrase lists: text is cut into clauses and again at contrastive markers
(`rather than`, `instead of`, `, not`), and a negation lexicon sets the sign of each
segment. A wrong-direction phrase that sits inside a negation is the correct statement and
counts as affirmation.

- Equivalent professional wording is accepted throughout; each conclusion is matched
  against several paraphrases (`conflict`, `contradict`, `inconsisten`, `irreconcil`,
  `at odds`, `cannot both`, and their equivalents).
- Reordered rows, alternate row identifiers and changed column labels are accepted.
  CSV columns are read by value, not by physical position or literal header.
- Numeric punctuation, common hyphen variants, case and section order are normalized, so
  `24,128` and `24128` are the same figure.
- Identifier-shaped tokens such as `r-03` or `pv-10` are stripped before numeric anchors
  are checked and are never read as quantities.
- Locators may be descriptive: `section`, `table`, `note`, `exhibit`, `schedule`,
  `heading`, `paragraph`, `page`, and reserve-specific pointers such as
  `standardized measure` or `proved undeveloped` all satisfy the locator requirement. The
  supplied filename itself is required because the brief requires it.
- Markdown sections are read whole, never at fixed line numbers.

### Related matters in a row

Fully supported related matters may share a row without an automatic dispersion penalty.
The diagnostic `semantic_dispersion` is 1. Each matter still needs its own facts, conclusion,
action and source evidence in its winning row; unrelated scattered tokens do not combine.
R-02 accepts a property-level event or movement ledger/register/schedule as an equivalent
reconciliation action when the product/correction scope is actually stated.

### Support scaling

The fact and evidence sub-items are the record-keeping layer. A row can transcribe every
anchor figure, cite `annual_report.html` with a locator, and assert nothing at all, and
still collect them — under `P01` that is 0.35 of the matter with no conclusion reached.
Correct figures and a real citation make a finding checkable, not correct.
Support credit is therefore scaled only by the judgement credit in the same
dimension. A weak conclusion in one matter cannot reduce support credit in an
unrelated matter. `P11` directly measures end-to-end closure and is not
scaled by another dimension.

## Deductions

Each independent damage root contributes one additive amount. Repeated
manifestations of the same root are deduplicated. There is no cap or floor.

| Item | Error | Damage instances | Amount | Rationale |
| --- | --- | --- | ---: | --- |
| D01 | A supplied source document is missing or altered | once | 1.00 | The review no longer addresses the issued record |
| D02 | The deliverables assert their own market valuation | one root per artifact | 0.10 | The brief forbids creating a valuation |
| D03 | A conclusion depends on outside information | one root per artifact | 0.15 | Conclusions must remain source-bound |
| D04 | Substantive non-English analysis (proper names, titles, locators and quotations exempt) | once per affected deliverable | 0.05 | Required language usability |
| D05 | Retired ordinary-omission penalty | never | — | Missing coverage loses positive shares only |
| D06 | One of the two declared deliverables is absent | one root per missing file | 1.00 | Both files are required |
| D07 | The review forces a reconciliation between incompatible reserve/value bases | one root per artifact | 0.15 | The source says the reconciliation is not practicable |

| D08 | Memo omits one or more required substantive units | once for the missing-unit root | 0.12 | Independent memo closure requirement |

A negation within 30 characters before a `D02`, `D03` or `D07` match ("we do not create a market
valuation") turns it into a disclaimer and it is not charged.

Interactions with the dimensions:

- `D01` is decided by hashing the six supplied source files and is independent of the
  answer wording, so it cannot be earned back through the dimensions.
- `D01` also applies to the lenient lens as a 0/1 multiplier.
- There is no automatic failure for formatting. A missing deliverable scores as zero or
  partial credit through the dimensions; `tests/test.sh` writes every reward file before
  the validator runs, so a failed submission stays in the sample as a scored zero rather
  than a dropped run.

## Lenient Lens

The lenient score is binary:

```text
lenient = 1 iff unscaled P03, P08, P09 and P11 are complete,
                source integrity and both deliverables pass,
                memo units are complete,
                and no damage root fires
          0 otherwise
```

This usability lens does not cap or otherwise change strict.

## Anti-gaming controls

- The facts, conclusion and evidence for a dimension must co-occur in one substantive
  register row.
- A memo-only keyword list earns no dimension credit; the dimensions are scored on the
  register.
- Evidence requires a supplied filename plus a section, table or paragraph-style locator,
  and the row must cite figures or several documents — the word "evidence" alone is not a
  citation.
- A readiness conclusion asserting that the package needs no correction forfeits the
  readiness component of `P11`.

## Semantic language review and reproduction

D04 is reviewed against the instruction and language policy in `tests/language_source.json`.
It applies once per affected deliverable, not per line; proper names, source titles, filenames,
locators and genuine source quotations are exempt. Configure the endpoint, model and key
through environment variables; required service errors exit 2 rather than yielding a score.
Historical rollout summaries are not presented as rescored current artifacts.

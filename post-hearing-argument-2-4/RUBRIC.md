# Scoring Rubric — Post-Hearing Construction Payment Argument

The deliverable is scored by the evaluator in `tests/`, including the required source-bound semantic review described below. The judge reads the submitted content and original evidence, without access to the trajectory or the identity of the model that produced the answer. Required semantic-service or verdict-validation failures are infrastructure errors and publish no score.
Deliverable: `workspace/output/post_hearing_argument.docx`.

## Score Form

```text
final           = positive_earned * retention
positive_earned = sum over the positive items of weight * completion   (weights sum to 1)
retention       = product over distinct damage instances of that instance's coefficient
```

Completion is a value in [0, 1] per item: the item's value has to be stated, in this deliverable's own words, inside the scope the item names; an item built from several checks takes the share of them that hold. Weights and coefficients are read from `tests/pjroot/rubric-contract.json`; this document states the same numbers.
Manifestations that share one damage instance are charged once, at the smallest coefficient among them, so one mistake written three times costs what one mistake costs.

## Scoring Dimensions

| Dimension | Weight | Items |
| --- | ---: | --- |
| Valuation scope and basis | 0.25 | P01-P06 |
| Payment attribution and authority | 0.50 | P07-P11 |
| Requested disposition | 0.25 | P12-P13 |

### Content (1)

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P01 | Identify the 4,468,031 appraisal as a limited certain-value figure and dispute its completeness, not a final court debt. | hearing_1.txt:p4-7; hearing_2.txt:p4-8 | 0.06 |
| P02 | Relate excluded management and measures costs to necessary organization or site work rather than merely listing fee names. | hearing_1.txt:p4,6; hearing_2.txt:p5-7 | 0.05 |
| P03 | Distinguish the absence of a written pricing agreement from the appraisal's partial formula and explain why an exclusion still needs a contractual or valuation basis. | hearing_1.txt:p4-7; hearing_2.txt:p4-7 | 0.03 |
| P04 | Treat profit and management-cost questions as dependent on actual work and legal analogy, rather than denying them solely because of personal qualification. | hearing_1.txt:p4-7; case_law_report.txt:case-table | 0.03 |
| P05 | Relate regulatory fees or taxes to the appraisal scope and the actual burden; do not equate a cited precedent with a finding in this case. | hearing_2.txt:p5-7; case_law_report.txt:case-table | 0.04 |
| P06 | Keep party market comparators and the proposed 7,507,771 total distinct from appraisal-certified value and final judicial assessment. | hearing_1.txt:p4-7; hearing_2.txt:p4-8 | 0.04 |
| P07 | Analyze both disputed worker-payment sums, 211,160 and 1,063,645, separately and test whether either can be attributed to plaintiff through authorization or ratification. | hearing_2.txt:p8-11; witness_hearing.txt:p2-5 | 0.18 |
| P08 | Bind witness recruitment, payor, and the limits of the witness's knowledge to the disputed plaintiff-party relationship. | witness_hearing.txt:p2-5; hearing_2.txt:p9-11 | 0.09 |
| P09 | Distinguish a site lead's alleged attendance or settlement signature from proved authority to bind or ratify plaintiff's payment account. | hearing_2.txt:p8-11; witness_hearing.txt:p3-5 | 0.09 |
| P10 | Reconcile 4,885,400 and 4,890,500, preserve the 5,100 difference, account separately for the 150,000 transfer, and prevent the helper payments from being counted as confirmed direct payment without proof. | hearing_1.txt:p2-4; hearing_2.txt:p8-10 | 0.09 |
| P11 | Connect the defendants' claimed rush-work rationale to the separate question of who contracted for and must bear the extra worker cost. | hearing_2.txt:p9-11; witness_hearing.txt:p2-5 | 0.05 |
| P12 | Request a complete court valuation that recognizes proved work and separately examines disputed components without promoting either party's figure to an adjudicated sum. | hearing_1.txt:p4-7; hearing_2.txt:p4-8 | 0.08 |
| P13 | Tie the pleaded principal and interest to verification of the valuation composition, reconciled direct payments and supported due date through a concrete conditional or supplemental-review route. | hearing_1.txt:p2-7; hearing_2.txt:p2-8; witness_hearing.txt:p2-5 | 0.17 |

The weights follow the decision structure of this record. Half of the positive score measures payment attribution and authority because the two disputed worker payments both drive the asserted overpayment counterclaim and require separate transaction, authority and duplication analysis. Valuation scope receives one quarter because it determines the other side of the same account but contains several related subissues. The final quarter measures whether those findings are carried into a usable disposition: a court filing must preserve concrete relief while avoiding a precise principal or interest conclusion that the supplied extracts cannot yet reproduce.

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | Affirm that 4,468,031 is the court's final total or admitted debt, without distinguishing appraisal scope. | one harm per wrong appraisal_as_final business relationship regardless of repeated mentions | 0.7 |
| D02 | — | Affirm that the appraisal itself certified the party-proposed approximate 7.5 million or that the court already adopted it. | one harm per wrong claimed_market_as_certified business relationship regardless of repeated mentions | 0.8 |
| D03 | — | Affirm the contested worker payments were paid to plaintiff or admitted deductible without authorization or ratification evidence. | one harm per wrong worker_payment_attribution business relationship regardless of repeated mentions | 0.7 |
| D04 | — | Affirm that the site lead's alleged signature alone proves authority or plaintiff's ratification. | one harm per wrong signature_conclusive_agency business relationship regardless of repeated mentions | 0.7 |
| D05 | — | Affirm that the witness personally verified contracts or agency between other parties beyond first-hand knowledge. | one harm per wrong witness_overreach business relationship regardless of repeated mentions | 0.7 |
| D06 | — | Affirm a fabricated or reconciled payment total as an undisputed court finding while suppressing the stated 5,100 discrepancy. | one harm per wrong payment_account_invention business relationship regardless of repeated mentions | 0.7 |
| D07 | — | Present the court as having already adjudicated the disputed counterclaim, refund or interest in this still-pending first-instance matter. | one harm per wrong unsupported_new_relief business relationship regardless of repeated mentions | 0.7 |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Delivery Gate

Applied by `tests/deliverable_gate.py` before the score is settled, on the files directly under the
delivery directory declared by the task: `output/` for a live workspace, or the equivalent
`artifacts/output/` or flattened `artifacts/` directory in an archived run. Files elsewhere in the
workspace, such as scripts used to generate the document, are working files and are outside the delivery.

- **Missing deliverable.** `post_hearing_argument.docx` must be present under that exact name; if any is missing the score is 0.
- **Extra files.** Every other file in that resolved delivery directory that is neither required nor allow-listed (`manifest.json`; hidden files and caches are always allowed) is one damage instance of `DX_DELIVERABLE` at coefficient 0.4, at most 2 instances.
- **Source overlap diagnostic.** The scorer records long verbatim overlap with supplied materials but does not infer harm from a character threshold. Quotation is allowed. Independent positive owners still require an adopted analysis or requested disposition, so source text pasted without analysis earns no corresponding credit.
- **Chinese filing language.** The delivered argument must use Chinese as its operative language. If Han characters are less than half of the Han-plus-Latin script-bearing characters, the single delivered file creates one `DX_LANGUAGE` instance at coefficient 0.1 and lenient fails. A wrong-language court filing is not operationally usable, while the nonzero coefficient preserves any independently correct source analysis for strict partial credit.

## Lenient Lens

`reward_lenient` is a 0/1 gate: 1 when `positive_earned > 0.50` and at most 2 distinct damage instances. It answers whether a usable deliverable was produced at all and is reported beside the score; `reward_strict` is the score.

## Worksheet repair: paragraph scope and semantic propositions

There is no hidden 42/80-character minimum or 1100/2600-character maximum for credit.
Any contracted soft length warning remains a warning. P02/P07-P13 require source-grounded
adopted substantive reasoning, judged across the coherent argument without fixed wording or
same-paragraph limits. Required semantic evidence binds exact submitted text spans and original
material hashes; quoted opponents, keyword lists and genuinely opposite claims are excluded.
Configure the judge by environment. Service/parse/evidence failures exit 2 and publish no score.

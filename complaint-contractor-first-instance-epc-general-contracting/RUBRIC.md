# Scoring Rubric — complaint-contractor-first-instance-epc-general-contracting

The deliverable is scored condition-blind by two Oracles in `tests/`: a local program judge settles closed facts, amounts and structure; a required source-bound semantic judge settles the open legal propositions and professional-error wording. The semantic request is content-addressed and may be replayed from an exact cache; a live/cache failure is `UNMEASURED`, never a score. Neither Oracle sees the trajectory or producer identity.
Semantic adjudication requires OpenAI Responses and a GPT judge. Only the packaged exact Golden key is replayable; another request without live service is `UNMEASURED`.
Deliverable: `artifacts/civil-complaint.md`.

## Score Form

```text
final           = positive_earned * retention
positive_earned = sum over the positive items of weight * completion   (weights sum to 1)
retention       = product over distinct damage instances of that instance's coefficient
```

Completion is a value in [0, 1] per item: the item's value has to be stated, in this deliverable's own words, inside the scope the item names; an item built from several checks takes the share of them that hold. Weights and coefficients are read from `task/tests/pjroot/rubric-contract.json`; this document states the same numbers.
Manifestations that share one damage instance are charged once, at the smallest coefficient among them, so one mistake written three times costs what one mistake costs.

No Golden-relative hard length threshold is scored. Concision or omission loses only the corresponding positive credit; copying and non-Chinese padding remain separate evidence-based damages.

## Scoring Dimensions

| Dimension | Weight | Items |
| --- | ---: | --- |
| Content | 1 | P02, P10, P12, P13, P19, P21 |

### Content (1)

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P02 | a request item asks that the 《建设项目工程总承包合同》 between B公司 and A公司 be terminated as of service of the complaint copy | request items of the 诉讼请求 section | 0.24 |
| P10 | loss items state 二期初步设计费 1,680,000 and 二期临时设施费 2,583,218.16 | loss enumerations in facts paragraphs where B公司 compensates, or damages request items against B公司 | 0.3 |
| P12 | a loss item states the bid service fee share 8,487.5 | loss enumerations in facts paragraphs where B公司 compensates, or damages request items against B公司 | 0.1 |
| P13 | one paragraph or R11 facts block asserts B公司 is a one-person company (or wholly owned by C公司) and C公司 bears joint liability for its debts | facts paragraphs of the 事实和理由 section | 0.16 |
| P19 | termination (if any) first; B公司's principal money before the capital occupation fee; both before C公司's joint liability; costs the last, separate item; money, fee, joint liability and costs present | 诉讼请求 section | 0.1 |
| P21 | Relevant current statutes sit beside the propositions they support; equivalent applicable authorities and several citations in one sentence are accepted. Legal correctness is assessed separately. | 事实和理由 section | 0.1 |

### Owner, Weight, Dependency, and Completion Rationale

| Item | Owner | Professional importance and relative weight | Dependency and completion calculation |
| --- | --- | --- | --- |
| P02 (.24) | required source-bound semantic judge | Judicial termination and its service-based effective point are prerequisites to the unperformed-phase loss theory, justifying nearly one quarter. | Full requires an operative judicial termination request and service point; mentioning a notice only as a damages fact is zero. |
| P10 (.30) | local structured judge | The two largest evidence-backed phase-II loss heads dominate the supported quantified claim, so together they carry the largest item. | Full requires design 1,680,000 and temporary-facilities 2,583,218.16 bound to their correct heads; one correct head earns half; omission loses credit and an adopted different amount may also trigger D03. |
| P12 (.10) | local structured judge | Three evidence-backed loss heads are closed quantities; quantum matters but does not replace remedy/causation. | Full only when 1,680,000, 2,583,218.16 and 8,487.50 bind to correct heads; omission loses credit, another adopted amount may trigger D03. |
| P13 (.16) | required source-bound semantic judge | C's liability is a distinct defendant/root and affects collectability, but remains accessory to B's primary liability. | Full requires one-person/sole-shareholder premise, burden condition and joint-liability conclusion; unambiguous pronouns are valid; half for a supported incomplete chain. |
| P19 (.10) | local structured judge | Operative ordering makes relief executable but is filing form rather than merits. | Full requires termination, B money/occupation relief, C liability, then costs; equivalent occupation-loss labels count. |
| P21 (.10) | required source-bound semantic judge | Current provisions must be applied beside propositions; this rewards professional legal sufficiency rather than citation volume. | Full for at least two current applicable provisions tied to propositions; half for one; detached lists or wrong/repealed law are zero and may trigger D05. |

Positive completion is additive because remedy, quantified loss, shareholder liability, request form and legal basis are separately reviewable and weights sum to 1. Strict multiplies earned content by one coefficient per distinct adopted damage root. Ordinary omission only loses the corresponding positive; a deduction requires an affirmative harmful proposition or filing defect. Equivalent legal wording is semantic; closed amounts, dates, parties and order remain local. No total-score cap, retention floor, Golden-relative length threshold, or damage-count threshold is used.

Damage coefficients express filing consequence: D01 (.3) is catastrophic wrong-party relief; D04/D15 (.5) are major identity/priority defects; D03 (.6) changes evidenced quantum; D02 (.7) invents expected-profit quantum; D05/D06/D10/D11/D13/D14 (.8) are material law, termination, fabrication, filing-note, copying or language defects; D07/D12 (.9) are narrower removable rate/procedural defects. D08 and G01 are inactive under the current source-derived policy. Repeated manifestations of one root merge; independent roots multiply. Lenient is the explicit remedy-and-merits hard gate below, not a strict-score threshold.

The numeric values are coarse legal-severity bands. They express filing consequence and remaining usable work rather than a precise measurement of harm.

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | D公司 or E公司 is named as a defendant, or a request item orders D公司/E公司 to pay or bear liability | wrong_defendant_non_party | 0.3 |
| D02 | — | a concrete expected-profit (预期利润/可得利益) amount is asserted although the materials provide no profit rate or cost basis; a gap-marked value does not trigger | fabricated_expected_profit_amount | 0.7 |
| D03 | — | a design-fee, temporary-facilities or bid-service-fee loss item carries an amount other than 1,680,000 / 2,583,218.16 / 8,487.5 | loss_item_amount_<slot> (design, temp and fee are independent damages) | 0.6 |
| D04 | — | the party block states street numbers, 18-character credit codes, phone numbers or representative names not in the materials; identifiers demonstrably present in the independent material copy are excluded | fabricated_party_identifiers | 0.5 |
| D05 | — | the facts section relies on the repealed Contract Law or Company Law art. 63 | repealed_law_basis | 0.8 |
| D06 | — | the complaint concedes that B公司 had a termination right or that the contract was terminated on 2024-07-08 / by the notice | conceded_valid_termination | 0.8 |
| D07 | — | a request item uses an LPR multiple above 1, an annual rate above 3.65%, a daily penalty rate or liquidated damages | unsupported_rate_or_penalty | 0.9 |
| D08 | — | inactive: no source-derived hard length threshold | none; never triggers | inactive |
| D10 | — | an adopted sentence asserts that the preliminary design passed the employer's review, that a payment condition is fulfilled, that B公司 confirmed an amount, reminders, failed negotiation or phase-II acceptance | fabricated_procedure | 0.8 |
| D11 | — | an internal drafting note in the filing: 输入材料, 本案材料未载明, 不在起诉状中/臆造, 证据目录中曾…, 本诉按…重新计算, (说明:…) | drafting_note_in_filing | 0.8 |
| D12 | — | a 管辖 subsection or sentence arguing jurisdiction, an application for appraisal/audit/court investigation, or an evidence-submission plan | unrequested_procedural_content | 0.9 |
| D13 | — | source-bound semantic finding that the facts substantially reproduce material/evidence-list wording instead of concise original pleading; names, dates, amounts and short titles alone do not trigger | verbatim_material_copy | 0.8 |
| D14 | — | a request or facts sentence of at least 40 Latin letters that make up more than half of its characters (prose not written in Chinese) | non_chinese_filing | 0.8 |
| D15 | — | an adopted 诉讼请求 asks for 优先受偿 over the phase-II loss heads | unsupported_priority_claim | 0.5 |
| G01 | — | inactive: ordinary omission affects positive completion only | none; never triggers | inactive |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Lenient Lens

`reward_lenient` is a 0/1 filing-usability gate. It requires a complete judicial-termination request (P02) and source-supported breach/loss chain (P10), with no wrong party, invented quantum/identity, repealed or materially wrong law, wrong termination consequence, fabricated fact, drafting note, procedural application, non-Chinese filing, or unsupported priority request. It has no statistical score threshold or damage-count ceiling.

Retention is the uncapped product of distinct source-grounded damage coefficients; there is no fixed score cap or floor.

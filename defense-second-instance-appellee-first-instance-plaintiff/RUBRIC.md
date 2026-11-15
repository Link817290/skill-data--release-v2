# Scoring Rubric — defense-second-instance-appellee-first-instance-plaintiff

The deliverable is scored condition-blind by a local closed-fact Oracle and a required source-bound semantic Oracle. A live/cache failure is `UNMEASURED`, never a score.
Semantic adjudication requires OpenAI Responses and a GPT judge. Only the packaged exact Golden key is replayable; another request without live service is `UNMEASURED`.
Deliverable: `artifacts/appeal-defence-statement.md`.

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
| Content | 1 | P02, P07, P10, P11, P12, P13, P14, P15, P16, P17 |

### Content (1)

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P02 | substantive caisson variation and repricing rebuttal | materials and contract clauses | 0.08 |
| P07 | actual-construction-period information-price rebuttal | appeal and judgment dates | 0.07 |
| P10 | review-delay/payment-delay obligations are distinct; audit referral does not excuse payment | clause 14.2 and appeal | 0.18 |
| P11 | exact 2021-08-19 due-date basis and 2021-08-20 penalty start | judgment | 0.12 |
| P12 | no counterclaim/not litigated, so delay damages cannot be offset in this appeal | judgment and appeal | 0.15 |
| P13 | current-law or contract reasoning for unclear payment time and filing-date reference; no named article is mandatory | current law and contract | 0.08 |
| P14 | clause 12.1 does not bar caisson repricing | contract and appeal | 0.07 |
| P15 | substantive high-pressure jet-grouting pile omitted-item repricing rebuttal | appeal, judgment, contact sheets and contract | 0.12 |
| P16 | substantive bored-pile geology/machinery-change repricing rebuttal | opposing appeal, judgment and contract | 0.10 |
| P17 | second-instance costs position | appeal posture and skill | 0.03 |

### Owner and calculation rationale

P02/P07/P10/P12/P13/P14/P15/P16/P17 are source-bound semantic owners because complete rebuttals admit equivalent legal and technical wording; keywords alone earn zero. P11 combines semantic due-date reasoning with local exact-date validation. P10 receives the largest weight because payment-default liability is a major appeal ground; P12 follows because it disposes of the delay-damages offset; P11/P15/P16 carry material but narrower independent grounds; P02/P07/P13/P14 are supporting price/legal propositions; P17 is ancillary costs relief. The weights sum to 1.

Each owner requires object, adopted proposition, and record/contract/legal ground. Full credit requires the complete stated limbs; half credit is available only where the item's definition identifies a severable correct limb. Omission loses positive credit only. An adopted false party, amount, date, law, fact, or adverse request creates damage because it affirmatively harms the filing. Distinct damage roots multiply once each; repeated wording of one root merges. There is no score cap, retention floor, hidden length threshold, or damage-count threshold.

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | the answer adopts an appellant price ground: 沉井 is a measure item / must not be re-priced / is not a variation; bored-pile change is the contractor's own cause; 水泥土/灌注桩 must be settled at bid rates; cement must not be adjusted; the appraisal lacks basis; or adopts that no late-payment penalty is owed or delay damages must be offset | concede_price:<object>, concede_penalty, or concede_delay_damages; one independent object per harm | 0.3 |
| D04 | — | the party block names B公司 as 答辩人/被上诉人 or A公司 as 上诉人/被答辩人 | party_roles_inverted | 0.3 |
| D05 | — | the appellee's own sentence or closing request asks to revoke the judgment, remand, or support the appellant's appeal (requests limited to adding the cement adjustment are excluded) | adverse_request | 0.3 |
| D06 | — | wrong caisson/cement amount, derived judgment total one digit wrong, or wrong late-payment penalty start date | wrong_amount:<caisson\|cement>, wrong_derived_total:<total>, or wrong_penalty_start | 0.9 |
| D08 | — | the text contains a second-instance case number with digits (民终123号), or party lines contain digit addresses, 18-character credit codes, phone numbers or a non-anonymised representative name | fabricated_identifiers | 0.9 |
| D09 | — | a sentence relies on the repealed 2004 construction interpretation (title without （一）), interpretation （二）, 法释〔2004〕14号 or 法释〔2018〕20号 | repealed_interpretation_basis | 0.9 |
| D10 | — | inactive: no task-authorized character/row limit; content omissions are scored by positive coverage. | never | inactive |
| D12 | — | an adopted answer-body sentence asserts, as the appellee's own affirmative case, a procedural act or omission whose act key is outside the frozen supported-act set (R11): a retrial-appraisal or appraiser-examination application, participation in the appraisal, the site-signature/construction-record/supervision-file basis of the appraisal, and the issuing of a delay warning or delay claim by the appellant; the same item and coefficient also cover two out-of-evidence assertions: the delay attributed to the appellant as settled fact (delay_cause_certainty: 工期延误/工程逾期… (完全\|全部\|均)?(系\|是\|由\|因) B公司/上诉人/被答辩人/发包人 … 所致/造成/导致/原因), against the judgment's 工程逾期的原因较为复杂…并不明确, and a letter, confirmation or undertaking said to be issued by the appellant (written_confirmation: 出具/发出/签署/签发/发送/致函/作出/递交/提交 + 书面函件/书面确认/确认函/确认书/承诺函/回函/复函/函件), which neither material records (函件 0, 确认函 0, 确认书 0, 承诺函 0, 书面确认 0, 回函 0, 复函 0); negated, hypothetical/conditional (即使/如果/若/如/是否…) and opponent-reported forms do not trigger | unsupported_addition:<act_key> (appraisal_procedure, delay_claim, delay_cause_certainty, written_confirmation) - one key per rebuttal line, because the invented appraisal-procedure facts damage the appraisal-admissibility rebuttal and the invented delay-claim facts damage the delay-responsibility rebuttal used under two different appeal grounds | 0.3 |
| D13 | — | the artifact adopts both that the appellee filed the appeal and that the appellee did not file it (R12) | internal_contradiction:appellant_identity | 0.9 |
| D14 | — | inactive: a conventional request to dismiss the appeal and uphold the judgment is proper for a non-appealing appellee | never | inactive |
| D17 | — | missing recognizable defence title, A-company appellee/respondent party line, or prayer to dismiss B's appeal | missing_structure, one root | 0.3 |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

Damage coefficients reflect consequence. D01/D04/D05/D12/D17 use .3 because they reverse a party position, seek adverse relief, invent a material act, or omit filing structure and substantially impair usability. D06/D08/D09/D13 use .9 because a wrong controlling amount/date, fabricated identity, repealed authority, or internal contradiction is narrower and readily severable, though still professionally wrong. D10 and D14 are inactive. Each causal root is charged once. Missing an argument is not a damage because the corresponding positive owner already records that omission; an affirmative wrong proposition is damage because the court could adopt it against A.

For the semantic part of D12, a fact or exhibit expressly recited in either supplied judgment or the opposing appeal is record-supported for purposes of answering that appeal, even when disputed. D12 instead targets a new act, date, document or event absent from both supplied case documents. P16 may therefore answer the appeal conditionally on its stated geology/machinery premise; it does not require a separate signed change document that the supplied record does not contain.

### Public coarse-grained scoring policy

The weights and coefficients above are coarse professional-severity bands and should be read by relative tier:

- `.18/.15` owners carry the main payment-liability and dispositive procedural answers;
- `.12/.10` owners carry independent material price/date grounds;
- `.08/.07` owners carry narrower supporting classifications or legal links;
- `.03` carries ancillary second-instance costs.

Multiplicative retention answers a different question from positive coverage: after measuring how much useful answer remains, it discounts that value for each independent adopted error that can be used against A or make the filing unusable. A `.3` coefficient leaves 30% of the otherwise earned value because wrong-side relief, a material invented act, or missing filing structure damages the response globally. A `.9` coefficient leaves 90% because the defect is material but normally severable, such as one wrong date, identifier, authority, or internal contradiction. Inactive D10/D14 never alter retention.

Dependencies do not create duplicate charges. P11 and P13 may rely on the same unclear-payment-time facts but own different completion questions; omission can lose each relevant limb, while one adopted wrong start date is one D06 root. P02/P14 share the caisson setting but own variation/repricing and the clause-12.1 answer respectively. Repeated manifestations with one causal root merge; independent roots multiply. Missing content loses its declared positive weight only. Wrong content additionally receives a damage coefficient because it leaves a harmful proposition in the filing.


## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Lenient Lens

`reward_lenient` requires full P02/P10/P12/P15/P16 and no critical party, adverse-request, amount/date, identity, law, fabrication, contradiction, or structure damage. It is not derived from a strict threshold or damage count.


## Additional Adjudication Rules

D17接受材料中的逾期竣工违约金及同义表述。S01/S02字数只作诊断，D10不再按隐藏参考答案长短扣分；缺少实质内容仍按原有正向项失分。

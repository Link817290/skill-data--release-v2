# Scoring Rubric — defense-first-instance-defendant-complaint-and-evidence

The deliverable is scored by a program judge in `tests/`: no model, no network, no access to the trajectory or to which model produced the answer. The same file always scores the same.
Deliverable: `artifacts/statement-of-defense.md`.

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
| Content | 1 | P01, P03, P04, P05, P07, P09 |

### Content (1)

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P01 | the defence opposes claim 1 (contract price 1,482,040) in full rather than conceding any phase-1 portion Read as: requires reading the complaint's claim structure and adopting a full-denial position although the evidence shows partial C公司 confirmation of phase 1 | materials/起诉材料-修订版.docx 诉讼请求 1; golden p[4] | 0.05 |
| P03 | clause 7.1 obliges the plaintiff to hand the owner's confirmation letter to the defendant Read as: requires linking clause 7.1's delivery duty to the payment mechanism rather than to delivery of the videos | materials/证据材料-修订版.docx 合同 7.1; golden p[6] | 0.05 |
| P04 | the plaintiff neither delivered C公司's written confirmation letter nor proved C公司 confirmed the phase-2 video Read as: requires auditing eleven evidence items: the only 二期 confirmations are of the storyboard (evidence 9) and models (evidence 10), the chat summary shows the plaintiff still urging acceptance on 2022-08-25/29, and evidence 2 is signed by 甲方 not C公司 | materials/证据材料-修订版.docx 证据目录 2, 9, 10, 11 and the 3月25日 纪要; golden p[6] | 0.39 |
| P05 | C公司 and the plaintiff agreed to evaluate and settle phases 1 and 2 jointly, so phase 1 cannot be paid on its own Read as: requires finding the 3月23日 meeting minutes embedded in the 2022-03-25 email (evidence 8) and the chat summary 一、二期统一确认盖章 (evidence 11) and turning them against the plaintiff | materials/证据材料-修订版.docx 证据 8 email body (会谈纪要 item 1), 证据目录 11 item 2; golden p[6] | 0.15 |
| P07 | the overdue-payment penalty claim fails because payment was never due Read as: propagates the unsatisfied payment condition to claim 2 instead of only disputing the rate | materials/起诉材料-修订版.docx 诉讼请求 2; golden p[8] | 0.11 |
| P09 | the clause 9.4 penalty applies only to late payment caused by the defendant; here non-payment is not attributable to it Read as: requires reading the penalty clause's causation condition and applying the owner-confirmation mechanism to fault | materials/证据材料-修订版.docx 合同 9.4; golden p[10] | 0.25 |

## Owner Design

| Owner | What and professional importance | Relative weight, dependency and calculation | Missing versus affirmative error |
| --- | --- | --- | --- |
| P01 | Response to the 1,482,040 principal claim; identifies the main dispute. | .05 because claim identity is necessary but compact; semantic full/half/zero, dependent on an adopted claim response. | Silence loses credit; stating another principal is D04. |
| P03 | Clause 7.1 confirmation-letter delivery duty. | .05 because it is one contractual link; semantic equivalence, dependent on applying the clause to payment. | Omission loses credit; reversing the duty is D12. |
| P04 | Absence of the written confirmation letter and proof of phase-2 final confirmation. | .39, largest because it is the central evidentiary condition; full for both propositions, half for one. | Missing analysis loses credit; conceding phase-2 confirmation is D07. |
| P05 | Joint verification/settlement of phases 1 and 2. | .15 because it explains why partial phase-1 confirmation does not mature all price; semantic application required. | Omission loses credit; invented verification conduct is D12. |
| P07 | No overdue liability before payment is due. | .11 because it directly answers claim 2; equivalent overdue-payment liability wording is accepted. | Omission loses credit; conceding default is D01. |
| P09 | Clause 9.4 attribution/fault condition. | .25 because it is an independent contractual defense; full for non-attribution, half for the condition alone. | Omission loses credit; reversed causation is D01/D12. |

Positive weights sum to 1. The required source-bound semantic judge evaluates adopted meaning and exact cited spans; no keyword fallback is allowed.

Weights use a public coarse professional-severity policy: minor framing owners are about `.05`, supporting legal links `.10-.15`, major independent defenses `.25`, and the dispositive evidence condition about `.40`. The relative bands reflect litigation importance and dependency; they are not precise measurements of harm. Dependencies prevent the same proposition from being credited twice.

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | the defence states the payment condition is satisfied, that the defendant agrees/ought to pay, or that it is in default | liability_conceded | 0.4 |
| D02 | — | the party block names A公司 as 答辩人 or the body asks the court to uphold the plaintiff's claims | wrong_side | 0.4 |
| D03 | — | relies on 《合同法》 as a legal basis | repealed_law_basis | 0.4 |
| D04 | — | the defence answers a principal claim of 2,814,000, 1,848,182.76, 366,142.76 or another amount the complaint does not make | claim_amount_misidentified | 0.4 |
| D05 | — | denies that a contract relationship exists or asserts the purchase contract is invalid/not formed | contract_relationship_denied | 0.4 |
| D06 | — | fills unsupported identifiers with invented values: concrete case numbers like (2026)…号, addresses with house numbers, 9-18 character codes, phone numbers or personal names for representatives/agents | fabricated_identifiers | 0.4 |
| D07 | — | concedes that C公司 confirmed the phase-2 video or that the plaintiff delivered C公司's confirmation letter | owner_confirmation_conceded | 0.4 |
| D08 | — | inactive: no task-authorized character/row limit; content omissions are scored by positive coverage. | never | inactive |
| D09 | — | an adopted clause of the argument body binds a numeric interest-rate figure to an interest-rate object (LPR / 贷款市场报价利率 / 年利率 / 年化 / 月利率 / 日利率 / 折合年利率) as the defence's own fact (R19) | unsupported_rate_figure; one key, because every invented figure in the sentence feeds the same single business damage - the penalty-reduction argument's quantitative basis | 0.4 |
| D10 | — | the answer asks the tribunal for an affirmative remedy against the plaintiff that the defendant has not claimed in the proceedings - a set-off of a penalty the plaintiff is said to owe, a deduction of such a penalty from the sum claimed, or a counterclaim brought here | relief_not_claimed | 0.1 |
| D11 | — | a core unit is missing: B公司 as answering party, the principal response, the overdue-payment-liability response, or the dismissal request; closing formulae are not damage instances | form_unit_<unit> | 0.2 |
| D12 | — | source-bound semantic review finds no substantive reasoning or a materially unsupported adopted assertion | unsupported_material_position | 0.4 |

Deduction owners separate omission from harmful assertion. D01/D02/D03/D04/D05/D06/D07/D09/D12 retain 40% because each materially corrupts the adopted defense; D10 retains 10% because an unauthorized counterclaim changes the proceeding's scope; D11 retains 20% per missing core unit because the filing cannot answer both claims without those units. Ordinary missing analysis stays on the positive side. Formal closing words, court line and signature formatting are professional drafting matters but do not multiply the whole score.

Retention bands describe remaining professional value after an independent root error: `.4` leaves substantial unaffected analysis, `.2` leaves only limited usability after a missing core unit, and `.1` is near-fatal scope expansion. Repeated manifestations sharing a causal root merge. These are coarse professional-severity bands rather than precise measurements of harm.

| Owner | Professional harm / dependency / calculation | Missing treatment |
| --- | --- | --- |
| D01 | Concedes maturity/default; .4 retention, one liability root, dependent on an adopted concession. | Silence loses P01/P07/P09 only. |
| D02 | Writes for the wrong side or supports plaintiff; .4, one wrong-side root. | Missing party voice is D11, not D02. |
| D03 | Uses repealed Contract Law as current basis; .4, one legal-basis root. | No citation is not an error. |
| D04 | Answers a principal other than 1,482,040; .4, one claim-object root. | Omitted amount loses P01. |
| D05 | Denies the admitted contract relationship; .4, one relationship root. | Not restating formation is harmless. |
| D06 | Invents masked identifiers; .4, one fabrication root. | Gaps and marked unknowns are valid. |
| D07 | Concedes phase-2 final confirmation/letter delivery; .4, one owner-confirmation root. | Failure to analyze loses P04. |
| D08 | Inactive; no coefficient or active calculation. | Omission remains positive-side only. |
| D09 | Invents a numeric rate; .4, one quantitative-basis root. | Naming the rate standard without a number is valid. |
| D10 | Seeks set-off/counterclaim not before the court; .1 retention because it changes proceeding scope, one relief root. | Reserving a separate claim is valid. |
| D11 | Missing party/principal/penalty/dismissal core unit; .2 per independently missing core unit. | Closing words, court line and signature form do not trigger. |
| D12 | Source-bound judge finds a material unsupported adopted position; .4, one document root, suppressed when the same error is already D01/D02/D04/D07. | Mere sparse analysis loses positive credit. |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Lenient Lens

`reward_lenient` is a legal-usability gate, not a threshold over continuous score. It requires observable substantive coverage of each source-bound unit P01, P03, P04, P05, P07 and P09: the principal claim; the confirmation-letter duty; the actual confirmation-evidence gap; the joint phase-settlement issue and the limited status of missing underlying pages; the link from payment maturity to overdue liability; and clause 9.4 attribution. It also requires a source-supported adopted strategy and no D01, D02, D04, D07, D11 or D12. Equivalent wording and valid partial formulations count as observable coverage; omission of an entire required link does not. Other depth and drafting quality remain in strict.


## Additional Adjudication Rules

六项实质答辩按原始起诉与证据材料做必需的语义评审，接纳不予认可、先交函后接收、付款条件未成就与举证归责边界等表达。参考答辩策略是非排他示例，任何结论均须原始材料支持。宽松分要求六项均有实质覆盖，不使用严格总分阈值；只写P04/P05不得满分。撤销无公开依据的参考字数惩罚；保留金额、身份与真实材料矛盾检查。
语义评审只接受 OpenAI Responses 协议与 GPT 模型，通过环境变量配置（`LLM_JUDGE_BASE_URL`、`LLM_JUDGE_API_KEY`、可选 `LLM_JUDGE_MODEL`）；默认模型 gpt-5.6-sol，base URL 规范拼接到 `/v1/responses`。响应必须完整、分数有效并引用实际提交片段；服务、协议或模型族不符时返回 UNMEASURED 基础设施错误，禁止关键词静默回退。请求记录绑定模型、规则、完整材料与提交哈希；`tests/golden_replay/` 仅含不变 Golden 的精确请求绑定回放，不含普通候选、运行/provider历史或凭据，且不进入 actor workspace。任意新候选未命中时仍须外部 fresh 服务。

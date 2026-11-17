# Scoring Rubric — enforcement-application-creditor-effective-second-instance-judgment

The deliverable is scored by a program judge in `tests/`: no model, no network, no access to the trajectory or to which model produced the answer. The same file always scores the same.
Deliverable: `artifacts/执行申请书.docx`.

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
| Content | 1 | P03, P07, P09, P10, P13, P14, P15 |

### Content (1)

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P03 | Correctly names the sole respondent with its registration number and address \| 本项的字面值在 materials 中已存在，命中只证明作者把判决主文的名称/金额/公式正确搬入，属摘抄而非推理（正分只奖励推理，不奖励摘抄）；其错误侧由 D02（使用未分摊或判前数字）覆盖。本项保留以维持文书事实骨架的可见度。 Read as: The complete proposition must be adopted by the author inside one bounded span | relation-matrix.md U002; golden/执行申请书.docx | 0.25 |
| P07 | Replays the public civil-procedure counting rule from the given service date and carries one baseline through the whole document \| sections 含 __head__：skill 的 enforcement-title-and-reach.md §4 教把整条时间链写进开场段，而 Golden 写在请求列表之后，两种写法同等计分。本项计的是「链」而不是 Golden 的那两个具体日期：relation-matrix U004 把生效起算点记为 equivalent_set，skill 也明确不替包选口径、只要求择一写明并全篇一致；三条链任一条两端齐全给满分，只齐一端给 0.5，两端分属不同链给 0（skill 自己点名的失败模式）。日期与谓词按邻接绑定且中间不得跨过另一个日期，「11月3日与届满同句」这种巧合不算命中。届满谓词含同义表述「为（履行）期间/期限的最后一日」，并加段落级顺延守卫——段内出现 顺延/延至/延长至 时，位置在该线索之前的届满命中一律丢弃：「至2024年11月3日届满；因该日为休息日，顺延至2024年11月4日为履行期间的最后一日」并全篇按 11/5 起算，是一条完整的链 B，不是跨链混用。守卫按段落而不是按句：中文法律文书用分号并列这两个半句，而 sentences() 在分号处断开。accrual 谓词的第一支「迟延履行/加倍 … 起算日」允许中间隔最多 160 字，仍不得跨过另一个日期——把基数的四个加数写在括号里（约 110 字）之后才写「自2024年11月4日起」，正是 application §3 要求的对账写法，链 A 仍认到两端。expiry 谓词的「届满」带 (?!之?次日\|的次日\|后) 否定，accrual 的日期带「后面不是届满」的守卫并有「起，发生/开始/承担 迟延履行/加倍」分支：「2024年11月4日（履行期间届满之次日）」读作起算日，不读作届满日。 Read as: The complete proposition must be adopted by the author inside one bounded span | relation-matrix.md U004; instruction.md service date + civil-procedure ten-day counting rule | 0.4 |
| P09 | Carries forward the two-period, two-base interest formula the judgments set out for overdue construction payment, without collapsing it into one period or one base \| 本项的字面值在 materials 中已存在，命中只证明作者把判决主文的名称/金额/公式正确搬入，属摘抄而非推理（正分只奖励推理，不奖励摘抄）；其错误侧由 D02（使用未分摊或判前数字）覆盖。本项保留以维持文书事实骨架的可见度，但不承担实质权重。 Read as: The complete proposition must be adopted by the author inside one bounded span | relation-matrix.md U006; materials/1 p.26 (判决理由); materials/1 p.28 (主文一) | 0.05 |
| P10 | Correctly carries forward the deposit-return amount \| 本项的字面值在 materials 中已存在，命中只证明作者把判决主文的名称/金额/公式正确搬入，属摘抄而非推理（正分只奖励推理，不奖励摘抄）；其错误侧由 D02（使用未分摊或判前数字）覆盖。本项保留以维持文书事实骨架的可见度，但不承担实质权重。 Read as: The complete proposition must be adopted by the author inside one bounded span | relation-matrix.md U007; materials/1 p.28 (主文二) | 0.05 |
| P13 | The delay-interest basis is not a fourth free-standing figure; it must be replayed as the sum of exactly the three already-awarded principal amounts (construction payment + deposit + apportioned fees), and combined with the standard statutory daily rate \| context_pattern 够得到民诉法 264 条自己的措辞「加倍支付迟延履行期间的债务利息」（中间隔 11 字）；中间跨度用 [^。] 而非 [^。；]。partial=0.5：enforcement-application.md §3 把本项定义为三件事同时成立（可对账的基数、届满次日起算、按标准称引利率），三分之二成立与三分之一成立不同判 0。basis_pattern 认「基数为判决确定的除一般债务利息之外的金钱债务8101635.72元」这种「基数为」后面不紧接数字的写法，partial 在「基数完全没写」时也可达。basis 另有对账回退支——从句里出现「基数」且句中有与三项本金之和（8462529.72）在 0.5 元容差内相等的数额时，以该数额为已陈述基数；答卷把四个加数逐项列出来（application §3「Write the base out so it can be reconciled with the items it is built from」要求的形态）不会让紧邻正则够不到。rate 认对法释〔2014〕8 号/「加倍部分债务利息标准」的称引——application §3 明写「do not state the rate as a figure you cannot place; name the standard instead」。只引民诉法第二百六十四条不算：264 条本身不确定利率。 Read as: The complete proposition must be adopted by the author inside one bounded span | relation-matrix.md U011; materials/1 p.29 (民诉法264条加倍利息); replay of the three awarded principal amounts (the sum P10 checks) | 0.05 |
| P14 | '驳回上诉，维持原判' after '驳回原告的其他诉讼请求' finally confirms that only B公司 owes anything; C公司 and D公司's dismissed claims cannot be revived by naming them as respondents in an enforcement filing \| 本项是本包的核心推理项：被申请人只能一家这个结论在 materials 中**没有任何一处写出**，它是从两句判项（一审第三项与二审主文）推出的执行依据主体侧射程判断，不是摘抄。其错误侧由 D01（把已被驳回的当事人重新列为被申请人/第三人）覆盖，与 D02（判前/未分摊金额）无关。 Read as: The complete proposition must be adopted by the author inside one bounded span | relation-matrix.md U013; materials/1 p.28-29 (驳回原告的其他诉讼请求); materials/2 p.18 (驳回上诉，维持原判) | 0.15 |
| P15 | Golden 的 U006-暂计金额/U008-暂计金额/U012 三个单元的金额本身 not_scored，理由是依赖历史 LPR。但依赖 LPR 的只是金额本身；「把运行中的利息项标为暂计、并指名一个真实日期作为暂计截止日、全篇同一天」这一部分是 unsupported-specifics-and-placeholders.md §1 意义上的 Class A（申请人自己选定的日期，记录里本来就不会有），也是 enforcement-application.md §3「Keep a running item's ends visible」与§9 第 6 条「every cut-off date in the document is the same day」的核心要求。在三个运行项与对账段写同一天的文书得分；把暂计截止日本身标成【待补：暂计截止日】的文书给不出任何可核的暂计口径——这正是「该推却标」的失分点。本项还要求该日与文书自己落款的日期是同一天：只要求「恰好一个真实的暂计截止日」会让全篇对象与数值整体换错的文书也满足本项；而同一天的要求是本文种自己的口径——Golden 的注就写「一般债务利息暂计算至执行申请日2024年11月4日」，落款日期也正是二〇二四年十一月四日，enforcement-application.md §3 与 §9 第 6 条把暂计截止日定义为申请提出之日并要求全篇同一天。顺带它也量住了把文书自己的日期标成【待补：申请日期】这一处 Class A 失分。 | relation-matrix.md U006-暂计金额 / U008-暂计金额 / U012; golden 第7、9、14行 | 0.05 |

## Owner Design

| Owner | What and professional importance | Relative weight, dependency and calculation | Missing versus affirmative error |
| --- | --- | --- | --- |
| P03 | Sole respondent identity with source-known portions and marked redactions. | .25 because enforceability begins with an actionable party; deterministic proposition, placeholders accepted for redacted fields. | Omission loses credit; adding dismissed parties is D01 and inventing specifics is D04/D14. |
| P07 | One internally consistent performance-expiry and delay-accrual chain. | .40, largest because every interest request depends on the operative date chain; full for both ends, half for one. | Missing endpoint loses credit; mixed/wrong basis-period is D03. |
| P09 | Two-period, two-base ordinary-interest formula. | .05 because the judgment supplies the formula directly; exact/equivalent replay. | Omission loses credit; pre-judgment figures are D02. |
| P10 | 40,000 deposit return. | .05 because it is a fixed smaller principal; deterministic replay. | Omission loses credit; wrong adjudicated amount is D02. |
| P13 | Delay-interest base equals construction payment + deposit + apportioned fees and names the statutory rate. | .05 strict plus a lenient hard requirement because the base determines execution scope; full for reconciled base/rate, half for start+rate without correct base. | Omission loses credit and blocks lenient; a short base is D03. |
| P14 | Only B公司 remains within the effective title. | .15 because party reach requires combining both judgments; a required source-bound semantic judge decides that legal reach and equivalent reasoning, while deterministic party scanning only extracts evidence and supports D01. | Omission loses credit; naming dismissed parties is D01. |
| P15 | Running amounts are expressly provisional with one selected date, or use clear placeholders where the filing/cut-off date remains open. | .05 because it controls reproducibility without rewarding unsupported rate results. | Omission loses credit; a fixed unsupported provisional amount is D04/D14. |

Positive weights sum to 1. Identity, date, formula and scope owners are deterministic; the required source-bound semantic judge is limited to unsupported adopted facts that cross those structured checks.

Weights follow public coarse severity bands: fixed supporting items `.05`, party reach `.15`, actionable identity `.25`, and the controlling date chain `.40`. The bands reflect professional dependency and remaining document value rather than a precise measurement of harm.

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | Names an already-dismissed party as a respondent or third party | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.6 |
| D02 | — | Reuses a pre-adjudication or un-apportioned figure instead of the court-awarded amount | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.6 |
| D03 | — | Mismatches the two-period interest basis with the wrong date boundary | item plus erroneous object; the basis/period mismatch and the short delay-interest base are separate objects | 0.3 |
| D04 | — | Unsupported specific fact | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.4 |
| D05 | — | Wrong court addressed | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.6 |
| D06 | — | Shape outside the unit's declared band | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.1 |
| D07 | — | Wrong statutory daily rate for delay interest | item plus erroneous object (fact value for unsupported specifics, shape unit and side for shape) | 0.6 |
| D08 | — | An unredacted, complete field expressly fixed by the source is delivered as a gap marker; redacted identities and an unfixed application date are excluded | one instance for the whole item: treating fields the record fixes as open is a single classification mistake and a single business damage (the filing is not actionable and is sent back). Each field is a manifestation of it, not an independent damage -- 04a only splits instances where the same cause produces two separately describable business damages, and 'the code is open' and 'the address is open' are the same filing being unusable once | 0.9 |
| D09 | — | An independent monetary enforcement claim states neither a sum nor a base, a period and a rate standard; conventional allocation of execution costs is excluded | item plus the class of field or item affected; a missing operative item is keyed by the item it lacks (missing:<id>), at most two | 0.7 |
| D10 | — | The operative part of the title is told twice, once as narrative and once as the list | item plus the class of field or item affected | 0.9 |
| D11 | — | A Civil Procedure Law provision is cited under a wrong (superseded) article number | item plus the topic (delay interest / application period / jurisdiction) whose provision is mis-numbered | 0.6 |
| D12 | — | Drafting notes, handler instructions or a to-do checklist carried inside the filing | one instance for the whole item: a memo to the handler is one classification mistake however many paragraphs it runs to | 0.7 |
| D13 | — | A party carries its designation from the concluded action (in brackets or instead of) its enforcement designation | one instance for the whole caption: labelling the parties by the concluded action is one decision | 0.5 |
| D14 | — | Source-bound semantic review finds an unsupported officer title, fixed historical-rate result or free-standing cost-interest claim | one document-level source-support instance | 0.4 |

Deduction coefficients are retention values. D01/D02/D05/D07/D11 at .6 address wrong parties, title figures, court or controlling legal rules; D03 at .3 addresses a core date/base mismatch; D04/D14 at .4 address unsupported adopted facts; D08/D10 at .9 are locally curable classification/repetition defects; D09/D12 at .7 address unactionable items or filing notes; D06 at .1 is reserved for material shape failure; D13 at .5 addresses caption-role confusion. Ordinary omission stays on the positive side.

The retention bands mean: `.9` mostly usable after a local curable defect; `.7-.6` materially impaired but still actionable in unaffected parts; `.5-.4` major source/scope confusion; `.3` core arithmetic/date mismatch; `.1` near-total shape failure. Repeated manifestations with one causal root merge. The numbers are coarse professional-severity bands rather than precise measurements of harm.

| Owner | Professional harm / dependency / calculation | Missing treatment |
| --- | --- | --- |
| D01 | Revives a dismissed party; .6, one instance per wrong party. | Missing respondent loses P03/P14. |
| D02 | Uses a pre-award/unapportioned figure; .6 per erroneous award object. | Missing award loses its P owner. |
| D03 | Wrong period/base or short delay base; .3 per independent mismatch because execution arithmetic is core. | No formula loses P07/P13 and blocks lenient. |
| D04 | Unsupported date/amount/identifier, including fixed provisional LPR result; .4 per unsupported fact. | Marked Class-B gaps are valid. |
| D05 | Addresses the wrong court; .6, one forum root. | Missing court is structural omission, not a false forum. |
| D06 | Material shape-band violation; .1 per declared shape object. | Ordinary concise drafting is uncharged. |
| D07 | Wrong statutory daily rate; .6, one rate root. | Naming the standard without an invented number is valid. |
| D08 | Leaves source-complete field open; .9, one classification root. | Redacted identities and applicant-selected dates may be placeholders. |
| D09 | Unactionable independent item; .7 by missing item/class, cap 2; execution-cost allocation boilerplate excluded. | Omitted optional extension is harmless. |
| D10 | Repeats operative title as narrative; .9, one repetition root. | Concise omission is preferred. |
| D11 | Misnumbers governing Civil Procedure Law provision; .6 per legal topic. | No decorative citation is required. |
| D12 | Carries drafting notes/checklist into filing; .7, one document root. | Clean silence is correct. |
| D13 | Carries concluded-action designations into enforcement caption; .5, one caption root. | Missing designation loses P03, not D13. |
| D14 | Source-bound judge finds unsupported title/rate result/cost-interest claim; .4, one document root. | Placeholders and omitted unsupported extensions are valid. |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Delivery Gate

Applied by `tests/deliverable_gate.py` before the score is settled, on the files directly under `artifacts/`:

- **Missing deliverable.** `执行申请书.docx` must be present under that exact name; if any is missing the score is 0.
- **Extra files.** Every other file there that is neither required nor allow-listed (`manifest.json`; hidden files and caches are always allowed) is one damage instance of `DX_DELIVERABLE` at coefficient 0.4, at most 2 instances.
- **Source pasted in.** A run of at least 500 normalized characters copied verbatim from a materials document into a required deliverable is one damage instance of `DX_SOURCE_DUMP` at coefficient 0.4, at most 2 instances; quoting the source is not charged.

## Lenient Lens

`reward_lenient` is a legal-usability gate. It requires P03, P07, P09, P10, P13 and P14 to be present and none of D01, D02, D03, D04, D05, D07, D08, D09, D11, D12, D13 or D14 to trigger. P15 affects strict quality but an expressly marked open filing date does not make the application unusable.


## Additional Adjudication Rules

D08只针对源材料明确给出未脱敏完整值而被写成缺失的字段；本案没有此类身份字段，源材料已打码或申请人自选日期可待核/留白。D09排除“本案执行费用由被执行人负担”等非独立债权费用套语；保留真正独立债权与判决费用请求的可计算性检查。

The source-bound semantic judge is required for D14. Its request binds the criteria, both judgments and the complete candidate. `tests/golden_replay/` contains only the unchanged Golden's exact request-bound response, with no ordinary candidate, run/provider history or credential, and is outside the actor workspace. An unseen candidate misses that record; without a valid external fresh response it is UNMEASURED and exits as infrastructure failure, never a business zero or Golden reuse.

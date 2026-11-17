# Scoring Rubric — retrial-application-first-instance-defendant-two-instance-judgments-and-submissions

The deterministic checks in `tests/` are supplemented by targeted semantic adjudication for the listed propositions. That adjudication requires the configured semantic service (`SEMANTIC_JUDGE_BASE_URL` and `OPENAI_API_KEY`); a service/schema/evidence failure is an infrastructure error and publishes no score. The same file and adjudication inputs always produce the same result when the service response is replayed.
Deliverable: `artifacts/retrial-application.md`.

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
| Content | 1 | P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P15, P16, P17 |

### Content (1)

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P01 | maps the two error clusters to the current CPL retrial grounds: fact finding lacking evidence (art. 211 item 2) and wrong application of law (art. 211 item 6) Read as: no material cites CPL art. 211; the drafter must know the 2023 numbering and choose items (2) and (6) for the errors actually argued | materials/4.二审判决书.pdf p73 (二审 依民诉法第一百七十七条维持); materials/1.一审判决书.pdf p63 (民诉法第二百六十四条 shows the 2023 numbering); golden/retrial-application.md body p[4], p[12], p[20], p[31], p[34] | 0.05 |
| P02 | the adverse part of the first-instance judgment is only item 1; item 2 dismissed A公司's other claims in B公司's favour, so revocation must target the second-instance judgment and first-instance item 1 Read as: requires reading both judgments' dispositive parts and limiting the revocation to the part that harms the client | materials/1.一审判决书.pdf p63-p64 判决主文 一、二; materials/4.二审判决书.pdf p73 驳回上诉维持原判; golden/retrial-application.md body p[6] | 0.07 |
| P03 | the concrete relief is a reduction of the payable price by the 未见实物 difference 21,404,977 Read as: requires carrying the calculated difference (P06) into the request rather than a generic 改判驳回 | materials/4.二审判决书.pdf p25-p30 (甲路 selective items), p34-p35 and p57-p58 (乙路 拦水埂); golden/retrial-application.md body p[7] | 0.05 |
| P04 | the 3,544,566.47 appraisal fee should not stay with B公司 once the audit-fault premise falls Read as: requires linking the fee burden (二审 p71) to the audit ground and asking for it in the request | materials/1.一审判决书.pdf p63 鉴定费3544566.47元由B公司负担; materials/4.二审判决书.pdf p71; golden/retrial-application.md body p[8] | 0.05 |
| P05 | identifies the objective evidence: the appraiser's on-site inspection recorded 未见实物 for 甲路 selective items 2-14 and 乙路 拦水埂, producing selective opinion 2 Read as: requires locating, among 28 甲路 determinate items, 14 甲路 selective items and 5 乙路 selective items, exactly the ones whose selective opinion turns on 未见实物 | materials/4.二审判决书.pdf p26-p30 (甲路 selective items 2-14 '现场勘验时部分未见实物'), p34-p35 and p45 (乙路 拦水埂 '二次现场勘验，均未见'); materials/2.被告关于一审判决事实错误的书面意见.docx p[70]-p[80]; golden/retrial-application.md body p[13]-p[14] | 0.05 |
| P06 | computes the reduction: 甲路 selective items 2-14 opinion 1 minus opinion 2 = 18,829,063.61 ≈ 18,829,064; plus 乙路 拦水埂 2,575,913 = 21,404,977 Read as: thirteen item-level subtractions across p26-p30 plus the 乙路 figure; no material states either result | materials/4.二审判决书.pdf p25-p30 (items 2-14 opinion 1 / opinion 2 amounts), p34-p35, p57-p58; golden/retrial-application.md body p[19] | 0.05 |
| P07 | shows materiality: 21,404,977 is about 17% of the adjudged principal 125,806,738.02 Read as: division against the adjudged principal to argue the error affects the outcome | materials/4.二审判决书.pdf p59, p62, p71 (尚欠125806738.02元); golden/retrial-application.md body p[19] | 0.05 |
| P08 | the court's '各方面情况可能发生改变 / 可能被破坏' reasoning is speculation substituting for evidence; nothing proves the works once existed Read as: requires attacking the exact inference in 二审/一审 p51-p52 as presumption replacing proof | materials/4.二审判决书.pdf p51-p52 (可能发生改变, 质保期内的维护整改), p65, p68-p69; materials/3.被告律师代理意见.docx p[61]; golden/retrial-application.md body p[15]-p[17] | 0.05 |
| P09 | warranty-period repair presupposes built but defective works; it cannot cover works that do not exist Read as: requires separating the court's 质保期维护整改 rationale from the non-existence fact | materials/4.二审判决书.pdf p51-p52; materials/3.被告律师代理意见.docx p[61]; golden/retrial-application.md body p[17] | 0.05 |
| P10 | 乙路 audit was completed: 审计报告 核定 328,446,294.68 (审减 33,575,679.36), so the second-instance finding 无审计结论 contradicts the record Read as: requires joining the audit facts (p17-p18) with the second-instance reasoning (p66-p67) and naming the contradiction | materials/4.二审判决书.pdf p17-p18, p66-p67; materials/3.被告律师代理意见.docx p[20]-p[28]; golden/retrial-application.md body p[23]-p[24] | 0.05 |
| P11 | the engineer's 土建 registration does not by any cited rule invalidate the whole audit report; the county audit is an independent act Read as: requires testing the court's invalidity inference (p66-p67) against the absence of a specific legal provision | materials/4.二审判决书.pdf p17-p18, p49, p66-p67; materials/3.被告律师代理意见.docx p[14]-p[15]; golden/retrial-application.md body p[25]-p[26] | 0.16 |
| P12 | the 发包人不正当阻止条件成就 rule needs employer fault; 甲路 audit materials were supplemented by A公司 only in July 2024, so the fault lies with A公司 Read as: requires joining the court's rule (p48, p67-p68) with the finding that A公司 supplemented 甲路 materials in 2024-07 (p18, p67) | materials/4.二审判决书.pdf p18, p48, p67-p68; materials/2.被告关于一审判决事实错误的书面意见.docx p[39]-p[49]; materials/3.被告律师代理意见.docx p[29]-p[34]; golden/retrial-application.md body p[27]-p[28] | 0.05 |
| P13 | the fee burden rests on the court's premise that B公司 failed to settle; if that premise falls, the fee burden must be corrected too Read as: requires carrying the audit ground downstream to the 鉴定费 order (二审 p71) | materials/4.二审判决书.pdf p71; materials/3.被告律师代理意见.docx p[36]; golden/retrial-application.md body p[29]-p[30] | 0.05 |
| P14 | the contract's 《某市建设工程造价信息》 is closer in name to the construction commission's 《某市工程造价信息》 than to the transport periodical chosen by the court Read as: requires textual interpretation of the price-adjustment clause against the two real periodicals (二审 p38-p40, p69-p70) | materials/4.二审判决书.pdf p10, p38, p40, p52-p53, p69-p70; materials/2.被告关于一审判决事实错误的书面意见.docx p[85]-p[87]; materials/3.被告律师代理意见.docx p[63]-p[64]; golden/retrial-application.md body p[32] | 0.05 |
| P15 | quantifies the interpretive choice: 交委 adds 5,236,264 (甲路) and 5,572,253 (乙路) while 建委 gives negative adjustments (甲路 -2,122,630, 乙路 -466,942), a gap over ten million Read as: requires pulling the paired figures from the supplementary appraisal (p38-p41) and contrasting them | materials/4.二审判决书.pdf p38-p41, p53, p56; materials/3.被告律师代理意见.docx p[65]; golden/retrial-application.md body p[32] | 0.05 |
| P16 | the adjusted materials (水泥、河沙、石子、钢筋、混凝土) are general building materials, so the road-project character says little about which periodical applies Read as: requires reading the clause's material list (p10) against the court's 公路工程 rationale (p53, p70) | materials/4.二审判决书.pdf p10, p53, p69-p70; golden/retrial-application.md body p[32] | 0.05 |
| P17 | a retrial application against a High Court's effective judgment between two companies goes to the court one level up, the Supreme People's Court Read as: the materials never name the receiving court; the drafter must apply the one-level-up rule | materials/4.二审判决书.pdf p1, p73-p74 (某高级人民法院 终审); golden/retrial-application.md body p[35]-p[36] | 0.07 |

P11 carries 0.16 because it tests the central legal bridge between a professional
registration label, the validity of the whole audit report, and the independent
county-audit act. That bridge directly controls whether the agreed settlement
route can be displaced; it is broader than a single fact lookup. P03 and P06 do
not duplicate credit: P06 measures the source-derived arithmetic and object
binding in the reasons, while P03 measures whether that result is converted into
operative relief in the request.

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | the application is signed or captioned for A公司 (再审申请人 A/C公司, 被申请人 B公司) or the request adopts 维持原判 / 驳回B公司再审申请 | posture_reversed | 0.2 |
| D02 | — | the 此致 addressee is a court other than the Supreme People's Court (e.g. 某高级人民法院, 某中级人民法院) | wrong_receiving_court | 0.9 |
| D03 | — | a retrial ground cites a superseded CPL article number (第二百条, 第二百零七条, 第一百九十八条) or the appeal article 第一百七十九条 as the retrial basis | superseded_retrial_article | 0.4 |
| D04 | — | the 未见实物 reduction is stated as 19,196,655 or 21,772,568 (report totals including 甲路 事项1 挖除树根, already decided for B公司), or the 乙路 拦水埂 reduction uses 5,510,870 / 6,239,007 / 5,456,461 | wrong_unseen_reduction_amount | 0.7 |
| D05 | — | the application attributes the 甲路 audit delay or non-completion to B公司 / the employer (e.g. 申请人未及时送审导致审计未完成) | audit_delay_conceded | 0.9 |
| D06 | — | the application endorses the 交委 periodical (《某市交通工程材料价格信息》) as the correct adjustment basis | periodical_choice_conceded | 0.9 |
| D07 | — | an identifier the materials mask or omit is invented: an 18-character unified social credit code, digits in a case number where the materials show XXX, or a street number where they show **** | fabricated_identifier | 0.7 |
| D08 | — | the request or grounds region is plainly a stub or bloated beyond its declared professional band; each section is measured independently, but both observations share one document-level structure damage | document_shape_balance | 0.9 |
| D09 | — | the party block names C公司 (B公司's wholly owning shareholder and co-defendant) as 被申请人 | co_defendant_as_respondent | 0.3 |
| D10 | — | an adjudged amount is misquoted: 鉴定费 other than 3,544,566.47 or the adjudged principal other than 125,806,738.02 | misquoted_fee \| misquoted_principal | 0.7 |
| D11 | — | the application concedes the 未见实物 works were built and later damaged, or that they fall within warranty-period repair | unseen_existence_conceded | 0.5 |
| D12 | — | a standalone conclusion repeats completed grounds, or an attachment/material/pre-submission checklist is appended in the closing or signature block | out_of_boundary_tail | 0.9 |
| D13 | — | the application asserts as its own finding that the adjudged sums are already discharged in full, that the parties' claims are extinguished, or that the case no longer carries a dispute | controversy_declared_over | 0.3 |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Delivery Gate

Applied by `tests/deliverable_gate.py` before the score is settled, on the files directly under `artifacts/`:

- **Missing deliverable.** `retrial-application.md` must be present under that exact name; if any is missing the score is 0.
- **Extra files.** Every other file there that is neither required nor allow-listed (`manifest.json`; hidden files and caches are always allowed) is one damage instance of `DX_DELIVERABLE` at coefficient 0.4, at most 2 instances.
- **Source pasted in.** A run of at least 500 normalized characters copied verbatim from a materials document into a required deliverable is one damage instance of `DX_SOURCE_DUMP` at coefficient 0.4, at most 2 instances; quoting the source is not charged.

## Lenient Lens

`reward_lenient` is a 0/1 filing-usability gate. It requires all of the following:

- `positive_earned > 0.50`;
- the correct applicant posture and at least partial targeted revocation relief;
- the Supreme People's Court as receiving court;
- operative monetary or appraisal-fee relief and at least one applicable statutory ground;
- at least one closed substantive reasoning chain among unseen works, audit responsibility, or pricing-publication interpretation;
- no critical posture, court, amount, fabricated-identifier, filing-boundary, or mootness damage.

This gate tests necessary correctness and professional usability. It is separate
from the continuous strict score.

## Worksheet repair: source-bound semantic equivalence

P04, P13, P14 and P15 use one required, request-bound `gpt-5.6-sol`
source adjudication. Its request includes the current instruction, source excerpts
and hashes, current rubric criteria, Golden reference, and exact candidate spans.
It accepts equivalent professional wording and paragraph bridges while preserving
actor, object, polarity, attribution and operative scope. P13-P15 use continuous
quarter-step partial credit for completed components; P04 remains binary because an
operative fee request either reallocates/exempts B or it does not. Service, schema,
request-binding or evidence failures exit without publishing a score. Process
scoring is outside this result score.

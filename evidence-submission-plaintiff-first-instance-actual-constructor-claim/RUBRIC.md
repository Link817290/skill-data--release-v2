# Scoring Rubric — evidence-submission-plaintiff-first-instance-actual-constructor-claim

The deliverable is scored by deterministic checks plus a required source-bound semantic judge for P01–P16. The judge reads the original dossier and the adopted meaning of the deliverable; it has no access to trajectory or model identity. Candidate evidence is required for nonzero credit. Cached verdicts are bound to model, criteria, source and candidate; unavailable semantic adjudication cannot yield a passing score.
Deliverable: `artifacts/evidence-submission-opinion.md`.

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
| Substantive proof and relief | 0.90 | P01-P16 |
| Filing structure | 0.10 | P17-P20 |

The 0.90/0.10 division reflects the professional purpose of an evidence-submission opinion: the proof propositions and executable relief determine whether it can support adjudication, while filing structure makes that analysis usable by the court. Within the substantive share, actual-constructor status and payment arithmetic receive 0.10 each because an error in either defeats the principal claim. Contract characterization, valuation, primary relief and the employer's bounded liability receive 0.08 each because they determine the legal route and recoverable scope. Supporting offset, limitation, corroboration, burden and wage propositions receive 0.02-0.06 according to their effect on that route. The four independent filing controls divide the 0.10 structure share equally; none substitutes for substantive correctness.

### Positive items

| Item | What is evaluated | Evidence | Weight |
| --- | --- | --- | ---: |
| P01 | group 3 (G17-G38 actual-construction records) locks A公司's actual-constructor status and is the core/foundation of the whole proof system Read as: requires ranking the evidence groups by probative role and binding the performance records to the actual-constructor element | materials/案件原始资料-某项目实际施工人纠纷.docx 八、第三组 table; 一、案件概要; 三、工程与项目概况; 六、实际施工过程详述; golden/举证意见.docx p[20], p[22], p[40] | 0.1 |
| P02 | the 项目内部承包责任书 is a nominal internal contract that is in substance a transfer (转包) and void, because no real employment relation exists (no labour contract, social insurance, wages, unsigned appointment letter). Read as: requires applying the internal-contracting test (real employment relation) to the evidence G10/G14 and deriving invalidity | materials/案件原始资料-某项目实际施工人纠纷.docx 四、法律性质分析; 争议焦点二; 第二组 G10, G14; golden/举证意见.docx p[16], p[18] | 0.08 |
| P03 | the actual-completed-quantity price 9,746.30万元 (not the 88% internal or nominal price) is the basis of the compensation for the void contract. Read as: requires choosing the compensation basis after invalidity (Civil Code 793) between competing price bases | materials/案件原始资料-某项目实际施工人纠纷.docx 十一、金额体系对照; 十、民法典第七百九十三条; 争议焦点三 (被告 88% defence); 第四组 G41, G43, G44, G45; golden/举证意见.docx p[26], p[49] | 0.08 |
| P04 | B公司 has paid 3,942.30万元 and still owes 5,804.00万元 (9,746.30 - 3,942.30). Read as: requires computing the balance from the valuation and the payment evidence and attributing the debt to B公司 not C公司 | materials/案件原始资料-某项目实际施工人纠纷.docx 十一、金额体系对照 rows 5-6; 第五组 G49, G54; golden/举证意见.docx p[30] | 0.1 |
| P05 | the 672.60万元 wage payment made for B公司's own workers must not be offset against A公司's claim. Read as: requires separating the disputed wage advance by worker population and deciding its offset effect | materials/案件原始资料-某项目实际施工人纠纷.docx 五、大事记 2022-01-25; 六、(四) 农民工工资阶段; 争议焦点六 (被告抗辩); 第五组 G55; golden/举证意见.docx p[28], p[30] | 0.06 |
| P06 | C公司 is liable to pay within the 2,412.00万元 it owes B公司. Read as: requires applying the employer's limited liability (Judicial Interpretation I art. 43) to the reconciled arrears | materials/案件原始资料-某项目实际施工人纠纷.docx 一、案件概要; 十、建工解释一第四十三条; 十一、金额体系对照; 第二组 G16; golden/举证意见.docx p[50] | 0.08 |
| P07 | the C-B property-offset agreement (以房抵债, G56) was not actually performed, so C公司's 2,412万元 arrears to B公司 still stand. Read as: requires evaluating the defendants' counter-document and its effect on the employer's liability | materials/案件原始资料-某项目实际施工人纠纷.docx 争议焦点五 (被告以房抵债抗辩); 第五组 G56; golden/举证意见.docx p[28], p[30] | 0.04 |
| P08 | the 214 migrant workers organised by A公司 are owed 613.80万元 in wages, confirmed by the labour-inspection investigation. Read as: requires linking the wage sheet to the inspection record (G57, G59, G60) into one confirmed fact | materials/案件原始资料-某项目实际施工人纠纷.docx 第六组 G57-G60; 大事记 2024-03-15; golden/举证意见.docx p[32], p[34] | 0.03 |
| P09 | A公司's written demands, letters and complaints interrupted limitation, so the claim is not time-barred Read as: requires applying limitation interruption to the demand/complaint evidence of group 7 | materials/案件原始资料-某项目实际施工人纠纷.docx 第七组 G63-G66; 大事记 2023-03-20, 2023-11-08, 2024-03-15; golden/举证意见.docx p[36], p[38] | 0.04 |
| P10 | the wage-payment flow and real-name records (G20/G21) corroborate the wage sheet and attendance records (G57/G58) on the personnel dimension Read as: requires connecting evidence across groups 3 and 6 that the materials list separately | materials/案件原始资料-某项目实际施工人纠纷.docx 第三组 G20, G21; 第六组 G57, G58; golden/举证意见.docx p[40] sentence 2 | 0.04 |
| P11 | the site instructions (G27-G64) corroborate the design change notices (G43) and variation settlement submission (G44) on the quantity dimension Read as: requires connecting evidence across groups 3 and 4 | materials/案件原始资料-某项目实际施工人纠纷.docx 第三组 G27-G64; 第四组 G43, G44; golden/举证意见.docx p[40] sentence 2 | 0.04 |
| P12 | the account statement (G16) and the unperformed property-offset agreement (G56) corroborate each other on the employer-liability dimension. Read as: requires connecting evidence across groups 2 and 5 for the employer's liability | materials/案件原始资料-某项目实际施工人纠纷.docx 第二组 G16; 第五组 G56; golden/举证意见.docx p[40] sentence 2 | 0.03 |
| P13 | the defendants' affirmative defences (valid internal contract, management fee, full wage offset, quality defects, property offset) carry their own burden of proof, which shifts to the defendants Read as: requires classifying each defence as an affirmative fact claim under Civil Procedure Interpretation art. 90/91 and allocating the burden | materials/案件原始资料-某项目实际施工人纠纷.docx 七、争议焦点一至七 被告抗辩; golden/举证意见.docx p[43] | 0.04 |
| P14 | the plaintiff's initial proof reaches the high-probability (高度盖然性) standard Read as: requires applying the civil standard of proof (Interpretation art. 108) to the assembled evidence | public convention (Civil Procedure Interpretation art. 108); no material source; golden/举证意见.docx p[42] | 0.04 |
| P15 | D公司 is a nominal contracting counterparty with no actual performance capacity; the B-D contract arrangement serves regulatory avoidance. This does not establish that D company was founded for that purpose. | materials/案件原始资料-某项目实际施工人纠纷.docx 四、第二层; 第一组 G4, G7; 第二组 G15; golden/举证意见.docx p[14] | 0.02 |
| P16 | customary 举证意见 closes with 请求事项 asking the court to admit the evidence and make the determinations it supports; primary debtor before the employer's limited liability (建工解释一第四十三条) Read as: format, section and order item scored in its own right: the delivered document must carry every element the item names, and keyword presence alone does not satisfy it | original dossier complaint and supported central relief; equivalent merged/split prayers accepted | 0.08 |
| P17 | 民事诉讼文书通行样式: 标题、致送法院、案号、当事人及诉讼地位 (民事诉讼法第一百二十二条/第一百二十四条 对当事人信息的要求) Read as: format, section and order item scored in its own right: the delivered document must carry every element the item names, and keyword presence alone does not satisfy it | golden/举证意见.docx p[0]-p[6]; materials 卷首, §二 | 0.025 |
| P18 | 证据规定第十九条、民诉法解释第九十条: 证据应分类编号并说明证明目的；通行举证意见按待证事实分组、每组写证明目的 Read as: format, section and order item scored in its own right: the delivered document must carry every element the item names, and keyword presence alone does not satisfy it | golden/举证意见.docx p[11]-p[38] | 0.025 |
| P19 | 通行举证意见结构: 总述、分组证据与证明目的、证据之间的关联、举证责任说明、请求 Read as: format, section and order item scored in its own right: the delivered document must carry every element the item names, and keyword presence alone does not satisfy it | golden/举证意见.docx p[7], p[10], p[39], p[41], p[44] | 0.025 |
| P20 | 诉讼文书落款: 署名当事人、代理人与日期 Read as: format, section and order item scored in its own right: the delivered document must carry every element the item names, and keyword presence alone does not satisfy it | golden/举证意见.docx p[53]-p[55]; materials §二 代理人沈某、郑某 | 0.025 |

## Deductions

| Item | Dimension | Error | Damage instances | Coefficient |
| --- | --- | --- | --- | ---: |
| D01 | — | an adopted clause takes 88%, 7,268.80万元, 8,260.00万元 or 4,860万元 as the basis of compensation or settlement (R05) | valuation_basis_conceded | 0.9 |
| D02 | — | an owed-amount assertion against B公司 carries an amount outside the replay set {5,804.00, 6,476.60} (R04) | owed_amount_misstated | 0.5 |
| D03 | — | an adopted sentence concedes the internal contract is valid/real, that there is no transfer, that A公司 is D公司's performance assistant or not the actual constructor, or that 徐某 is B公司's employee | contract_nature_conceded | 0.9 |
| D04 | — | an adopted sentence concedes that the 12% management fee (991.20万元) should be deducted or that the 1,286.40万元 wage advance is fully offset | b_deductions_conceded | 0.9 |
| D05 | — | an adopted sentence says the property offset was performed, C公司's arrears were discharged, or C公司 bears no liability | employer_released | 0.2 |
| D06 | — | an adopted clause asks C公司 to bear joint liability, the full 5,804.00/6,476.60/9,746.30万元 or all the debt, without the 范围内 limit | employer_liability_overreach | 0.6 |
| D07 | — | an adopted sentence states a judicial/court-commissioned appraisal confirmed the cost, or calls the unilateral cost report (G42/G45) a judicial appraisal | appraisal_fabricated | 0.5 |
| D08 | — | a signature/date line invents a concrete date outside the supplied record; an open date field and the dossier-supported filing date 2024-07-22 are accepted | submission_date_fabricated | 0.5 |
| D11 | — | the plaintiff states that its own core proof is not proven / below the proof standard / 待定 / its weakest point, that it does not ask the court to determine it, or that one of its exhibits cannot alone prove its stated purpose | adverse_disclosure | 0.3 |
| D12 | — | asserts a submission, carrier, seal or backdating the materials do not record | procedure_fabricated | 0.5 |
| D13 | — | turns a dossier qualifier (关联关系嫌疑, contested quality, unilateral notice) into an established fact about the defendants' state of mind or conduct | qualifier_overclaimed | 0.6 |
| D14 | — | adds unsupported procedural applications outside the requested evidentiary opinion, including appraisal, investigation, order to produce, witnesses, preservation or carrier verification; an adopted conditional procedural request is still checked | extra_or_conditional_requests | 0.6 |
| D15 | — | issues 真实性/合法性/关联性 verdicts in an evidence-submission opinion | three_property_boilerplate | 0.8 |
| D16 | — | addresses an internal strategy note to the court | internal_strategy_note | 0.9 |
| D17 | — | three or more prose sentences copied verbatim from the dossier (N06 masked, evidence rows and tables excluded) | bulk_material_copy | 0.7 |
| D18 | — | introduces a G-number outside the identifiers actually present in the dossier; the overview reaches G68 while the detailed third-group table includes overlapping original identifiers through G86, so G1-G86 are accepted | unauthorized_evidence_identifier | 0.6 |

Ordinary omission is not charged: an answer that says less than the source is scored by the positive side alone. A deduction charges damage - a statement the source does not support, a shape the brief did not ask for, or a deliverable that cannot be read.

Each coefficient expresses retained professional utility after one distinct adopted error. A coefficient of 0.9 covers a material but locally curable concession; 0.8-0.7 covers broader presentation or source-integrity harm; 0.6-0.5 covers an error that changes a liability, amount, evidence universe or procedural premise; 0.3-0.2 is reserved for a concession that directly undermines a central claim. Coefficients multiply only across independent causal roots. Repetitions of one error are charged once, so the formula measures separate legal harms rather than word frequency. These coefficients are part of the professional loss model, not score caps.

## Automatic Failure

- A deliverable that cannot be decoded scores 0, and no deduction is charged on top of it: an unreadable file is an absent observation, not a business error.

## Delivery Gate

Applied by `tests/deliverable_gate.py` before the score is settled, on the files directly under `artifacts/`:

- **Missing deliverable.** `evidence-submission-opinion.md` must be present under that exact name; if any is missing the score is 0.
- **Extra files.** Every other file there that is neither required nor allow-listed (`manifest.json`; hidden files and caches are always allowed) is one damage instance of `DX_DELIVERABLE` at coefficient 0.4, at most 2 instances.
- **Source pasted in.** A run of at least 700 normalized characters copied verbatim from a materials document into a required deliverable is one damage instance of `DX_SOURCE_DUMP` at coefficient 0.4, at most 2 instances; quoting the source is not charged.

## Lenient Lens

`reward_lenient` is a separate filing-readiness gate rather than a threshold over strict score. It requires at least half completion on the principal status, contract, valuation, arithmetic, bounded-employer-liability, limitation, relief, caption and signature items (P01, P02, P03, P04, P06, P09, P16, P17 and P20), no adopted professional damage D01-D08 or D11-D18, and a passing delivery gate. `reward_strict` remains the continuous quality score.

P01-P16 use source-bound semantic review for legal equivalence and professional meaning. Each nonzero decision must cite exact candidate and dossier spans, and the cited candidate span must independently carry the criterion's material dossier anchor. Closed amounts, evidence identifiers, party direction, filing structure and unsupported assertions remain deterministic. Exact Golden replay is an offline reproduction of that one content-bound request; a different submission requires fresh adjudication and cannot inherit the Golden result.

The source-anchor floor is limited to closed dossier identity, not legal wording. P01/P02/P07/P15 accept the supplied group, exhibit, instrument or party locator; P03-P06 accept their disclosed closed amounts; P08/P09 accept any listed worker, amount, exhibit or dated-event locator; P10-P12 require two supplied locators because those items expressly measure corroboration between independent evidence; P16 requires both closed quantum anchors for the primary and bounded-employer relief. P13 and P14 have no deterministic token floor because their burden and proof-standard conclusions are semantic legal judgments. The exact public anchor for every P01-P16 item is also recorded in `rubric-contract.json` as `deterministic_source_anchor`. These checks cannot award legal credit; they only prevent a semantic finding from floating free of the cited record.

# PPM Diagnosis Rubric

Version: `ppm-semantic-llm-v2.1-audited`.

All 26 source checks remain mandatory rubric coverage. Each source check is complete/correct (1) or not (0).
Sixteen active positive items carry normalized reward weights on the 0.01 grid. No item has zero weight.
Related arithmetic checks and period product-risk ratios are grouped; their original within-group relative weights are retained.
Every source check belongs to exactly one active item. The same parameters score all models and conditions.

## Active Positive Items

| ID | Capability | Weight | Source Checks |
| --- | --- | ---: | --- |
| P-A-EXCEPTION | diagnostic-reasoning | 0.05 | P-A-EXCEPTION |
| P-A-FEB-REPAIR | diagnostic-reasoning | 0.05 | P-A-FEB-REPAIR |
| P-B-RISK | diagnostic-reasoning | 0.05 | P-B-RISK |
| P-B-SWING | diagnostic-reasoning | 0.05 | P-B-SWING |
| P-CAUSAL-LIMIT | diagnostic-reasoning | 0.05 | P-CAUSAL-LIMIT |
| P-FOLLOWUP | diagnostic-reasoning | 0.05 | P-FOLLOWUP |
| P-FOLLOWUP-FIELDS | diagnostic-reasoning | 0.05 | P-FOLLOWUP-FIELDS |
| P-FULL-SCOPE | diagnostic-reasoning | 0.08 | P-FULL-SCOPE |
| P-METRIC-LIMIT | diagnostic-reasoning | 0.10 | P-METRIC-LIMIT |
| P-OVERALL-PEAKS | diagnostic-reasoning | 0.05 | P-OVERALL-PEAKS |
| P-PRIORITY | diagnostic-reasoning | 0.05 | P-PRIORITY |
| P-PRODUCT-PEAKS | diagnostic-reasoning | 0.05 | P-PRODUCT-PEAKS |
| P-SCOPE | diagnostic-reasoning | 0.05 | P-SCOPE |
| P-SEVERITY-LIMIT | diagnostic-reasoning | 0.17 | P-SEVERITY-LIMIT |
| P-rate-reconciliation | rate-reconciliation | 0.05 | P-MONTH-TABLE, P-PRODUCT-TABLE, P-AGGREGATE-RECONCILE, P-RECONCILE |
| P-derived-product-risk | derived-product-risk | 0.05 | P-SHARE-A, P-SHARE-B, P-SHARE-C, P-SHARE-D, P-RELATIVE-A, P-RELATIVE-B, P-RELATIVE-C, P-RELATIVE-D |

### Owner, source and severity ledger

| Active item | Strict owner / dependency | Source basis | Professional severity |
|---|---|---|---|
| P-A-EXCEPTION | semantic; singleton | source A counts/rates; Skill rate arithmetic | high: wrong period/generalization reverses the stated exception |
| P-A-FEB-REPAIR | semantic plus cell/formula evidence; singleton | February A numerator/denominator and stored rate | high: a known source inconsistency must be isolated, not propagated |
| P-B-RISK | semantic; singleton | B complaints, total complaints and product rate; decomposition Skill | high: combines burden and rate for management attention |
| P-B-SWING | semantic; singleton | B monthly count-derived rates; trend Skill | medium: required observed movement, not a causal claim |
| P-CAUSAL-LIMIT | semantic; singleton | absence of case/category/batch evidence; task and Skill boundary | critical: prevents unsupported root-cause attribution |
| P-FOLLOWUP | semantic; singleton | observed high-rate cases and B6 comparison; task request | medium: makes diagnosis actionable without claiming completion |
| P-FOLLOWUP-FIELDS | semantic; singleton | missing governance fields identified by source inventory and Skill | medium: defines evidence needed for corrective-action closure |
| P-FULL-SCOPE | semantic with numeric scope; singleton | source months 1–8, task period, PPM definition and aggregation Skill | critical: establishes population, denominator and missing-data limits |
| P-METRIC-LIMIT | semantic; singleton | CPPM filename/PPM sheet labels and absent defect-unit definition | critical: prevents relabeling complaints as confirmed defective units |
| P-OVERALL-PEAKS | semantic; singleton | recomputed monthly overall PPM | medium: observed period prioritization |
| P-PRIORITY | semantic; singleton | D period PPM and exposure; decomposition Skill | high: principal containment priority |
| P-PRODUCT-PEAKS | semantic; singleton | recomputed monthly product PPM | medium: localizes the highest observed rate periods |
| P-SCOPE | semantic; singleton | blank September–December operands and `#DIV/0!` cells | critical: unobserved periods cannot become zero performance or trend data |
| P-SEVERITY-LIMIT | semantic; singleton | source lacks severity/customer-impact evidence; task and Skill boundary | critical: rate and count rankings are not a severity model |
| P-rate-reconciliation | mixed program/semantic; four listed checks, weighted within group | source counts, formulas and same-period totals; arithmetic Skill | critical: core numerator/denominator truth and aggregate closure |
| P-derived-product-risk | program numeric; eight listed checks, weighted within group | same-period product/overall counts; decomposition Skill | high: product share and relative-rate conclusions depend on these ratios |

### Per-owner calculation and weight rationale

The weights allocate the diagnosis by professional consequence and independent
work product. They are not derived from model performance. Missing work earns no
owner credit. A source-contradicted adopted assertion also becomes one confirmed
error root cause, zeros every affected owner and applies the separately documented
0.7 trust-retention factor; repeated manifestations of that same cause are not
charged again.

| Strict owner (weight) | What is evaluated | Why this importance and relative weight | Preconditions and calculation | Missing versus wrong |
|---|---|---|---|---|
| P-A-EXCEPTION (0.05) | Correctly distinguishes A's period-low aggregate from January's C low | Medium atomic diagnostic; equal 0.05 share with other independent trend/risk conclusions | Singleton P-A-EXCEPTION; binary complete/correct | Missing loses 0.05; an adopted false comparison loses 0.05 and is a confirmed error |
| P-A-FEB-REPAIR (0.05) | Identifies and bounds the February A cached-rate defect | High data-quality exception, but one localized conclusion; 0.05 avoids outweighing population/meaning controls | Singleton P-A-FEB-REPAIR with cell/formula evidence | Missing loses 0.05; a false repair or propagated wrong value also creates error retention |
| P-B-RISK (0.05) | B complaint share, second-highest rate and management relevance | Medium independent burden/rate conclusion, peer-weighted with other priority observations | Singleton P-B-RISK | Missing loses owner only; wrong burden/rank loses owner plus confirmed error |
| P-B-SWING (0.05) | B's April–July observed movement | Medium trend observation; one of several complementary diagnostic findings | Singleton P-B-SWING | Missing loses 0.05; invented/wrong movement also triggers error retention |
| P-CAUSAL-LIMIT (0.05) | Refuses unsupported causal or responsibility attribution | High safety boundary, represented as one atomic closure alongside the larger severity/metric limits | Singleton P-CAUSAL-LIMIT | Missing loses 0.05; an adopted unsupported cause loses affected owners and adds error retention |
| P-FOLLOWUP (0.05) | Case review focused on observed peaks with a comparison period | Medium actionable output, balanced with the governance-field follow-up | Singleton P-FOLLOWUP | Missing loses 0.05; a false claim that review occurred is an adopted factual error |
| P-FOLLOWUP-FIELDS (0.05) | Requests month status, severity, category, customer and closure evidence | Medium governance closure, complementary to the case-review action | Singleton P-FOLLOWUP-FIELDS | Missing loses 0.05; fabricated completed fields/actions create error retention |
| P-FULL-SCOPE (0.08) | Period, source, PPM formula, aggregate method and unknown counting/cohort limits | Foundational multi-part population contract; 0.08 exceeds an atomic 0.05 item but remains below the two principal misuse boundaries | Singleton P-FULL-SCOPE; all stated parts required | Incomplete scope loses 0.08; a false population/formula also creates error retention |
| P-METRIC-LIMIT (0.10) | Distinguishes complaint-per-sales PPM from confirmed defective-unit PPM | Major category-error control affecting every conclusion; twice an atomic 0.05 finding | Singleton P-METRIC-LIMIT | Missing loses 0.10; false metric relabeling loses owner plus error retention |
| P-OVERALL-PEAKS (0.05) | Correct worst and second-worst overall months | Medium atomic prioritization finding | Singleton P-OVERALL-PEAKS | Missing loses 0.05; wrong peaks also create error retention |
| P-PRIORITY (0.05) | D high-rate containment priority | Medium management decision, separately balanced by B burden and severity limitations | Singleton P-PRIORITY | Missing loses 0.05; unsupported/wrong priority fact loses owner plus error retention |
| P-PRODUCT-PEAKS (0.05) | Highest product-month rates | Medium atomic localization; active weight is 0.05 even though its legacy within-group base is 0.10 | Singleton P-PRODUCT-PEAKS | Missing loses 0.05; wrong product/month/rate also creates error retention |
| P-SCOPE (0.05) | Treats September–December as unobserved, not zero or trend data | High missing-data boundary expressed as one atomic scope conclusion | Singleton P-SCOPE | Missing loses 0.05; adopting absent months as observed facts creates error retention |
| P-SEVERITY-LIMIT (0.17) | Separates rate/count priority from severity/customer-impact risk | Highest semantic owner because misuse can reverse management escalation without any supporting severity data | Singleton P-SEVERITY-LIMIT | Missing loses 0.17; invented severity/impact claims lose owner plus error retention |
| P-rate-reconciliation (0.05) | Month/product tables and same-scope aggregate reconciliation | Core quantitative evidence carrier; one 0.05 owner because its 4 leaves are partial-credit measurements supporting, rather than duplicating, the separately scored diagnosis | Weighted normalized mean of P-MONTH-TABLE, P-PRODUCT-TABLE, P-AGGREGATE-RECONCILE and P-RECONCILE using declared leaf bases | Missing/wrong leaves lose their effective share; wrong adopted values also create one deduplicated error cause |
| P-derived-product-risk (0.05) | Four complaint shares and four relative-rate ratios | One coherent derived-risk block; equal total weight to rate reconciliation with finer 8-leaf partial credit | Weighted normalized mean of P-SHARE-A, P-SHARE-B, P-SHARE-C, P-SHARE-D, P-RELATIVE-A, P-RELATIVE-B, P-RELATIVE-C and P-RELATIVE-D using declared leaf bases | Missing/wrong leaves lose their effective share; wrong adopted ratios also create deduplicated error retention |

## Source Checks

The values below are within-group aggregation bases, not additional reward weights. A singleton normalizes to its own 0/1 completion.
For a group G, completion = sum(base_i * correct_i) / sum(base_i). Effective leaf weights are represented at 18 decimal places with the final leaf closing the exact group budget.

| Check | Within-Group Base | Complete Requirement |
| --- | ---: | --- |
| P-A-EXCEPTION | 0.05 | - A产品的*八个月合计*PPM最低，其各月重算值在11.7225至32.0926之间；1月单月最低的是C产品，不是A产品。 |
| P-A-FEB-REPAIR | 0.09 | - 2月A产品D7缓存显示`20` PPM，但D6/D5 = 20/1,706,124 = 11.7225 PPM；应修复公式或缓存值。2月整体PPM和A产品累计值各自与其分子分母一致，不应因这一错误一并改写。 |
| P-AGGREGATE-RECONCILE | 0.01 | - 四类产品的销量与投诉数分别与整体总数完全一致。 |
| P-B-RISK | 0.05 | - B产品投诉639起，占全部1,130起的56.55%，且投诉率居第二，属于另一重点。 |
| P-B-SWING | 0.05 | - B产品从4月94.0182升至5月136.0505，6月降至45.7750，7月再升至158.0740 PPM；这种波动需要产品级调查。 |
| P-CAUSAL-LIMIT | 0.02 | - 工作簿未提供投诉类别、严重度、客户、批次或因果证据，不能仅凭该表断言根因或责任归属。 |
| P-FOLLOWUP | 0.05 | - 立即复核D产品5月及8月和B产品7月的具体案例，并保留B产品6月改善情况作为对照。 |
| P-FOLLOWUP-FIELDS | 0.05 | - 将受控月份状态、投诉严重度、类别、客户及关闭字段补入后续治理台账，再用于纠正措施管理。 |
| P-FULL-SCOPE | 0.08 | 范围仅为1月至8月。来源：`2024年客诉月CPPM统计表.xlsx`的第1张工作表。下表PPM均按投诉数量除以销量再乘100万计算，并保留两位小数；汇总PPM按投诉总数除以销量总数计算，而不是各月PPM的算术平均。原表未定义投诉的计次方式、重复投诉是否去重，也未说明销量与投诉是否属于同一生产批次。 |
| P-METRIC-LIMIT | 0.05 | - 文件名写`CPPM`、工作表写`PPM`，未给出单独的客户投诉PPM定义；这里只能按表内每百万销量的投诉比率解释，不能声称是已确认的不良品PPM。 |
| P-OVERALL-PEAKS | 0.05 | - 整体PPM最差为7月72.6039，次差为5月66.9320。 |
| P-PRIORITY | 0.05 | - D产品销量最低，但年内累计投诉率最高，应优先进行遏制和原因调查。 |
| P-PRODUCT-PEAKS | 0.1 | - 最高月度产品率为D产品5月181.2764 PPM，其次是D产品8月164.2537 PPM和B产品7月158.0740 PPM。 |
| P-RECONCILE | 0.05 | 各月A至D产品销量之和与整体销量一致，投诉数之和也与整体投诉数一致；例如7月投诉数为31 + 125 + 16 + 20 = 192。汇总单元格O2:O16仅依据前8个月，K:N列不是已观测月份。 |
| P-SCOPE | 0.05 | - 9月至12月销量和投诉数空白却出现`#DIV/0!`；这些未来或未提供的月份应标为不可用，并排除趋势结论。 |
| P-SEVERITY-LIMIT | 0.06 | - 该排序仅按投诉率：表格没有客户影响或严重度信息。B产品按投诉绝对数量排首位；若建立有依据的严重度风险模型，两者的先后顺序可能改变。 |
| P-SHARE-A | 0.0025 | A产品1-8月客诉占比 = 该产品期间客诉数 / 期间总体客诉数。分子分母必须同期间，允许百分比显示。 |
| P-SHARE-B | 0.0025 | B产品1-8月客诉占比 = 该产品期间客诉数 / 期间总体客诉数。分子分母必须同期间，允许百分比显示。 |
| P-SHARE-C | 0.0025 | C产品1-8月客诉占比 = 该产品期间客诉数 / 期间总体客诉数。分子分母必须同期间，允许百分比显示。 |
| P-SHARE-D | 0.0025 | D产品1-8月客诉占比 = 该产品期间客诉数 / 期间总体客诉数。分子分母必须同期间，允许百分比显示。 |
| P-RELATIVE-A | 0.0125 | A产品1-8月相对总体倍率 = 产品汇总PPM / 总体汇总PPM；各自按期间计数加总重算，不用月度率算术平均。 |
| P-RELATIVE-B | 0.0125 | B产品1-8月相对总体倍率 = 产品汇总PPM / 总体汇总PPM；各自按期间计数加总重算，不用月度率算术平均。 |
| P-RELATIVE-C | 0.0125 | C产品1-8月相对总体倍率 = 产品汇总PPM / 总体汇总PPM；各自按期间计数加总重算，不用月度率算术平均。 |
| P-RELATIVE-D | 0.0125 | D产品1-8月相对总体倍率 = 产品汇总PPM / 总体汇总PPM；各自按期间计数加总重算，不用月度率算术平均。 |
| P-MONTH-TABLE | 0.04 | All eight observed months: matching overall sales, complaints, overall PPM and all four product PPM values. Every required field complete and source-correct. |
| P-PRODUCT-TABLE | 0.04 | All four products: matching period sales, complaints, and aggregate PPM from summed counts. Every required field complete and source-correct. |

## Deductions And Settlement

Strict = sum(active weight * group completion) * 0.7 ** independent confirmed errors.
Each adopted independent factual error retains the original 0.7 coefficient. Same-root manifestations count once; unrelated errors remain separate.
An affected source check earns zero. Omissions do not create extra factual-error deductions. Correct additional content earns no extra credit.
The damage owner is an evidence-bound confirmed adopted error: an omission only
loses its positive item, while a false adopted claim also reduces trust retained
across the diagnosis by 30% per independent root cause. The 0.7 coefficient is a
damage weight, not a pass threshold or score cap. It reflects the high professional
severity of issuing a management diagnosis containing a source-contradicted fact;
same-root deduplication prevents repeated text from multiplying the harm.
Lenient is a source-domain usability gate, not a strict-score threshold. The 16
owners are partitioned into four professional domains: scope/boundaries,
quantitative reconciliation, trend diagnosis and decision/action. Four explicit
usable profiles each require three complete domains and omit one different domain.
Therefore one incomplete or wholly missing domain can remain lenient-usable when
the other three are complete; failures spanning two or more domains cannot. The
partition and profiles are machine-bound in `scoring_params.json`. Any confirmed
adopted factual error still fails lenient.
Missing or unreadable XLSX deliverables earn 0. A workspace argument resolves only `output/cppm_diagnosis.xlsx`; an output-directory argument resolves its own `cppm_diagnosis.xlsx`. Noncanonical backup files do not substitute for or override that artifact. There is no score ceiling or role/condition-specific adjustment.

## Judge And Replay

The only entrypoint is `tests/test.sh`. Ten numeric checks are recomputed from source counts and actual candidate cells/formulas.
Sixteen semantic checks use evidence-bound LLM decisions. A request-bound
evaluator cache replays an already validated response; a cache miss requires a
fresh evaluator call and an unmeasured artifact produces no numeric reward.
The semantic key binds the actual candidate/source/reference/prompt/model and extraction contract. The separate settlement fingerprint binds current scoring code and parameters.
Offline replay needs no endpoint/key when its request-bound evaluator cache is
provided. Missing semantic replies without evaluator API access return
review_required and remove stale rewards. Credentials belong only in the isolated verifier.

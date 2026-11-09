# Scoring: customer service quality report

All criteria are condition-blind and grounded in the supplied records and the
owner-approved reporting policy. No credit depends on the expert workbook's
visual layout, prose, worksheet names or arbitrary tie order.

| Item | Weight | Full credit | Partial credit | Zero credit | Anchor |
|---|---:|---|---|---|---|
| B01 Daily ranking | 0.5% | All source-bound daily ranking fields are correct | Mean field completion | No supported daily table | Finalized report-date records |
| B02 Cumulative ranking | 0.5% | All source-bound cumulative ranking fields are correct | Mean field completion | No supported cumulative table | Finalized cumulative records |
| B03 Period comparisons | 1.5% | Both period comparison tables are correct | Mean cell completion | No supported comparison | Finalized cumulative records by listening date |
| B04 Coverage | 0.5% | Daily and cumulative bases and coverage values are correct | Mean field completion | No supported coverage table | Operations context and counted quality records |
| B05 Dissatisfaction | 0.5% | The team-by-cause distribution is correct | Mean cell completion | No supported distribution | Finalized dissatisfaction records |
| B06 Fatal incident | 0.5% | The recorded fatal incident and relevant action are correct | Mean field completion | No supported incident | Fatal source record |
| B07 QA workload | 0.5% | All reviewer workload components and totals are correct | Mean field completion | No supported workload table | Quality records and operations context |
| B08 Native charts | 7.75% | Five native charts are correctly bound to the required report areas | One fifth per correctly bound chart role | No supported native chart | Native workbook chart references |
| A01 Contact record unit | 25% | An audit note states that one source row is one reviewed contact and repeated employee names are not deduplicated | Statement credit is multiplied by daily-ranking completion | Missing statement or no supported daily table | Reporting policy, source structure and task Skill |
| A02 Overlap key reconciliation | 9.5% | Audit notes state non-concatenation and document a row/key/field comparison between report-date and cumulative snapshots | Statement credit is multiplied by cumulative-ranking completion | Missing evidence or no supported cumulative table | Source snapshots and task Skill |
| A03 Score and comparison authority | 0.5% | Notes adopt finalized CF values without recomputation and reconcile the report-date comparison to the ranking | Mean note completion multiplied by period-comparison completion | Missing notes or no supported comparison | Reporting policy, finalized score column and report-date ranking |
| A04 Coverage formula and base | 0.5% | A note identifies reviewed contacts divided by the disclosed call-volume reference base | Statement credit is multiplied by coverage-table completion | Missing statement or no supported coverage table | Operations context and counted quality records |
| A05 Feedback scope closure | 0.5% | Notes distinguish the applicable dates and retain valid and invalid analyzed feedback in the required work population | One half for each supported scope closure | Neither scope closure is supported | Dissatisfaction dates/status and reporting policy |
| A06 Incident action boundary | 25% | The incident section separates observed facts from proposed action and includes process training or equivalent targeted coaching | One half for each supported action control | Neither action control is supported | Fatal source record, reporting policy and expert recommendation |
| A07 Workload boundary and reconciliation | 3.5% | Notes limit 62 complaints to aggregate workload and close `105 + 20 + 62 = 187` | One half for each supported closure | Neither closure is supported | Operations context and source counts |
| A08 Chart binding closure | 0.5% | Five native charts exist and a note states that categories and series bind to report data | Credit is multiplied by native-chart completion | Missing binding evidence or no supported charts | Deliverable requirement and native workbook references |
| A09 Follow-up verification control | 22.75% | The incident action includes follow-up sampling, post-training review or an equivalent future verification control | Full credit for a proposed verification control bound to the incident | No follow-up verification control | Expert incident recommendation and task Skill |

### Strict owner, dependency and severity ledger

| Item | Owner / dependencies | Source basis | Professional severity |
|---|---|---|---|
| B01 | program `P01` | finalized report-date records | high: daily management ranking |
| B02 | program `P02` | finalized cumulative records | high: cumulative management ranking |
| B03 | program `P03` | finalized records grouped by listening date | medium: period movement and consistency |
| B04 | program `P04` | reviewed-contact counts and disclosed call bases | high: denominator-sensitive sampling coverage |
| B05 | program `P05` | finalized dissatisfaction categories, team totals and grand total | medium: feedback cause distribution |
| B06 | program `P06` | source fatal record and observed evidence | critical: mandatory zero-score escalation |
| B07 | program `P07` | quality records plus disclosed dissatisfaction/complaint workload | high: QA capacity and reconciliation |
| B08 | program `P08` | task requires five editable, bound native charts | medium: required management views; blank/unbound series are invalid |
| A01 | deterministic semantic `S01` × `P01` | source row structure, reporting unit and Skill | critical: name deduplication changes the population |
| A02 | `S02` × `P02` | overlapping source snapshots and stable record keys | critical: concatenation double-counts contacts |
| A03 | `P03` × mean(`S03`,`S11`) | owner-approved finalized CF and report-date reconciliation | high: prevents unauthorized score recomputation |
| A04 | `S04` × `P04` | reporting-policy coverage formula, disclosed base and unverified cumulative-base period | high: denominator authority and period limitation |
| A05 | mean(`S05`,`S06`) | policy date dimensions and valid/invalid analyzed population | high: prevents scope/status exclusion bias |
| A06 | `P06` × `N01` × mean(`S09`,`I07`) | fatal source record, action boundary, whole-workbook non-completion check and targeted correction Skill | critical: action cannot exist without the incident or coexist with an unsupported completed-action claim |
| A07 | mean(`S07`,`S08`) | operations context: 62 aggregate complaints and 105+20+62=187 | high: complaint cases cannot be fabricated from workload only |
| A08 | `S10` × `P08` | task native-chart binding requirement | low: supporting audit note, locally dependent on actual charts |
| A09 | `P06` × `I10` × `N01` | source incident, whole-workbook non-completion check and Skill follow-up verification | critical: closes proposed action with future evidence, without inventing completion anywhere in the report |

### Per-owner calculation and weight rationale

Weights reflect the professional consequence and propagation range of each
reporting control, not model performance. Program owners use mean field/cell
completion. Semantic controls use documented binary components, with local
multiplication only where a control cannot be meaningful without its business
result. Missing content loses that owner's available credit. Wrong fields also
lose the same credit; only the independently defined D01/D02 harms receive an
additional once-per-root-cause deduction, so ordinary errors are not double-counted.

| Strict owner (weight) | What is evaluated | Why this importance and relative weight | Preconditions and calculation | Missing versus wrong |
|---|---|---|---|---|
| B01 (0.005) | Daily ranking fields and risk order | Narrow result table; low standalone weight because A01 separately owns the population control | P01 mean across manager/mean/attainment/samples/order checks | Missing/wrong fields lose their fractions; no extra damage unless independently D01/D02 |
| B02 (0.005) | Cumulative ranking fields and risk order | Narrow result table paired with A02's higher overlap risk | P02 mean field completion | Missing/wrong fields lose fractions; independent contradictions may additionally trigger D01 |
| B03 (0.015) | Both date comparison matrices | Three times a narrow table owner because it covers two metrics across two periods | P03 mean cell completion | Missing/wrong cells lose proportional credit; contradictory adopted duplicates may trigger D01 |
| B04 (0.005) | Daily/cumulative call bases and coverage | Narrow numeric result; denominator authority is separately controlled by A04 | P04 mean field completion | Missing/wrong fields lose fractions; no generic extra deduction |
| B05 (0.005) | Team-by-cause cells, team totals and grand totals | Narrow distribution output with 40 independently checked values | P05 mean cell completion | Missing/wrong cells lose fractions; conflicting adopted aggregates may trigger D01 once |
| B06 (0.005) | Fatal employee/team/score/category/failure/action | Narrow source row owner; its critical action consequences are owned by A06/A09 | P06 mean of five source/action checks | Missing/wrong fields lose fractions; invented additional zero-score employee may trigger D02 |
| B07 (0.005) | Reviewer workload components and totals | Narrow reconciliation table; boundary significance is separately A07 | P07 mean field completion | Missing/wrong fields lose fractions; contradictory totals may trigger D01 |
| B08 (0.0775) | Five valid native chart roles | Larger deliverable block requiring five editable bindings; one fifth per role and materially above a single table | P08 = valid roles/5; blank, malformed or unbound series invalidates that chart | Missing/invalid charts lose one-fifth each; no prose can substitute |
| A01 (0.25) | Contact row unit and no name deduplication | Highest accounting control because a wrong unit propagates through daily counts, means, attainment and coverage | P01 × S01 | Missing statement/result zeros A01; false population assertion also fails semantic source fidelity |
| A02 (0.095) | Non-concatenation and stable-key snapshot reconciliation | High cross-period duplication risk, but narrower than the universal contact-unit control | P02 × S02 | Missing evidence/result zeros A02; contradictory aggregate may also trigger D01 |
| A03 (0.005) | Finalized CF authority and report-date comparison agreement | Narrow authority/reconciliation closure already supported by B03 | P03 × mean(S03,S11) | Each missing semantic half reduces completion; false comparison also loses B03 cells |
| A04 (0.005) | Coverage formula, disclosed base and cumulative-period limitation | Narrow audit closure paired with B04; low weight avoids duplicating numeric coverage credit | P04 × S04 | Missing formula/period note or result zeros A04; wrong bases lose B04 fields |
| A05 (0.005) | Feedback date scope and valid/invalid analyzed population | Two narrow policy closures | mean(S05,S06) | Each missing half loses half credit; unsupported exclusions also reduce B05/workload where manifested |
| A06 (0.25) | Incident fact/action separation, targeted correction and no false completed action | Critical customer/employee escalation control; equal to A01 because unsupported completion or generic action defeats the mandatory fatal-case response | P06 × N01 × mean(S09,I07) | Missing components reduce/zero A06; any adopted completed-remediation contradiction makes N01=0 throughout the workbook |
| A07 (0.035) | 62 complaints as aggregate-only workload and 105+20+62=187 | Material workload/ledger boundary spanning two independent closures | mean(S07,S08) | Missing one closure loses half; fabricated complaint cases fail semantic fidelity and relevant results |
| A08 (0.005) | Audit statement that real chart categories/series bind to report data | Supporting closure only; actual charts carry 0.0775 in B08 | P08 × S10 | Missing statement or charts zeros A08; declaration never rescues invalid charts |
| A09 (0.2275) | Incident-bound future sampling/review with no false completion | Near-highest control because corrective action without future verification cannot demonstrate closure, while remaining slightly below A06's full action boundary | P06 × I10 × N01 | Missing verification zeros A09; any adopted completed-remediation contradiction makes N01=0 |

Positive weights sum to 100%. Accuracy tolerances permit two-decimal score display
and two-decimal percentage display (0.0051 score points or 0.0051 percentage points).
Counts and supplied bases must remain exact. Missing work earns no positive credit
and is not automatically penalized again.

Independent damage deductions, each applied at most once per root cause:
- D01 (0.02): two formally adopted aggregates assert inconsistent numeric results
  for the same scope and subject. Repeated consistent presentations and harmless
  rounding are allowed. An alternative diagnostic must be labeled as such.
- D02 (0.20): an additional named employee is falsely adopted as a zero-score fatal
  incident without a corresponding source incident. Ordinary below-threshold
  contacts are not this event.

D01 is a low-severity presentation-integrity deduction because the conflicting
adopted aggregate is already denied its own positive accuracy credit; 0.02 marks
the independent contradiction without double-counting every repeated cell. D02
is high severity because a fabricated named fatal incident creates an unsupported
employee escalation; 0.20 is applied once per root cause in addition to denying
the affected incident credit. Both are grounded in the reporting policy's ban on
invented incidents and conflicting adopted results.

Settlement: `max(0, sum(weight * completion_fraction) - independent_damage_penalties)`.
An absent, empty or invalid required workbook earns zero. Verifier execution or
missing recalculation-tool errors are invalid evaluations, not business scores.

The eight `B` items preserve cross-owner partial credit: one omitted result area
does not erase another independently correct area. `A01`, `A02`, `A03`, `A04`
and `A08` are local conjunctive chains whose source control must be accompanied
by the related business result. A06 and A09 likewise require a source-supported
fatal incident before its action controls can earn credit. The remaining controls
award their stated components separately. The 17 positive weights sum to exactly 1.0; no global
power, curve, floor or piecewise score transform is applied.

Expected values are derived from source operands rather than reference wording.
Recommendations and source notes receive separate semantic review; deterministic
checks do not certify arbitrary prose.

The required source-bound semantic judge evaluates A01-A09 as business meaning,
accepts equivalent wording and rejects keyword-complete but false, generic or
misbound prose. Positive semantic credit requires exact candidate and source or
reference evidence. Program checks supply only numeric/structural prerequisites;
they never award open-semantic credit from regexes or keywords. A worksheet whose
name contains "detail", "ledger", "明细" or similar is excluded as raw detail only
when its contents do not explicitly identify an incident or escalation. A chart
with a blank, malformed or unbound series is not counted as a correctly bound role.

## Delivery score lenses

Strict is the bounded additive score defined above. Lenient is an independent
binary usability lens, not a strict-score threshold. It requires one controlled
ranking route, either daily B01+A01 or cumulative B02+A02, plus the source fatal
incident B06, its bounded targeted action A06 and future verification A09. Daily
and cumulative are source-equivalent management ranking routes for this basic
lens; strict still scores both separately. Other business areas remain strict
owners and their individual absence does not by itself make the workbook unusable.
Any independent damage fails lenient. The exact routes are machine-bound in
`scoring_params.json::lenient_domain_routes`.

The mixed semantic review is required settlement evidence, not a cosmetic audit
receipt. It supplies A01-A09 completion; final strict combines those decisions
with program B01-B08 prerequisites and program damages. Judge failure is
UNMEASURED and removes numeric rewards. No hidden weight, center, scale, cap or
threshold is applied.

# Rest-day Hours Reconciliation Rubric

The only numeric authority is `tests/validator.py` with `tests/scoring_params.json`. This rubric evaluates evidence-supported event relations, not copied phrases, visual formatting or the number of columns.

Strict score is `max(0, B - D)`, where `B` is the weighted completion of the eleven independently owned business responsibilities and `D` is distinct business damage. The weights sum to 1. A linear completion scale is used because each owner already has an explicit professional share; applying a further power transform would punish the same omissions a second time and erase useful differences among partially complete reviews. Ordinary omissions lose their own positive credit only.

Lenient is the binary conjunction of six independent must-haves: both deliverables are present and parsed; all core event classifications and leave findings are correct; all required intervals are reproducible; every event has an object-bound citation; all required follow-ups are actionable; and no unsupported pay amount is adopted. It is not a strict-score threshold.

## Positive credit

Capability tags are defined in `tests/capability_map.json`: Domain judgment, Evidence handling, Numeric derivation, Cross-record reconciliation, Action closure and Rationale. These describe the measured work; they do not add another scoring layer.

| Owner | Weight | Measured work |
| --- | ---: | --- |
| Approved swaps | 0.11 | Correct approved-swap classification, inapplicable compensatory leave and the corresponding approved-shift disposition for both linked cases. |
| Evidence chains | 0.05 | Correct adopted classifications and leave findings with verified, event-bound source categories. |
| Unresolved follow-ups | 0.05 | Four case-specific evidence requests with HR and supervisor roles and a review milestone. |
| Attendance intervals | 0.05 | Ten subject- and date-bound entry/exit calculations, with hours within 0.015 of reproducible arithmetic. |
| Non-work record treatment | 0.27 | Correct non-work classification and inapplicable leave, preservation of relevant records and exclusion from rest-day work treatment. |
| Payroll reconciliation | 0.05 | Each payroll status and payroll's own leave reading, supported by the actual payroll source. |
| Unresolved activity disposition | 0.19 | The unresolved activity remains unresolved and the activity-specific evidence is requested before deciding the leave/payroll path. |
| Report controls and limits | 0.05 | Payroll evidence control; version, timestamp, notification and separate workflow control; no pay calculation and a subject-bound unresolved activity finding. |
| Supported leave disposition | 0.08 | Correct work and actual-rest findings with the corresponding retained internal leave treatment for both supported cases. |
| Unarranged leave disposition | 0.05 | Correct work/leave findings and a concrete leave application or payroll-review path. |
| Unsupported leave disposition | 0.05 | Correct findings and evidence/correction plus payroll review for both unsupported leave cases. |

Within each event, classification, leave finding and disposition contribute 25%, 25% and 20%. Chronology contributes 18% across five independently observable relations: schedule, initiation/notification, presence versus activity, leave processing versus actual rest, and payroll status. Evidence quality contributes 12% across event-bound references, the proposition established by each source, source limitations or contradictions, and correct subject/date/object binding. These shares reflect the task's professional sequence: reach the right decision, show how the records lead to it, and preserve the limits of that evidence. This preserves credit for a correct finding when another part is incomplete. The independent Lenient gate still requires every core classification and leave finding, so partial strict credit cannot turn an unusable review into a pass. Independent events within an owner use the original source-weighted mean: supported cases have equal shares, unsupported cases have equal shares, and the two swap shares are 0.045:0.035. Independent evidence, intervals, payroll rows, follow-ups and report relations use their original equal shares. No minimum is taken across independent events. Every source leaf remains measured once.

Classification and disposition credit are distinct from citation credit; citation formatting does not erase recognized substantive decisions. Explicitly dated calculations for a later leave day are not calculations for the original attendance day. Payroll readings remain separate from leave-ledger readings, and conflicting explicit readings cannot receive full credit.

## Independent business damage

| Affirmatively adopted error | Damage | Reason |
| --- | --- | --- |
| Calculating an unsupported pay amount | 0.040 per report | Requires salary and legal facts absent from the task |

Version 1.8 removes the additional penalties for classification, leave, payroll-status
and conflicting-required-answer errors: those operations already lose their own
positive credit. An additional unsupported pay-amount assertion has a distinct
owner and is charged once per report. Missing content, an ambiguous field, a
parse failure and a clearly unresolved question never create a damage charge.

## Equivalent representations and limits

Sheet names, row order, department/month display columns, and Chinese versus recognized English header aliases are open. Supported/valid, unsupported/invalid, pending/unresolved and inapplicable statuses are equivalent within their object and context. Source row references and record identifiers must point to the subject event. The report remains Chinese as requested.

Report actions are scoped to their named subjects. Shared actions naming several cases may apply to all of them; a numbered exceptional group must resolve to a previously named group. Another subject's action cannot supply a missing disposition. Actual-rest, approved-shift and unresolved-activity equivalents retain credit. The unresolved report finding accepts names or event identifiers and linked sentences; another subject's issue, a legal caveat or a negated pending label does not supply that finding.

Version 1.9 recognizes equivalent follow-up headers for evidence to obtain,
facts to establish and unresolved risks, as well as equivalent shift-table
wording. Approval records for a processing plan retain their explicitly bound
leave scope. Evidence, responsible roles, review milestones and an actual issue
are still independently required. Missing components, negated requests and
example-only requests receive no follow-up credit.

Exact statutory articles, legal deadlines and pay multipliers in the expert report are not scored because their authoritative texts were not bundled. The original report's truncated opening is preserved and is not a scoring anchor. No artificial "half deleted" cap applies: only removed scored evidence changes the positive ledger.

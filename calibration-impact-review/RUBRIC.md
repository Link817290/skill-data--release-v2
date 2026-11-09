# Evaluation Rules

Strict reward preserves partial credit for every scored business owner, then adds
credit for local dependencies that are meaningful only when all of their stated
parts hold. Each of the ten scored numerical owners and four semantic owners earns
0.5% independently. The remaining 93% is allocated as follows:

| Integrated work | Weight | Required parts |
| --- | ---: | --- |
| Fixed-baseline review | 20% | Correct baseline reconstruction, source-supported method explanation, operational limitations and bounded downstream scope |
| Optical impact decision | 14% | Correct optical limits and record/day decisions, supported action and bounded downstream scope |
| Small-tail numerical review | 12% | Stable small-tail calculation, source-supported method explanation and appropriate limitations |
| Monitoring-shift interpretation | 12% | Correct trend calculation, supported review action and appropriate limitations |
| Rerunnable calculation | 10% | Reordering/path robustness, changed-record response, changed-setting response and invalid-input rejection |
| Supported supplied-run summary | 8% | Correct structured summary/scope, supported conclusion and source evidence |
| Operational applicability | 12% | Correct limitations and evidence-bounded downstream scope |
| Bounded final conclusion | 5% | Supported conclusion and evidence-bounded scope |

The scored numerical owners are summary/scope, baseline reconstruction, optical
limits, record and day decisions, monitoring trend, representation robustness,
changed-record recalculation, changed-setting recalculation, small-tail stability
and invalid-input rejection. Invalid-input credit is the mean of independently
executed public cases. The four semantic owners are conclusion, evidence,
trade-offs and scope; each uses the published 0, 0.5 or 1 completion scale.

Two additional checks are diagnostic only and do not change strict or lenient
reward: recalculation at the documented alpha=0.001 setting, and installed
dependencies plus executable README commands. They remain visible in evaluation
evidence while remaining outside this release's fixed-product score.

The trade-off explanation is an operational-applicability owner. It is not copied
into the baseline, tail and monitoring chains, so a limitation is not multiplied
four times merely because it is mentioned in several sections.

## Error Ownership

Required fields, membership, limits, decisions and exception rows are reconstructed
from the issued records and settings. Equivalent row order, identifier forms such
as 1 and 1.0, algebra and source-correct wording are accepted.

A submitted JSON or CSV defect belongs to its originating output owner. If the
same defect recurs after reordering or another input transformation, it is not
charged again; the transformation owner fails only for an additional defect.
Likewise, one numerical root error is not repeated as several semantic deductions
merely because its value appears in several summaries. An independently unsupported
customer action, product verdict or closure claim is a separate business error.

The local dependency credit does not erase independent partial credit. For
example, correct baseline arithmetic remains credited when downstream scope is
wrong, while the complete baseline-review dependency is not earned.

## Lenient Completion

Lenient reward is binary and independent of the continuous strict total. Its
numeric side asks whether the delivered tool is minimally usable:

- the required deliverables parse;
- the CLI executes successfully on the supplied inputs;
- every required result family and issued record is covered.

It also requires independent core-completion verdicts for conclusion, evidence,
trade-offs and scope. A wrong individual limit, trend value, representation
variant or invalid-input case remains strict partial credit and does not by itself
make the whole tool unusable. Neither a high strict score nor either diagnostic
check can substitute for a missing minimum-usability decision. If the deliverables
cannot be parsed, the CLI cannot run, or an entire result family is absent, one
20% minimum-usability deduction is applied; related symptoms do not repeat it.
A semantic score of 0.5 represents a separable quality omission while the core
brief remains complete. If a semantic core brief fails, that criterion is 0 and
its published local dependencies remove substantive strict credit.

## Measurement Boundary

Candidate omissions, incorrect calculations and unsupported business claims are
measured failures and receive the applicable partial or zero reward.

Missing trusted inputs, a failed isolation bootstrap, an unavailable semantic
service without a request-bound replay, a malformed service response, or another
evaluator infrastructure failure is UNMEASURED. In that state the evaluator exits
nonzero, clears standard reward files and never reuses a stale score.

The semantic review binds short exact candidate and source quotations. A conflict
between the reference and original material withholds semantic measurement for
review rather than penalizing a source-correct submission. No visual-polish score
or hidden model-dependent parameter is used.

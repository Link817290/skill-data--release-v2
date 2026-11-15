# Full-Chain Table Consistency Audit Rubric

The evaluator scores one Chinese Markdown audit against the issued proposal.
Arithmetic, source values, locations, table coverage, and adopted error
directions are deterministic. A separate integrity judge rejects pervasive
padding, source dumping, grader instructions, and unfinished structures.

## Strict Score

Strict reward is the weighted sum of the following independent owners, followed
only by deductions for independently demonstrated harmful assertions. Owner
weights sum to 1. Ordinary omission loses its owner credit and is not multiplied
again.

| Owner | Weight | Professional basis |
| --- | ---: | --- |
| P02 Missing weight reconciliation | 0.04 | A weight column totaling 75% cannot support a composite score. |
| P03 Percentage-basis consistency | 0.05 | Percentage points and relative change cannot share one unlabeled result column. |
| P04 SLA response-time consistency | 0.05 | Conflicting P1/P2 response commitments create direct delivery risk. |
| P07 Non-numeric coverage claim | 0.05 | Category labels cannot substantiate a 300% increase. |
| P08 FPGA TCO replay | 0.05 | The published node count and unit/development costs must reconcile to TCO. |
| P09 Six-layer versus three-row mechanism | 0.17 | Missing compliance layers materially weaken the stated governance mechanism. |
| P10 Ten-point matrix unit consistency | 0.05 | Raw milliseconds, currency, text, and scores cannot be combined as one ten-point scale. |
| P12/P13/P14/P17/P21 Author-confirmation items | 0.19 total | Ambiguous differences receive credit only when the alternative reading and confirmation need are explicit. |
| P28/P30 Checked-consistent items | 0.06 total | Apparent anomalies need a reproducible clearing calculation or source reading. |
| P33 Energy-mode range inconsistency | 0.06 | Full high-performance to saving-mode reductions exceed the stated frequency, power, and latency ranges. |
| P41 Finding location | 0.03 | Every active confirmed finding must identify the source section, table, or heading. |
| P42 Complete table coverage | 0.20 | The instruction requires all 97 native tables and four paragraph-form pseudo tables to be audited. A complete explicit census or equivalent section/table identification is accepted; `T1`–`T97` and `PSEUDO-A`–`D` labels are not required. |

P01, P05, and P06 are retained as diagnostics with zero weight. Equal GPU power
does not establish identical model or architecture; a 200 ms result can satisfy
a less-than-500 ms threshold; and latency ranges from unspecified workloads or
pipeline stages cannot be forced into one comparison.

P42 gives proportional credit for distinct source tables represented in a
reviewable ledger. Each row records table identity, structure, data-density
checks, duplicate-row checks, and disposition. Repeating a generic status
without table-specific evidence fails the integrity gate.

## Deductions

Deductions apply only to adopted, independently harmful statements. Repeated
wording of one causal error is one instance.

| ID | Retention | Trigger |
| --- | ---: | --- |
| D02 | 0.90 | An explicit arithmetic recomputation in a finding does not replay. |
| D03 | 0.90 | The report reverses the source-supported direction of a confirmed issue. |
| D04 | 0.90 | A finding is bound only to source sections that do not contain its evidence. |
| D05 | 0.90 | The report recommends sending the proposal unchanged despite confirmed material issues. |
| D06 | 0.90 | The report invents a definitive corrected value not supported by the proposal. |
| D10 | 0.90 | A source-supported confirmed issue is declared consistent without resolving it. |
| D12 | 0.80 | A figure value is used as one side of a reported table conflict. |
| D14 | 0.80 | A source range or quoted source statement is restated incorrectly. |
| G-LANG | 0.20 | The required Chinese audit is predominantly written in another language. |

The former Golden-whitelist overgrading, extra-finding count, fixed section
number, auxiliary-file, and document-length deductions are retired. They
punished comprehensive professional review or style rather than demonstrated
business error.

## Lenient Score

Lenient reward is 1 only when:

- P02, P03, P04, P07, P08, P09, P10, and P33 each reach at least 0.5;
- P42 table coverage is at least 0.8;
- P41 location coverage is at least 0.7; and
- no active harmful deduction instance remains.

It is independent of a strict-score threshold.

## Integrity Judge

The integrity judge checks whether the deliverable is a real, complete attempt
and obeys the task text. It does not decide technical correctness. Configure it
with LLM_JUDGE_BASE_URL, LLM_JUDGE_API_KEY, and optional LLM_JUDGE_MODEL.
Request-bound Golden replay may be used offline; changed artifacts require a
fresh call. Missing judge infrastructure is UNMEASURED.

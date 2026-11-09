# Customer service quality report

You are preparing the online customer service team's service-quality analysis for
26 March 2015. Produce an editable Chinese Excel report for the team leads and QA
manager from the supplied finalized quality records and operations context.

## Inputs

The files are under `/workspace/materials/`:
- `quality-records.xlsx`: quality-review records and dissatisfaction analyses.
- `operations-context.xlsx`: disclosed call-volume reference bases and complaint-analysis workloads.
- `reporting-policy.md`: reporting scope, metric definitions and authority of the records.

## Deliverable

Save `/workspace/output/service-quality-report.xlsx`. It must contain:
- Team rankings for the report date and the cumulative period, showing supervisor,
  team, mean finalized quality score, attainment rate, reviewed-contact count,
  call-volume reference base and sampling coverage. Put lower attainment first;
  ties may appear in any order.
- Team-by-team comparisons of the two review dates, for mean scores and attainment.
- Dissatisfaction counts by team and recorded root-cause category, with totals.
- The fatal-quality incident escalation: employee, team, finalized score,
  contact category, the observed failure and a relevant actionable improvement.
  Keep recorded observations distinct from proposed future actions.
- QA workload by reviewer: quality monitoring, dissatisfaction analysis,
  complaint analysis and total completed reviews.
- Five editable Excel charts covering the two team rankings, the two period
  comparisons and dissatisfaction root causes. Each must have meaningful categories
  and series bound to its report data, rather than a pasted image.

Use clear semantic headings. Sheet names, section order, styling and chart types
are your choice. Include concise calculation/source notes so a reviewer can audit
the scopes, percentages and incident evidence. Those notes must document that
each source row is one reviewed contact (do not deduplicate repeated employee
names); reconcile the report-date snapshot with the cumulative snapshot by
stable record keys without concatenating them; adopt finalized CF scores without
recomputing them; define coverage as reviewed contacts divided by the disclosed
call-volume base, state that the cumulative base is only a disclosed reporting
premise whose full period is not verified by an independent call ledger;
distinguish feedback event/review dates and retain both valid
and invalid analyzed feedback in workload; limit the 62 complaints to aggregate
workload and reconcile `105 + 20 + 62 = 187`; and state that native chart series
and categories bind to report data. Keep the incident's observed facts separate
from a proposed targeted process correction or coaching, and include a future follow-up sample or review
without claiming it has already occurred. Scores may be displayed to two
decimals and percentages to two decimal places; retain sufficient numeric precision
in the workbook. Do not invent source transactions, complaint cases, approvals or
completed remediation. Do not modify the supplied source files.
Treat disclosed call-volume bases and complaint-analysis counts as reporting
premises, not transaction or complaint-case ledgers, and do not expand their
period, case findings or evidentiary authority.

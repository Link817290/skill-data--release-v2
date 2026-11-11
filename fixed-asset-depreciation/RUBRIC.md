# Fixed-Asset Depreciation Scoring

The verifier opens a private copy with macros disabled, recalculates in the
pinned offline spreadsheet engine, and measures actual financial outputs after
uniform changes to the supplied business inputs. Model identity and skill
condition are not available to the scoring predicates.

| Owner | Weight | Required Business Work |
| --- | ---: | --- |
| P01 | 0.05 | Four-method depreciation engine: assumptions, annual/monthly schedules, workload openings, residual caps and report balances |
| P03 | 0.05 | Expenses attributed to the department in each recorded month |
| P04 | 0.19 | Dashboard departmental depreciation retains historical expense ownership |
| P05 | 0.33 | Dashboard departmental cost, accumulated depreciation and carrying value use cutoff ownership |
| P06 | 0.05 | Category/global summaries, expense totals and annual reconciliation |
| P07 | 0.18 | Opening records have the proper key and numeric amount and do not silently admit an amount above depreciable basis |
| P08 | 0.05 | Visible diagnoses for invalid asset, master-data, workload, transfer and reporting-period inputs |
| P09 | 0.05 | Routine asset/method/category/department maintenance within the supplied capacity |
| P10 | 0.05 | Preserved business inputs, workbook structure, charts and offline spreadsheet formulas |

Each native atomic comparison and each semantic diagnosis is binary. Independent
business cases earn meaningful partial completion through arithmetic means.
The assumptions-to-schedule-to-report calculation chain and the opening-record
admission chain use a minimum across their prerequisites. The three time-based
methods and one workload method retain a 3:1 arithmetic share in P01.

The weighted completion is `B = sum(weight * completion)`. Strict reward is
`B ** 1`, so the reported strict score remains the weighted business completion.
Owner weights and the calculation/admission prerequisite minima already encode
materiality and dependency; no unsupported nonlinear compression is added.
The same formula applies to every artifact, reference and probe. There are no
role multipliers, deductions or final-score caps.

Weights reflect accounting materiality, financial-statement propagation and the
number of independently tested reporting states. The numeric allocations are a
coarse-grained policy for this supplied workbook. Partial completion preserves
the remaining verified accounting value. Prerequisite minima deduplicate one
broken calculation or admission root so downstream manifestations do not
manufacture extra credit; there are no separate deduction coefficients.
Severity bands are: critical financial-stock owner `0.33`; high propagation or
source-admission owners `0.18-0.19`; supporting calculation, control and
maintainability owners `0.05`. Within each owner, scenario means retain unaffected
value while prerequisite minima collapse only the shared causal root.

## Owner Explanations

### P01 Four-Method Depreciation Engine (`0.05`)

**Evaluates:** Assumptions, annual/monthly schedules, workload openings, residual caps and reporting balances for straight-line, SYD, DDB and workload methods.
**Professional importance:** It establishes method-level arithmetic before amounts flow to reports.
**Weight rationale:** `0.05` is a focused engine owner; downstream expense, stock and opening owners independently retest its financially material effects, avoiding double weight.
**Prerequisites/dependencies:** Valid asset master data, method, acquisition date, useful life, residual precedence and keyed opening/workload inputs; the time engine uses prerequisite minima and the workload method retains a 3:1 method share.
**Calculation:** `(3 * time_engine + workload_completion) / 4`, then multiplied by `0.05`.
**Missing versus error:** Missing formulas fail affected atomic cases. Wrong formulas fail recalculated outputs; invalid-input diagnoses belong to P08 and affirmative unsupported workbook behavior is not inferred.

### P03 Monthly Department Expense Attribution (`0.05`)

**Evaluates:** Department assigned to each depreciation expense in the month incurred.
**Professional importance:** Expense is a period flow and must follow transfer effective dates.
**Weight rationale:** `0.05` is local because broader historical ownership is separately tested by P04.
**Prerequisites/dependencies:** Correct monthly depreciation and ordered transfer records.
**Calculation:** Arithmetic mean of affected monthly expense-allocation checks, multiplied by `0.05`.
**Missing versus error:** Missing links and wrong departments both fail their months; wrong cutoff stock ownership is P05, not P03.

### P04 Historical Departmental Depreciation Flows (`0.19`)

**Evaluates:** Dashboard departmental depreciation retains historical expense ownership across transfers and periods.
**Professional importance:** Reassigning past expense to the current department materially misstates departmental performance.
**Weight rationale:** `0.19` is high because history is tested across months, transfers and report periods and directly affects management reporting; it remains below P05 stocks.
**Prerequisites/dependencies:** P03 monthly attribution and effective-dated transfer ordering.
**Calculation:** Mean of historical dashboard flow checks, multiplied by `0.19`.
**Missing versus error:** Missing historical links and wrong retroactive ownership fail affected cases; current cutoff ownership alone cannot substitute.

### P05 Cutoff Departmental Financial Stocks (`0.33`)

**Evaluates:** Departmental cost, accumulated depreciation and carrying value at each reporting cutoff.
**Professional importance:** These are balance-sheet stocks and the largest direct financial-statement exposure.
**Weight rationale:** `0.33` is the largest owner because three stock measures are tested across multiple cutoff, transfer and long-service scenarios; P03/P04 separately own expense flows.
**Prerequisites/dependencies:** Correct asset basis, accumulated depreciation, report period and department effective at cutoff.
**Calculation:** Mean of nonzero/failed department stock checks over scenarios, multiplied by `0.33`.
**Missing versus error:** Missing stock links and wrong ownership/amounts fail affected cells; expense-flow correctness does not prove stock correctness.

### P06 Category And Global Summaries (`0.05`)

**Evaluates:** Category/global cost, depreciation, net value, expense totals and reconciliation.
**Professional importance:** Summary controls expose broken aggregation and stock/flow mixing.
**Weight rationale:** `0.05` is local because underlying asset and departmental amounts carry most materiality under P01/P03-P05.
**Prerequisites/dependencies:** Correct underlying asset schedules, category mapping and reporting period.
**Calculation:** Mean of total, dashboard-summary, category-flow and category-stock scenario means, multiplied by `0.05`.
**Missing versus error:** Missing summaries and wrong aggregation fail local checks; copied zeros do not dilute affected nonzero cases.

### P07 Opening Record Admissibility (`0.18`)

**Evaluates:** Asset/year opening key, numeric opening amount and prohibition on openings above depreciable basis.
**Professional importance:** Invalid openings corrupt all later accumulated depreciation and workload quota.
**Weight rationale:** `0.18` is high because the opening is a source-state gate with downstream multi-period effects, comparable to P04 but narrower than P05.
**Prerequisites/dependencies:** Unique asset/year key, valid depreciable basis and visible invalid-input diagnosis.
**Calculation:** Minimum of mean valid-opening diagnoses and the above-basis admission decision, multiplied by `0.18`.
**Missing versus error:** Missing/duplicate/non-numeric records lose the relevant diagnosis cases; silently admitting above-basis amounts fails the prerequisite minimum.

### P08 Visible Input Diagnoses (`0.05`)

**Evaluates:** Visible diagnoses for invalid asset, master-data, workload, transfer and reporting-period inputs.
**Professional importance:** Operators need actionable native feedback rather than silent formula corruption.
**Weight rationale:** `0.05` reflects usability/control evidence; financial misstatement is separately weighted in P01/P03-P07.
**Prerequisites/dependencies:** Native recalculation must expose an actual changed visible output bound to each invalid input.
**Calculation:** Mean of asset/period, master, workload and transfer diagnosis-family means, multiplied by `0.05`.
**Missing versus error:** Missing diagnosis loses that binary scenario. Equivalent wording/location is accepted; evidence not bound to an actual output is verifier error or failed evidence, not guessed credit.

### P09 Routine Maintenance (`0.05`)

**Evaluates:** Add/change asset, method, category and department data within supplied workbook capacity.
**Professional importance:** A fixed model must remain maintainable without rewriting formulas.
**Weight rationale:** `0.05` is a bounded maintenance owner; unrequested unlimited expansion is excluded.
**Prerequisites/dependencies:** Preserved configured tables, formulas and last supported rows.
**Calculation:** Mean of declared maintenance scenarios, multiplied by `0.05`.
**Missing versus error:** Missing propagation or wrong recalculation fails the scenario; no points are removed for unsupported capacity beyond the supplied design.

### P10 Native Workbook Preservation (`0.05`)

**Evaluates:** Preserved business inputs, sheet structure, charts and offline native formulas without macros/external links.
**Professional importance:** A numerically correct replacement that destroys the issued workbook is not a usable accounting model.
**Weight rationale:** `0.05` is a gate-like local owner because detailed financial behavior is scored elsewhere and the independent lenient check also requires native integrity.
**Prerequisites/dependencies:** Original nine-sheet workbook and supplied inputs.
**Calculation:** Minimum of structural/formula completion and measured source-input preservation, multiplied by `0.05`.
**Missing versus error:** Missing sheets/formulas, changed inputs, broken chart series, collapsed row/column presentation, or lost issued styles fail the affected preservation checks; equivalent visible formatting remains acceptable where it preserves those structures.

## Lenient Minimum-Usable Result

Lenient is the conjunction of eight independently reported checks:
`native_integrity`, `four_method_bridge`, `period_ownership`,
`year_department_bridge`, `safe_workload_opening`, `global_summary_correct`,
`all_required_diagnostics`, and `configured_capacity_maintenance`. Each check remains visible
in `must_have` and failed IDs are reported, so the binary result does not hide
whether one boundary or the entire model failed.

Financial comparisons accept exact and cent-rounded monthly/annual policies,
using an error envelope that accumulates only across the financial aggregation
span. Correct copied zeros and unused annual years do not dilute failures of
the affected assets or departments. Actual formula errors fail the affected
financial comparison. Missing infrastructure or unresolved semantic evidence
is a verifier error and never silently becomes a candidate zero.

The dashboard is assessed within its supplied display scope: six category rows
and ten departmental rows. Expense allocation retains the full configured
department capacity. No unrequested disposal, tax, impairment, unlimited-row
or expanded-dashboard rules are added.

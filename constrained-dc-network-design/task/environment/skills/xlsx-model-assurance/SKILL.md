---
name: xlsx-model-assurance
description: Build and close auditable Excel planning workbooks whose detail, summaries, formulas, and source controls remain traceable. Use when the required deliverable is a native .xlsx model rather than a flat export, especially for large allocation, finance, operations, or scenario workbooks.
---

# XLSX Model Assurance

## Trigger and boundary

Use this method once the analysis must become an editable Excel working file with
detail-to-summary lineage. Apply it while constructing the workbook, not only after
values have been pasted.

This method assures file structure, formula lineage, and presentation closure. It does
not validate the domain meaning of a route, rate, contract, or allocation. Domain
controls must already exist and remain visible in the workbook.

## Workbook Lineage Closure framework

Use the **Workbook Lineage Closure (WLC)** framework. It has five criteria:

1. **Source protection:** input files remain unchanged and identifiable.
2. **Stable keys:** joins and formulas resolve through business identifiers.
3. **Detail lineage:** derived decision and cost fields remain visible at unit level.
4. **Summary reconciliation:** executive and facility outputs derive from detail.
5. **Native-file integrity:** the delivered OOXML file opens, contains formulas, and
   has no unresolved formula errors or unintended external dependencies.

Create a workbook control record before writing sheets:

```text
output path | source hashes | detail grain | key columns | summary dependencies | recalculation method
```

## Source-protection and schema capture

Open source workbooks read-only for inspection and load them without overwriting the
original. Capture sheet names, used ranges, headers, key counts, and formula presence
before transformation. Preserve identifiers as text and dates as dates.

Do not rename, repair, or enrich the supplied source in place. When normalized values
are needed, write them into the output workbook or a temporary build artifact. Keep a
source checksum or equivalent immutable control outside the calculation cells and
verify it again after the output is saved.

Treat a changed source schema as a revision trigger. If a header, key population, or
row count changes, invalidate downstream formulas and rebuild the dependent ranges;
do not silently keep old column offsets.

## Keyed detail-model construction

Give each atomic business unit one durable row in the detail model. Put source keys,
decision state, evidence keys, component calculations, and exception state on that
row. A summary-only model cannot be back-checked.

Prefer structured tables or stable absolute ranges over formulas tied to incidental
row positions. When formulas are generated programmatically, audit the first, a
middle, and the last populated row for correct relative references.

Useful formula patterns include:

```excel
=COUNTIF(detail_status_range,"Assigned")
=SUMIFS(detail_cost_range,detail_facility_range,current_facility)
=IF(decision="Assigned",handling_cost+freight_cost,0)
```

These are patterns, not required names or layouts. Use formulas appropriate to the
workbook and application compatibility target. Keep decision inputs as values and
derived summaries as formulas so reviewers can distinguish judgments from
calculations.

After writing each detail block, persist a control row with its first and last key,
record count, formula count, and exception count. This catches tail truncation before
formatting begins.

## Cross-sheet summary lineage

Executive and facility views must point back to detail calculations. Use cross-sheet
references or keyed aggregate formulas for material totals, rather than repeating
numbers as constants.

Maintain a dependency register:

```text
published metric | destination cell | source detail field | reconciliation formula | expected unit
```

At minimum, close population, served/unserved totals, capacity or utilization,
component cost, and total cost when those are in scope. Recompute the same quantities
from parsed detail rows in an independent check; matching formula text alone does not
prove that the referenced range covers the population.

If a later exception or assignment correction changes detail, refresh every summary
whose dependency register points to that field. Do not patch the published total.

## Scenario and governing-case registers

When the decision includes disruptions or alternatives, keep one structured scenario
register instead of hiding event meaning in prose or worksheet colors. At minimum use:

```text
scenario_id | unavailable object | scope basis | achieved service | residual demand | variable cost | governing flag | status
```

The scenario register and order detail must share a stable scenario identifier. A
comparison total with no join to event state is not auditable. If only the governing
event requires full detail, retain summary rows for every screened event and a complete
decision population for that governing identifier.

Build separate facility reconciliation records for primary and recovery use. Capacity
for an unavailable facility should be visibly zero or unavailable in recovery, and
every recovery summary should link to the event-specific detail rather than to the
primary allocation.

## Formula and OOXML assurance

Inspect the saved file twice: once with formulas visible and once with cached values if
a recalculation engine is available. Formula-writing libraries often preserve formulas
without evaluating them; decide whether the recipient application will recalculate on
open and set calculation mode accordingly.

Use `scripts/audit_xlsx_lineage.py` for a structural report:

```bash
python scripts/audit_xlsx_lineage.py model.xlsx --output lineage_audit.json
```

The script reports sheet dimensions, formula counts, cross-sheet formula counts,
formula-error cells, external-link formulas, merged ranges, filters, freeze panes, and
hidden sheets. It does not decide whether formulas express correct business logic.

Review formulas that contain external workbook tokens such as `[other.xlsx]`.
Unintended links make the deliverable non-portable. Also inspect formulas containing
`#REF!`, and confirm that the OOXML archive opens as a ZIP and reloads successfully.

## Review-oriented presentation

Format for repeated operational use rather than decoration:

- Keep the most decision-relevant summary visible first.
- Freeze identifiers and headers on long detail sheets.
- Enable filters on tabular outputs.
- Use consistent number formats for counts, currency, weights, percentages, and days.
- Use restrained status colors with text labels; color alone must not carry meaning.
- Size columns to keep identifiers and exceptions readable without making detail
  sheets excessively wide.
- Put assumptions and decision boundaries in a compact model-notes area, not in cell
  comments that may be missed.

Avoid merged cells inside sortable data regions. Tables, panes, widths, and styles are
presentation aids; they never substitute for detail completeness or formula lineage.

## Formula back-check and revision

Sample formulas by business risk, not just row number. Include:

- the first and last unit;
- every decision or exception state;
- zero and non-zero monetary components;
- boundary conditions in lookups or rate bands;
- at least one row for every published facility or category.

For each sample, recompute from source values and compare both the formula dependency
and numeric result. When a sample exposes a wrong range or lookup, revise the formula
template and regenerate the full affected column. Do not hand-fix isolated cells.

## Closing reconciliation

Before delivery, verify:

- The file exists at the required path and has a genuine `.xlsx` OOXML structure.
- The source checksum still matches the pre-build control.
- Detail row count and distinct business keys reconcile to the source population.
- Required scenario rows reconcile to the primary positive-flow facility population,
  and governing recovery detail reconciles to the same source demand keys.
- Every material published total is formula-linked to detail or a clearly identified
  calculation block.
- Formula ranges include the final populated row and exclude headers and totals.
- No duplicate decisions, broken references, or unintended external links remain.
- Formula counts and cross-sheet counts are non-zero where a working model is required.
- Filters, freeze panes, widths, formats, and notes make the workbook reviewable.

Save, close, and reload the final file for this pass. A workbook that only works in the
in-memory object used to create it is not a finished deliverable.

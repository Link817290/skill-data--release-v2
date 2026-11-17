---
name: structural-load-combination-audit
description: Audit load cases, signed force and moment combinations, stability factors, bearing checks, and omitted-case scope in structural calculation reports. Use when permanent, hydraulic, construction, maintenance, or seismic actions must be reconciled to case-specific limits and source evidence.
---

# Structural load-combination audit

Use this capability when reviewing a calculation report that mixes permanent, variable, hydraulic, seismic, construction, or maintenance actions. The aim is to establish whether the reported design effects and stability checks are supported by the supplied load cases, not to repeat a favorable summary sentence.

## 1. Build a source ledger

1. Extract the report's load-case names exactly as written, including the Chinese label if that is the source identifier. Keep a separate column for a translated description; never replace the source identifier.
2. Record the effect sign and unit for every component (force, moment, stress, or factor). A dash, blank, and numeric zero are different observations.
3. Capture the governing limit beside each observation and cite the report section/table/page. If the report gives a limit only in narrative text, link all affected rows to that clause.
4. Mark whether a case is a basic, accidental/special, service, construction, inspection, or seismic combination only when the report supports that classification.

The ledger should let a second checker trace a result to one source cell without guessing which repeated table is intended.

## 2. Reconstruct combination arithmetic

For each force or moment subtotal, recompute the signed sum from the component rows. Preserve the report's precision for the displayed result and keep a higher-precision working value. Round only for presentation.

Check both directions when a table has downward and upward actions. A net vertical force is not interchangeable with the downward subtotal, and an uplift arm has the opposite moment sign. Confirm that the reported resultant moment equals the signed component moments, not the sum of absolute magnitudes.

For a stability factor, identify numerator and denominator from the report's definitions or calculation context. Compare the reported factor with the applicable allowance for that same case. Do not borrow an allowance from a neighboring combination merely because it is close in the table.

Use the following invariants as diagnostics, not as unqualified conclusions:

- subtotal = sum(component values), within a documented rounding tolerance;
- resultant moment = sum(signed component moment values);
- factor >= its case-specific allowance when the factor is applicable;
- maximum bearing stress does not exceed the stated bearing limit, and a reported minimum stress is interpreted with its sign.

## 3. Handle scope and non-applicability

A dash can mean “not calculated for this case” rather than zero. Read the paragraph that describes which checks were run for each case. If a case is explicitly exempt from a factor check, record `PASS` for the scope decision only when the text supports that exemption; otherwise use `REVIEW` and explain the missing basis.

Do not infer omitted hydraulic, ice, or seismic actions from a generic standard. The assignment is a review of the supplied report. An absent component should be recorded as absent, with a review finding if the component is binding to the claimed check.

## 4. Calibrate conclusions

Separate four outcomes:

- `PASS`: the supplied value, unit, arithmetic, and applicable limit close;
- `FAIL`: a supplied value or arithmetic relation demonstrably violates its governing limit;
- `REVIEW`: a binding input, applicability statement, or unit conversion is absent or ambiguous;
- `NOT_APPLICABLE`: use only when the report explicitly says the check does not apply. If the deliverable contract has only three statuses, fold this into `PASS` with a scope note rather than inventing a fourth enum.

When a narrative says a structure “satisfies the code,” test the underlying rows. If one row fails, preserve the row-level failure and identify the affected combination; do not average it away.

Keep two approval layers separate. A reported factor can pass its displayed allowance while the factor remains independently unreproducible because the resisting and driving components, coefficients, or combination definition are absent. Record the displayed comparison as `PASS`, but create a distinct `REVIEW` finding for calculation-chain reproducibility. Never let the first layer silently close the second.

At approval level, aggregate open reproducibility findings by affected structure and state what evidence would close each one. A blanket satisfactory narrative cannot close an issue register whose underlying rows or inputs remain open.

## 5. Use the helper script

`tools/combo_arithmetic.py` accepts a JSON object containing signed components and returns recomputed subtotals and moments. It never emits a project verdict or reads a task answer. Use its output as working values, then make the professional judgment in the workbook with a source citation.

Example input shape:

```json
{"components":{"downward":125,"upward":40,"positive_moment":45,"negative_moment":-12},"expected":{"net_moment":33}}
```

The script's decimal output is intentionally not rounded to a status; keep the calculation visible in the workbook formula cells.

## 6. Common traps

- treating an empty cell as zero;
- comparing a stress to an allowable factor or mixing kN with kN·m;
- losing the negative sign on uplift or a negative bending moment;
- accepting a global “satisfied” sentence without checking the worst row;
- changing the rounding rule from one combination to another.

## 7. Evidence record

For every conclusion, write the source table/section and the exact observed values used. A concise process note should say what was compared (for example, “signed subtotal versus reported resultant”) rather than merely quoting a governing rule. This preserves a review trail without prescribing a single spreadsheet layout.

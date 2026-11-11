# Movement Category Controls

Use this reference after extracting reserve roll-forwards. It is designed for annual
filing packages with multiple products, properties, reserve classes, or reporting
periods.

## Preserve Source Semantics

Record printed units and signs before normalizing anything. A parenthesized value is a
signed decrease. A dash may mean zero, not applicable, or not disclosed; preserve the
source treatment until context resolves it. Keep native oil, gas, and liquids units in
separate columns and add an equivalent-unit column rather than replacing the source
values.

## Closure Is Only the First Control

For each displayed roll-forward, calculate:

```text
residual = reported ending - (reported opening + all signed movements)
```

Classify a residual as exact, rounding-sized, or substantive. Then run a separate
semantic test on every category. It is possible for a preparer to move an amount from
extensions to revisions, or from extensions to purchases, and preserve a zero residual.

## Category Evidence

Use event evidence, not labels alone:

| category | corroborating evidence | common misclassification |
| --- | --- | --- |
| production | period production or sales volume | sign reversal or unit mismatch |
| purchase | acquired interest and transaction timing | organic addition parked as acquisition |
| sale | disposed interest and closing date | production or revision parked as sale |
| extension/discovery | new proved area, reservoir, or drilling result | negative plug or revision |
| revision | new performance, economics, ownership, or technical interpretation | unexplained catch-all |
| improved recovery | approved recovery project and supporting technology | ordinary development activity |

A negative extension/discovery amount is a strong investigation signal, not an automatic
instruction to reverse the sign. First determine whether another category absorbed the
offsetting amount.

## Cross-Layer Conversion

Use the issuer's stated equivalence factor. For a geography with oil, gas, and liquids:

```text
equivalent movement = oil movement + gas movement / stated factor + liquids movement
```

Do this for every movement category, not only ending reserves. Retain unrounded results
and compare to the reported rounded equivalent amount. A match indicates that the
summary was derived consistently from the product tables; it does not prove that the
underlying category is economically correct.

When factors differ by geography, convert within geography and then sum. Applying a
portfolio factor before geography-level conversion can create a false discrepancy.

## Subset Controls

Developed and undeveloped tables are subsets of total proved reserves. Test whether a
subset narrative is directionally and quantitatively consistent with the same movement
in the total proved layer. A negative category in one subset cannot be excused merely
because total proved reserves increased.

Use opening, additions, conversions, revisions, acquisitions or disposals, and ending
balances as separate comparison fields. Conversion from undeveloped to developed should
reduce the undeveloped subset but should not change total proved reserves.

## Period Controls

Repeat the category conversion for each comparative year. Trend and reserve-replacement
claims may depend on the historical categories. When a magnitude disappears from one
category and reappears in another only at the equivalent-unit layer, the likely issue is
a summary classification swap rather than a quantity-estimation error.

## Downstream Dependency Note

Flag quantity-category exceptions for review against the discounted-cash-flow change
table. Do not assume the dollar categories can be corrected with the same ratio. Timing,
development cost, tax, and property price differences mean a property-level model or
prepared reconciliation is normally required.

## Working-Paper Minimum

For every material exception, retain:

- source values and units;
- independent arithmetic and residual;
- cross-layer comparator;
- narrative comparator;
- affected downstream disclosures;
- what is known, what is inferred, and what remains unavailable.

That record supports both a correction and a defensible decision not to overstate it.

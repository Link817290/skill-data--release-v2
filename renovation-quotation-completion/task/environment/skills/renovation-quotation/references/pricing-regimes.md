# Pricing Regimes and Loss Quantities

## Composite Work Rates

When a work-item table splits the price into direct material, auxiliary material
and labor rates for the same unit, add the numeric rate components and multiply
by the work quantity. A blank component is not a missing quote if another supplied
component is sufficient and the table's convention treats the blank as unused.
Text such as a brand or concrete specification is not a numeric rate.

Verify a representative row from each header regime before applying a formula
throughout a section. Repeated item names do not imply identical units or rates.
Keep supplied rates separate from newly proposed rates so a reviewer can recover
the original basis. Do not silently replace a scheduled quantity because a nearby
drawing dimension happens to have a similar value.

## Purchased Materials

When the table has one purchase rate and an extra-quantity field, determine whether
the extra value is an absolute quantity or a percentage. Compare dimensions and
the header's expression with the actual entries. If the extra quantity is already
calculated, add it once to the net quantity before multiplying by the unit rate.
Applying another percentage to that number charges the same loss twice.

For example, a net strip length of 8 with an explicitly calculated extra length
of 0.8 uses 8.8 chargeable units. A field explicitly expressed as a fractional
uplift of 0.10 instead uses net quantity multiplied by 1.10. These are different
representations of loss and require different formulas.

Equipment counts and installed fixture counts need their own applicability check.
Do not assume every numeric value under an inherited loss header is an additional
payable device. If its meaning is unclear, retain the source and mark the counting
decision for confirmation instead of inventing an extra unit.

## Commercial Exceptions

A negotiated lump sum can differ from a mechanical quantity-times-rate result.
Adopt an exception only when the source supplies that amount or a traceable
commercial basis. If only a misplaced number or incomplete rate exists, show the
supported computation or unresolved question without inventing approval.

Verification compares the saved line amount with the selected pricing rule using
the saved quantity, units and rate inputs. A plausible round amount is not a check.

# Scope and Quotation Closure

## Scope Before Quantity Revision

Bind each row to its room, work category and project. Distinguish floor area from
wall area, length, count and building-wide service area. A floor plan can help
identify room quantities but does not automatically describe all floors, exterior
works or the contractual measurement method. Where coverage is uncertain, preserve
the schedule and flag the specific discrepancy rather than silently redesigning
the estimate.

## Aggregation as a Dependency Graph

For every subtotal, identify the work items it owns. For every larger total,
identify whether its inputs are individual rows, section subtotals, fees or taxes.
A subtotal printed after unrelated rows need not own all preceding rows. Use source
formula references, visible grouping and category labels together to establish
scope. Do not count an individual detail again if it already flows through a
selected subtotal.

Compute leaf amounts before parent totals. Check a second independent sum over
the same adopted scope. If a detail changes, update every dependent subtotal and
total, including any per-area indicator that actually has a declared denominator.
An unrelated numeric cell beside a total is not automatically such an indicator.

## Fees, Tax and Unresolved Quotes

Separate a percentage rate, its applicable base, an explicit negotiated fee and
an unused fee row. A rate printed in a template does not establish that the charge
is payable, nor does a zero quantity establish that the rate should be applied
to a different base. Preserve explicit commercial amounts when provided and flag
ambiguous applicability without changing the contract.

For an unpriced item, identify the missing quantity, rate or agreed lump sum.
Leave a visible pending marker or an explicitly provisional assumption rather
than presenting an invented amount as agreed. If a subtotal excludes such items,
label it as a known-cost subtotal. Do not present it as the complete fixed price.
Unknown and zero are different states even when spreadsheet SUM ignores both.

Verify closure from the saved artifact: all adopted priced lines use a traceable
basis, every subtotal has one scope, repeated totals agree, and unresolved items
remain visible to the next reviewer. Keep any discretionary estimate separate
from the adopted quotation.

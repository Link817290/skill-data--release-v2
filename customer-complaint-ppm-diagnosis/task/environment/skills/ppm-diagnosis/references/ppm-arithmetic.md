# Rate arithmetic and reconciliation

For a defined population, PPM = complaints / sales * 1,000,000.
Keep full precision during calculation and round only the displayed result.

## Counts before rates

When complaints and sales are both supplied, compute the rate from those values.
Compare it with the source's reported rate, including whether the cell is a
formula or a manually entered constant. Explain a discrepancy; do not reproduce
an inconsistent rate merely because it is already formatted in the source.

If only a rounded rate and a matching denominator exist, any reconstructed count
is an estimate. Identify it as such and assess the rounding interval before
treating a rounded integer as an observed count. Without a matching denominator,
the count cannot be recovered from the rate alone.

## Combining observations

For disjoint populations, overall PPM = sum(complaints) / sum(sales) * 1,000,000.
Equivalently, weight each population's rate by its sales, not by its complaints.
The same rule applies when combining time periods with unequal sales volumes.

Do not sum overlapping populations or average rates without their denominators.
Reconcile both numerator and denominator before interpreting a mismatch.

## Missing and zero exposure

A missing sales or complaint cell is not an observed zero. A zero denominator
makes the rate undefined even when the complaint count is zero. Keep any known
count visible, flag the undefined rate and explain its effect on aggregate scope.
Periods without observed exposure must not silently become zero-rate periods.

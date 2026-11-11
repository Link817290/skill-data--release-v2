# Periods and methods

## Separate schedule time from report time

An asset's service year is not necessarily a calendar year. Build a service-age
index from the documented start convention, then map each calendar month to
the applicable service-year amount. A calendar year can contain portions of
two different service years under an accelerated method.

Represent acquisition, service start and reporting cutoff on a common timeline.
Establish the interval convention before aggregating periods. Use the supplied
date granularity and distinguish a business date from a display label. The
assignment determines whether service starts at acquisition, commissioning or
another established event.

Distinguish these aggregates:

- Calendar-year plan: expense for all modeled months in the reporting year.
- Year-to-date expense: expense from the start of that year through the cutoff.
- Accumulated depreciation: expense since the asset's depreciation start,
  including established prior-period amounts.

Do not include future months in year-to-date results. Do not erase prior-period
depreciation when selecting another reporting year. A plan that uses forecast
workload is different from an actual-workload expense report; label and source
those quantities according to the business request.

## Preserve method meaning

For each supported method, identify its allocation basis, rate, state carried
between periods and stopping rule. Express units alongside intermediate
quantities so that the calculation has an economic interpretation. Distinguish
actual activity from forecast activity and a period observation from a
cumulative measurement.

Treat a change in accounting assumptions as a business event with an effective
period and a stated treatment of history. Numerical stabilization and error
handling should preserve the business definition. Derive bounds from that
definition rather than treating computational convenience as a new convention.

## Keep calculation capacity explicit

Determine the supported horizon and trace it through the schedule and its
consumers. Keep that horizon a declared modeling assumption. Extending storage
or formula ranges does not authorize inventing additional economic assumptions.

When checking a method, compare the per-period sequence with an independent
calculation, rather than only comparing its lifetime sum. Two schedules can
fully allocate the same basis while charging different periods incorrectly.


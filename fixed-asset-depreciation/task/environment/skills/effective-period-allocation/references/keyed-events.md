# Keyed events

## Define record identity and grain

Use an asset key to associate register data, opening state and change records.
A worksheet row number is a location, not a persistent business identity.
Determine whether a source allows one annual plan row per asset, multiple
effective-dated events, or another grain before choosing lookup logic.

Establish cardinality at the declared grain. Repetition can be meaningful in an
event table while representing a different relationship in a register. Use that
relationship to choose joins and aggregation, rather than treating all tables
as interchangeable lookup lists.

Keep business identity independent of worksheet layout. Establish how incomplete
source records are represented and resolve uncertainty before presenting an
allocation as complete.

## Resolve time-dependent ownership

Establish the opening owner and the event's effective convention. A change may
apply from the start of its month, from its exact date, or from the next period.
Do not infer proration or event precedence solely from a date's display format.

Define the state transition represented by each business event and the meaning
of periods without a new event. Keep the source representation separate from the
resolved state used by the reporting layer.

When switching reporting years, establish the next opening ownership state and
select the matching year's events. Do not silently reuse a prior year's monthly
plan or retroactively replace history with the new year's opening owner.

## Keep configuration interfaces consistent

Treat configuration, data entry and calculation as interfaces to the same
business schema. Their supported scope should agree. Choose a representation
that preserves the source business meaning through each interface.

Keep unresolved assignment visible and traceable to its source. Use the existing
workbook's conventions to distinguish incomplete data from established ownership.


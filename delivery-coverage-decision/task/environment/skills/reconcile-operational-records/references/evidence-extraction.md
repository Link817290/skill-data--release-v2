# Extract rules without inventing authority

## Distinguish the document's role

A quotation defines commercial alternatives and what is included. A service notice defines obligations and dates. An equipment log can describe availability without changing contracted service promises. A field guide defines how to interpret a value, not whether the business approves it. Record the relevant role before combining numbers from different documents.

Use a compact rule ledger with: evidence location, entity/resource, date and period scope, operation (replace/add/override), displayed value and unit, normalized value, and any unresolved interpretation. Preserve document identifiers and table row labels instead of relying only on page numbers, which may change when Word is rendered.

A revision to one site's morning staffing does not revise its afternoon staffing or its refrigeration quota. An effective date is not automatically the event-reception date. If authority is ambiguous, retain the alternative interpretations and identify whether they affect the recommendation; do not choose the convenient value silently.

## Read tables as logical cells

Check vertical merges, horizontal spans, repeated headers, units in captions and notes below the table. Blank XML cells can inherit a visible merged value. Conversely, a genuinely blank commercial field is not zero. Validate at least a representative merged row against the rendered page before bulk extraction.

Determine the payable unit before summing prices. If one quoted package spans several component rows, propagate its package identifier for joins but count its total price once. Store component capacities separately from package price. Do not deduplicate distinct packages just because their amounts match.

## Protect joins and populations

Write down the intended cardinality before each join: one order to many events, one selected revision to one current state, one station-period to multiple independent resource types. Check unmatched keys and multiplicative row growth after the join. Missing resource records require a business interpretation; filling them with zero can turn missing information into an invented shutdown.

Reconcile at each grain separately. Raw deliveries partition into retained message groups, duplicate deliveries and message-conflict groups. Entities partition into active, cancelled and unresolved states according to the actual contract. A network-ineligible active order remains in demand if the business denominator includes it. Avoid adding counts from different grains into one reconciliation equation.

## Finish with a small trace

Trace one normal record and each observed exception class from its source identifier to its governing state and downstream inclusion. A trace should explain the governing evidence and action; it need not repeat the entire source table. This makes later disagreements about counts resolvable without reconstructing all joins manually.

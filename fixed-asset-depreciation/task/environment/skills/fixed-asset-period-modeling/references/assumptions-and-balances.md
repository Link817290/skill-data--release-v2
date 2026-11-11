# Assumptions and balances

## Resolve an assumption once

Record each driver's source, unit, scope and authority. Where multiple sources
can supply a driver, establish their precedence from the business contract.
Resolve an effective value in a traceable layer before downstream calculations.

Model configuration as data with an explicit schema and relationship to the
register. Preserve the distinction between a source fact, a permitted default
and an unresolved assumption. Report uncertainty at the layer where it arises
rather than letting a downstream result imply unsupported certainty.

## Establish opening facts

Opening facts establish the state from which the report period evolves. Keep
their identity, effective period and provenance separate from current-period
activity. A model-derived history and an imported accounting balance need an
explicit reconciliation rule if both are present.

Define a balance bridge using only supported business events. Classify any
unexplained difference before adjusting the calculation. Do not introduce
additional accounting operations solely to make an identity balance.

Changing the report year is not sufficient to perform a business rollforward.
Where opening facts and ownership state are maintained by year, establish the
new year's opening from the appropriate closing facts and review any new events.

## Reconcile different quantities independently

For the supported accounting scope, connect opening accumulation, period charges
and closing accumulation; then reconcile cost, accumulated depreciation and
carrying amount. Review each asset before relying on the portfolio total.

Review grouped totals against their declared population and reporting scope.
Distinguish a presentation subset from a complete portfolio reconciliation.

Use both economic checks and bookkeeping identities. A schedule can satisfy
`cost = accumulated depreciation + carrying amount` even when the expense is
wrong, because all three results share the same faulty driver.


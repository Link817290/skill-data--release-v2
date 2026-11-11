# Compare investments without conflating priorities

## Build comparable metrics

Compare complete feasible alternatives on the same demand population and scenario definitions. Record unavailable or uncomputed results separately from zero. Apply exact currency conversions before budget filtering, and respect whether the quote is a package or independently purchasable components.

For scenario robustness, calculate the worst value separately for each metric. The minimum priority fulfillment can occur in a different scenario from minimum overall fulfillment. Do not invent occurrence probabilities to compute an expected outcome. If probabilities are supplied, check their interpretation before aggregation.

The business objective order comes from the task's business evidence. Presentation emphasis and the number of checks performed are not coefficients in the investment objective. Where the business material leaves priorities open, state an interpretation, show meaningful alternatives and support the recommendation rather than claiming a hidden unique optimum.

Compare the adopted explanation with the actual decision rule, not only the selected option. Two conflicting priority orders can happen to select the same option on one dataset; that coincidence does not validate a false explanation. Separate absent optional metadata from an explicit contradiction. Check the meaning of an equivalent explanation rather than requiring private enum names or wording, and attribute a contradiction once to the affected decision claim.

## Distinguish dominance from selection

An alternative dominates another only when it is at least as good on every declared comparison metric and strictly better on one. A lexicographic winner can remain worse on lower-priority metrics. For example, one option can protect more priority items while another serves more total items at lower cost. Report that trade-off instead of calling the winner universally best.

If a new service floor is being considered, label it as a proposed condition and recompute feasibility under it. Do not quietly use it to change the approved recommendation. Distinguish an investment tie-break from allocation priorities within the same investment.

## Use the comparison helper

`scripts/compare_alternatives.py` takes a UTF-8 CSV of already verified per-alternative metrics. Numeric columns are finite decimal values; there is no unit conversion. Supply metrics in business priority order:

```bash
python scripts/compare_alternatives.py alternatives.csv --id alternative --objective max:protected --objective max:fulfilled --objective min:cost --cost-column cost --budget 40
```

The budget and cost column must share a unit. Output includes budget exclusions, ordered tie groups, all tied winners, and the Pareto frontier under the supplied objective metrics. Input order is not an implicit tie-break; identifiers only make output order deterministic. Add a documented numeric tie-break column if it is genuinely part of the rule. For a nonnumeric business tie-break, resolve the reported tie explicitly outside this numeric helper.

The helper rejects duplicate identifiers, missing fields, nonfinite metrics, and a negative budget or cost. It cannot certify that the aggregates came from legal routes or optimal assignments. It performs no scenario aggregation and has no preference model beyond the ordered metrics supplied. If all alternatives exceed the budget, it reports no winner.

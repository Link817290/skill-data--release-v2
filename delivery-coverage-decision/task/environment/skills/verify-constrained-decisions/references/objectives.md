# Allocation and objective proofs

Represent each independently limited resource explicitly. A small count of accepted jobs can still exceed a time budget; spare processing time cannot replace a missing refrigerated slot.

Eligibility and allocation are distinct. Eligibility asks whether an entity could use a resource under time, location and capability rules. Allocation chooses among eligible alternatives under shared limits. Explain an unassigned entity using the distinction rather than labeling every miss as geographic exclusion.

For lexicographic objectives, optimize the first criterion, fix its optimum and proceed to the next. Weighted sums require a mathematically justified dominance bound; arbitrary large weights can change the intended order.

Keep nested decision levels distinct. Within-plan dispatch can optimize priority fulfillment, total fulfillment and travel time, while across-plan selection also considers purchase cost. A reviewer should not insert the investment criterion into the dispatch problem or remove it from the investment comparison. Explain both levels separately in the report.

An independent optimality check can search for an improving feasible solution at each level: improve the first objective; hold it fixed and improve the second; then hold both fixed and improve the third. Proven infeasibility of every improvement establishes optimality within the model. A timeout, solver error or missing bound does not.

Verify routes using the declared direction of each physical segment. A closure on a physical segment may remove both traversal directions; deleting a single directed arc is a different restriction. Recompute path cost from legal segments rather than trusting a supplied total.

Equivalent optimum assignments are valid. Positive controls should include at least one genuinely different equal optimum when nonuniqueness is material. Keep exact-key serialization checks confined to an explicit interface contract or an internal reference implementation.

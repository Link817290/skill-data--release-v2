# Formulation and legitimate decomposition

## Keep eligibility separate from shared resource choice

Let x(i,s) indicate whether demand item i is assigned to facility s. Create it only for eligible pairs, or force ineligible pairs to zero. A typical indivisible assignment model includes:

- Sum over s of x(i,s) <= 1 for each item.
- Sum over i of handling(i) * x(i,s) <= available_minutes(s).
- Sum over refrigerated items of x(i,s) <= refrigerated_slots(s).

These examples define different resource dimensions, not interchangeable counts. Include date, period and scenario keys in the resource indices whenever their limits are independent. Use equality for mandatory service only if the business rules actually require it; otherwise an infeasible mandatory model can obscure legitimate unserved demand.

The exact model depends on the operation. Add vehicle routing, return travel, shift continuity or replenishment only when required or supported by the task. A shortest-path assignment is not a multi-stop vehicle-route schedule.

## Split only where constraints permit

Independent date/period problems can be solved separately if no capacity, decision or state carries between them. A global daily quota, shared vehicle fleet, inventory balance or cross-period investment choice couples those problems. Check the constraint graph before decomposition.

For additive lexicographic objectives over independent subproblems, optimizing each subproblem at each priority level establishes the corresponding aggregate optimum. This argument fails when the aggregate objective is a minimum across periods or when resources can be borrowed. Document the decomposition argument alongside certificates rather than assuming more subproblems imply a stronger proof.

## Inspect a tiny instance first

Use two or three items to verify the coefficients. For example, with six handling minutes, two ordinary items using three minutes each can be served; a refrigerated item using four minutes also requires an independent cold slot. Removing its cold slot must make it ineligible or unassignable even while handling time remains. The model should not count one order as one minute.

If priority items come first, a feasible allocation with more total items may still be inferior. Verify the first objective, then fix its optimal value before optimizing the next. For floating objectives, declare the tolerance and justify how it interacts with feasibility; integer counts should not need arbitrary floating slack.

## Read solver outcomes correctly

Store status, incumbent objective, bound/gap, tolerances and the objective values fixed at previous levels. A feasible incumbent is useful but is not an optimality certificate. At a later level, fixing an unproven incumbent from an earlier level can exclude the true lexicographic optimum. Preserve that uncertainty instead of labeling the final result optimal.

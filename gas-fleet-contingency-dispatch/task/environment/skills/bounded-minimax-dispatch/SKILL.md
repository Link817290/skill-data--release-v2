---
name: bounded-minimax-dispatch
description: Implement a deterministic minimax dispatch allocator with capacity, state-transition, and balance constraints. Use for multi-unit redistribution where each step must be feasible, reproducible, and independently certifiable without an optimization package.
---

# Bounded Minimax Dispatch

At each time step, allocate a fleet target across available units while minimizing the maximum
capacity utilization. Keep constraint construction separate from target construction so either can
be audited independently.

## Derive a scenario-step adjustment envelope

When only plant-aggregate historical observations are available, call the result a scenario-step
adjustment envelope, not a physical ramp rate. For each plant:

1. convert the selected aggregate series to MW;
2. calculate absolute consecutive changes;
3. divide each change by the currently dispatchable plant capacity;
4. take the nearest-rank 90th percentile, where rank is `ceil(0.90 * n)` in ascending order;
5. multiply each unit capacity by that plant fraction to obtain its symmetric per-step limit.

This preserves a visible relationship to observed variability without claiming sub-hourly dynamics
from daily records. If fewer than two observations or no usable current capacity exists, declare the
envelope unavailable instead of inventing a default.

## Build a dimensionless stress target

To apply a historical shape to a current fleet without treating the levels as contemporaneous,
normalize the combined historical series:

`stress_t = (historical_t - historical_min) / (historical_max - historical_min)`

For a nonconstant series, map stress monotonically into a declared current operating band. Choose
the lower and upper fractions for the decision context and expose both as scenario assumptions:

`target_t = pre_event_output * (lower_fraction + (upper_fraction - lower_fraction) * stress_t)`

Require `0 <= lower_fraction < upper_fraction <= 1` for a screen that does not assume output above
the observed pre-event fleet level. Preserve the band in the model record and never present the
resulting target as measured demand. Reject a constant source series unless another visible
normalization rule is supplied.

## Construct causal bounds

For each remaining unit `i` at step `t`, with prior simulated output `p_prev`, capacity `c`, and
step limit `d`:

`lower_i = max(0, p_prev - d)`

`upper_i = min(c, p_prev + d)`

For the lost unit, both bounds remain zero. The first simulated step starts from the post-event
state; later steps start from the immediately preceding simulated output, never from the original
snapshot.

Clamp the requested total to the aggregate feasible interval:

`served_target = min(max(target, sum(lower)), sum(upper))`

The signed tracking residual is `target - sum(output)`.

## Solve the minimax allocation

For feasible total `T`, the allocation minimizing the maximum utilization has the form:

`p_i(lambda) = clip(lambda * c_i, lower_i, upper_i)`

Find `lambda` by bisection because `sum(p_i(lambda))` is monotone. Search a bracket beginning at
zero and extending beyond the largest `upper_i / c_i`; 80 iterations is ample for decimal MW data.
After bisection, distribute any floating residual only over units with remaining slack, in exact
identifier order. This makes the result deterministic.

Certificate checks for each step are:

- each output lies within its lower and upper bound;
- the delivered sum equals the clamped target within numerical tolerance;
- the reported residual equals requested target minus delivered sum;
- no alternative common-utilization level can meet the same target with a smaller maximum ratio;
- tie handling is independent of input row order.

An infeasible requested target is not an optimizer failure. Preserve the binding aggregate bound,
the residual, and the affected step in the result.

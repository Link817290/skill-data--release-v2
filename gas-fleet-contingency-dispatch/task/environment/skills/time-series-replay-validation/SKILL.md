---
name: time-series-replay-validation
description: Validate causal multi-unit simulation traces through state linkage, conservation, constraint, source, and decision invariants. Use when a generated time series must support an operational recommendation rather than merely look plausible.
---

# Time-Series Replay Validation

A professional trace is an executable certificate. Validate relationships across rows instead of
looking only at headline metrics or the final step.

## Choose trace grain

Use one row per time step per participating unit when the decision depends on unit constraints. Each
row should retain the source observation identity, step index, unit identity, prior state, bounds,
command, simulated state, and repeated step aggregates. Keep the lost unit in every step with zero
state. Sort deterministically by time and exact unit identifier.

## Check causal linkage

For each unit:

- at the first step, prior state equals the declared post-event initial state;
- at later steps, prior state equals that unit's simulated state at the preceding step;
- step bounds are calculated from that prior state, not from a future target or observation;
- simulated state equals the feasible command and stays inside capacity.

A trace can satisfy every row-local bound while still be noncausal if each row resets from the
snapshot. Explicitly test the cross-step link.

## Check aggregate conservation

At every step, independently sum unit outputs and compare it with the repeated aggregate. Recompute
the residual as target minus that sum. All rows for the same step must agree on the source values,
target, aggregate, residual, and reachability label.

Reject these cheap substitutes:

- one aggregate row standing in for unit constraints;
- repeated copies of a single step;
- a correct final metric paired with inconsistent row arithmetic;
- a status label without the quantities that establish it;
- hard-coded artifacts that a clean rerun cannot reproduce.

## Reconcile headline metrics

Derive counts, extrema, sums, and binding units from the trace, then compare them with the report.
At minimum, reconcile step count, unit count, feasible-step count, maximum absolute residual, maximum
utilization, selected loss, initial post-event output, and remaining ceiling.

## Bound the decision

Use a conditional decision when historic shape and current state have different timestamps or when
daily peak aggregates stand in for operating dynamics. A feasible simulation supports a statement
that the declared scenario is feasible; it does not prove actual reserve delivery, stability,
transmission adequacy, fuel availability, or sub-hourly ramp performance.

An infeasible step supports rejection of the tested scenario. It does not by itself identify a
mechanical cause. List limitations as concrete evidence boundaries, including time separation,
aggregation mismatch, temporal resolution, and unmodelled system constraints.

## Clean-room reproduction

Copy only the submitted program and immutable source records into a clean directory, run the
program there, and compare parsed JSON objects plus canonical CSV rows. Ignore key order and benign
float formatting, but require values, row identity, and relationships to match. This catches hidden
inputs and current-directory assumptions without rewarding a particular writing style.

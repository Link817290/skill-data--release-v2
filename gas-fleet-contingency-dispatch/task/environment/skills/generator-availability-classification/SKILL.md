---
name: generator-availability-classification
description: Classify generating-unit availability and select credible single-unit contingencies from operational snapshots. Use when nameplate capacity, present output, ownership or type, and free-text outage notes constrain dispatch eligibility.
---

# Generator Availability Classification

Build a unit register before constructing an optimization set. Classification is a source-bound
decision: capacity, output, type, scope, and note must all refer to the same snapshot row.

## Establish scope before status

Select an entity only when its exact identifier and type place it in the requested fleet. Prefix
matching is acceptable only when the scope defines a plant family and the retained register exposes
the exact source name. Avoid near matches from another owner, technology, test program, or aggregate
subtotal.

Every in-scope row belongs in the register even when it cannot be dispatched. Silent omission loses
the evidence needed to distinguish an outage from a parser failure.

## Apply availability precedence

Use this conservative precedence:

1. Missing or nonnumeric nameplate capacity means `not dispatchable`; output may still be observed,
   but no headroom can be inferred.
2. A full unavailability note such as maintenance, overhaul, failure, planned shutdown,
   environmental shutdown, or contractual restriction means `not dispatchable` for upward action.
3. A partial restriction means `derated`; do not infer the unrestricted nameplate as usable
   headroom. In the absence of a stated derated maximum, current output is the defensible ceiling.
4. A numeric capacity with no restrictive note is `dispatchable`. Zero current output does not by
   itself prove an outage; it may be available but not committed.

Preserve the source note as an enum-like value. Report an observed blank separately from the derived
classification reason.

## Select a single-unit loss

A credible online N-1 event removes one currently producing, dispatchable unit. For a deterministic
screening case, choose the unit with the greatest current net output; break a numerical tie by exact
identifier. This represents the largest observed instantaneous loss, not the largest nameplate unit
and not an already unavailable unit.

The lost quantity is the observed pre-event output. After the event, enforce zero output and zero
upper bound for that unit at every simulated step. Keep it in the trace so the event cannot vanish
from aggregate arithmetic.

## Close the register

Check these identities before simulation:

- in-scope count = dispatchable + derated + not-dispatchable count;
- pre-event dispatchable output = sum of the included snapshot outputs;
- post-event initial output = pre-event output minus the selected loss;
- remaining nameplate ceiling excludes the lost unit and every unavailable unit;
- each headroom term is bounded below by zero.

Do not describe the result as system-wide N-1 security. A scoped fleet test says only whether the
modelled fleet can cover the selected loss under the declared scenario.

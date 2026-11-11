# Algorithm State Closure

Use this procedure when a scientific correction changes any part of an iterative
or distributed algorithm.

## Reconstruct the executable transition

Write one row for each role:

| Role | State read | Operation | State written | Justification |
| --- | --- | --- | --- | --- |
| Initialization | | | | |
| Candidate generation | | | | |
| Information exchange | | | | |
| Temporary aggregation | | | | |
| Optimization or update | | | | |
| Pruning or projection | | | | |
| State advancement | | | | |
| Stopping test | | | | |
| Final recovery | | | | |

Mark which rows must change because of the corrected model or theorem. Preserve
all other rows unless a dependency makes that impossible, and document the
dependency when it does.

Count proposals as well as states. If multiple workers each produce a proposal,
record whether the established transition unions the whole batch, ranks it, or
selects one member. Preserve that cardinality and aggregation topology unless the
revision explicitly changes them. A global argmax is not an equivalent rewrite
of a per-worker batch.

Initialization is part of the algorithm, not disposable setup prose. Preserve a
concrete feasible seed construction and its invariants unless a required change
makes it invalid; "initialize a feasible point" is not an equivalent replacement.

## Guard against attractive but unsupported redesigns

An existence result does not itself provide an algorithm for selecting the
promised representation. Do not insert a new compression, ranking, projection,
or top-k operator merely because it would realize the theorem's conclusion.
Repair the manuscript's established candidate, pruning, and stopping mechanism
unless the brief explicitly requests a replacement and the evidence supports it.

Keep these roles separate:

- a candidate budget limits what is proposed or retained;
- a pruning threshold removes negligible state;
- a convergence tolerance measures progress;
- a loop guard enforces a structural or feasibility condition;
- a final recovery step maps the relaxed state back to the original problem.

Two thresholds with similar notation are not interchangeable. A structural
support bound is not automatically a pruning rule. A distributed claim also
requires an explicit account of each node's local input, received information,
reported output, and the work that remains centralized.

## Closure checks

Before accepting the edit, simulate one iteration on paper. Confirm that every
read state has been initialized, every temporary set has a defined source, every
index and dimension agrees with the formulation, every updated state advances,
and the stopping test refers to the intended quantities. Then verify that the
pseudocode, equations, prose description, complexity discussion, and output all
describe the same transition.

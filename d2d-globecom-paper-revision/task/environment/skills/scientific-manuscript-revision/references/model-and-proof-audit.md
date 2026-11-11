# Model and Proof Audit

Use this procedure when a manuscript changes a formulation, relaxation,
representation, theorem, or guarantee.

## Separate formulation layers

Create a table for the original problem, each relaxation or reduction, each
algorithmic subproblem, and final recovery. For every layer record:

- variables and dimensions;
- domain and feasibility conditions;
- equalities and inequalities;
- objective and any positivity or boundary assumptions;
- which implication connects the layer to the next one.

An equality that holds at an optimum of a relaxed allocation does not
automatically replace an inequality in the original discrete formulation. A
guarantee for a continuous problem does not automatically survive rounding,
association recovery, or re-optimization. State these boundaries explicitly.
The phrase "make the relaxation and algorithm consistent" normally closes those
two downstream layers; it is not permission to strengthen an upstream discrete
feasible set. Preserve an original idling or slack allowance unless the brief
separately requires and justifies changing it.
If the revision request names the relaxation and the algorithm but does not name
the original constraint as defective, freeze the original relation and verify
that final recovery still solves that preserved problem.

## Audit dimensional arguments

Identify the object whose convex combination is actually being optimized. Do
not count auxiliary coordinates that the objective sees only through a lower
dimensional image. Conversely, do not discard coordinates merely because the
desired result is smaller.

For each support or sparsity claim, verify:

1. the ambient set and its dimension;
2. whether the optimizer lies in the interior, on a boundary, or on an exposed
   face;
3. the theorem being used and every condition it requires;
4. whether the conclusion is existence, uniqueness, or a property of every
   optimizer;
5. whether the old result was false, loose, or valid under different assumptions.

If feasible points depend on internal per-mode decisions, represent the
per-mode feasible region rather than pretending that each mode contributes a
single fixed vector. Show that any combination or aggregation step remains
feasible.

## Close the proof-to-claim chain

Trace the corrected result into every place that depends on it: proposition,
restricted problem, complexity statement, algorithm budget, abstract,
contributions, and conclusion. A numeral replacement without a corrected
representation and proof earns no confidence.

Keep claim strength exact. Distinguish global optimum, optimum of a relaxation,
subproblem optimum, stationary point, local optimum, existence of a sparse
representative, and empirical proximity. Record any unproved transfer as an
open limitation rather than smoothing it away in prose.

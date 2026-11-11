---
name: scientific-manuscript-revision
description: Revise an existing technical manuscript when the scientific framing, model, proof, algorithm, or evidence chain needs correction. Preserve unaffected content and do not invent experiments, metadata, or unsupported claims.
---

# Scientific Manuscript Revision

Use this skill for a technically substantive revision of an existing paper. The
goal is a minimum correct scientific delta, not a replacement paper that merely
looks coherent.

## Route the work

Read the references that match the defect before editing:

- Read [model-and-proof-audit.md](references/model-and-proof-audit.md) when a
  formulation, relaxation, dimensional argument, theorem, or guarantee changes.
- Read [algorithm-state-closure.md](references/algorithm-state-closure.md) when a
  theorem or model correction must propagate through an iterative algorithm.
- Read [evidence-and-preservation.md](references/evidence-and-preservation.md)
  before changing experiments, claims, citations, metadata, or unrelated prose.

For a revision that spans model, proof, algorithm, and results, read all three.

## Core workflow

1. Preserve the received source and inventory the paper's claims, definitions,
   equations, algorithm states, figures, values, citations, and metadata.
2. Build a change ledger. Mark each unit `preserve`, `modify`, `replace`,
   `remove`, or `unresolved`, and attach every planned edit to a stated defect or
   a necessary downstream consequence.
3. Reconstruct the scientific chain before rewriting prose:

   `problem -> assumptions -> variables -> feasible set -> objective -> result -> algorithm -> evidence -> claim`

4. Correct the earliest defective link. Propagate only consequences that are
   logically required. Keep the original formulation distinct from any relaxed,
   reduced, projected, or recovered formulation. If a brief asks for consistency
   between a relaxation and its algorithm, treat that as no authorization to
   strengthen the original discrete constraints.
5. Reconstruct the adopted algorithm as an executable state transition. Check
   initialization, proposal generation, information exchange, temporary state,
   optimization, pruning, advancement, stopping, and final recovery.
6. Preserve every unaffected scientific unit. A cleaner notation, shorter proof,
   or fashionable alternative algorithm is not sufficient reason to alter it.
7. Keep evidence strength aligned with available assets. Existing figures cannot
   validate a materially changed implementation without a new run.
8. Build the paper and audit the final PDF, then reconcile every edit against the
   change ledger. Leave unresolved technical or evidentiary gaps explicit.

## Non-negotiable boundaries

- Do not infer authors, affiliations, funding, experimental values, runtimes, or
  citations from a reference answer or from plausible convention.
- Do not turn a property of a relaxation into a constraint of the original
  discrete problem without a proof that licenses that propagation.
- When a brief asks to make a relaxation and its algorithm consistent, treat
  that wording as no authorization to rewrite the original discrete feasible
  set. Preserve the original relation unless the brief separately identifies it
  as defective.
- Do not turn an existence theorem into a new executable operator unless the
  requested revision and available evidence support that design change.
- Do not silently swap the roles of pruning thresholds, convergence tolerances,
  candidate budgets, or stopping guards.
- Preserve the multiplicity and topology of distributed reports. Do not collapse
  a per-worker proposal batch into one globally selected proposal, or replace a
  concrete feasible seed family with generic initialization, unless the
  requested correction proves that replacement necessary.
- Do not claim global optimality when the derivation supports only a relaxed,
  local, stationary, heuristic, or empirical result.

Report compilation, mathematical validation, algorithmic closure, evidence
traceability, and metadata confirmation as separate handoff results. A readable
PDF by itself establishes none of the other four.

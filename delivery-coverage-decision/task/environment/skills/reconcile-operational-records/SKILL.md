---
name: reconcile-operational-records
description: Reconstruct current operational state from revisioned exports and changing business documents before planning or capacity analysis.
---

# Reconcile operational records

Use this workflow when event arrival order, document revisions, units, or coordinate conventions can change the population or constraints. It does not choose an investment or prescribe an output schema.

Establish the business grain before joining records. A message, an order, a location and a resource interval are different entities. Retain the identifiers needed to explain exclusions and superseded states.

Read [revision semantics](references/revisions.md) when reconstructing state. Use `scripts/reconcile_events.py` only after confirming that its whole-record revision model matches the supplied contract; patch-level updates require a different reconstruction.

Read [units and document precedence](references/units-and-precedence.md) when extracting capacities, prices or spatial parameters. Preserve the human-facing units and convert once into explicit computational units. Keep an inspectable rule ledger with effective scope and evidence identifiers.

For mixed Word tables and exports, read [evidence extraction](references/evidence-extraction.md): it explains commercial grain, merged cells, scoped rules and cross-file joins. For proximity or service-network calculations, read [spatial interpretation](references/spatial-interpretation.md) before deriving eligibility. Neither reference supplies a local policy or a task answer.

Before running the event helper, read its [input contract and usage](references/script-contract.md). Its conflict semantics are intentionally conservative; transport metadata differences and patch events require explicit normalization or another implementation.

Before analysis, reconcile the raw population to active, cancelled and unresolved records. A valid request that cannot be served remains demand unless the business definition says otherwise. Distinguish unknown data from a genuine zero resource allocation.

Do not infer a conflict-resolution policy merely to obtain a clean table. Use the stated policy, retain the unresolved cases, and identify any decision that depends on them.

Hand off a reconciled entity population, an exception ledger and a scoped rule ledger to downstream analysis. These can be sheets or in-memory tables when separate files would duplicate the user's deliverables. Preserve enough lineage to reproduce the result without distributing redundant exports.

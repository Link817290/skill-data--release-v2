---
name: affine-orbit-classification
description: Use when reconstructing periodic site orbits, stabilizers, affine-operation closure, and group invariants from the ordered symmetry actions supplied in a CIF.
license: Custom
metadata:
  role: symmetry-domain-procedure
---

# Affine orbit and group classification

## Scope and order

Apply this method after token extraction and before formula reconciliation. It uses only the supplied ordered actions. A space-group label is metadata, not a replacement for the operation list.

## Parse an operation as an action

Represent each expression as `r' = W r + t`:

1. Split the three comma-separated components without discarding empty or malformed components.
2. Parse each signed variable term into one integer coefficient in the `x,y,z` columns.
3. Parse the constant part as a rational translation.
4. Retain the raw expression and source line beside the integer matrix `W` and translation `t`.

String substitution is unsafe for coupled terms such as `-x+y`; matrix arithmetic is deterministic and exposes a mistaken coefficient. Keep translations unreduced in the parsed action, and use modulo-one translations only for equality on the periodic cell.

## Compose and close the supplied set

For an ordered pair `(g,h)`, compute `g(h(r))` by matrix multiplication and affine translation composition. Canonicalize the result by reducing only its translation modulo integer lattice shifts. Map the canonical result to the supplied operation identifier. Record every ordered pair, its target identifier or `null`, the pair count, and an explicit unmatched list. A missing operation, incomplete loop, or unmatched pair yields `unknown` or `conflict` according to whether evidence is absent or contradictory.

Retain the identity action if supplied and identify it by its canonical matrix and zero translation, never by its position in a familiar table. This identity is the reference for operation orders and stabilizer counts.

## Group invariants

When an identity and a closed operation list are available, derive these independent checks:

* The determinant of each `W`, retained per operation and in a class histogram for `-1`, `0`, `1`, and other values.
* The least positive power of each operation that returns to the identity modulo lattice translations. Search only through a finite bound justified by the supplied operation count; unresolved powers remain `unknown`.
* A fixed-site profile: for each operation, count how many derived representative sites it stabilizes.
* An order histogram and a deterministic `group_signature` containing operation count, determinant classes, order histogram, and fixed-site histogram.

The group assessment is `supported` only when the operation loop is complete, all ordered compositions resolve, an identity exists, and every operation order resolves. Otherwise carry `conflict` or `unknown` with the failed check visible. These invariants are evidence of the supplied action, not a lookup of a conventional group.

## Build periodic sites

Treat every atom row as a candidate. Two rows belong to one site when one supplied operation maps one coordinate to the other modulo one within a tolerance justified by the least precise coordinate token. Use a union-find or an equivalent transitive grouping so that a chain of equivalent rows cannot be split. Rows at one coordinate remain one site even when element or occupancy tokens differ. Preserve all labels and one-based source rows; select the first source row as representative under the declared order.

For each representative, apply every operation twice in concept: retain the unreduced affine coordinate for audit, and reduce it modulo one for comparisons. Count distinct reduced images for `orbit_size`. Count operations whose reduced image returns to the representative for `stabilizer_order`. Record the matched source rows for every operation, including operations that do not stabilize the representative.

Check the orbit-stabilizer relation against the supplied operation count. An identity-only stabilizer is `general`; a larger stabilizer is `special`; a missing operation set, unresolved coordinate, or failed closure is `unknown`. Optional multiplicity or Wyckoff fields are compared with the derived orbit size and retained even when they conflict.

## Evidence contract

At record level keep `source.affine_operations` in source order with `id`, `raw`, `source_line`, `matrix`, and `translation`. Keep the ordered composition witness under `source.operation_composition` with `status`, `pair_count`, `composition_map`, and `unmatched_pairs`. At site level keep an `operation_trace` with the operation id, raw text, source line, unreduced and reduced coordinates, stabilizer boolean, and matched source rows, plus the complete operation-id list and coordinate tolerance.

At group level keep `operation_group` with the per-operation determinant and order inventories, fixed-site profile, group signature, status, and evidence identifiers. Do not replace these arrays with a prose statement or a single group label.

Use the following compact mapping when the report is large: one list item per supplied operation, one string key `left_id|right_id` per ordered composition pair, and one trace item per operation for each representative site.  The compact mapping is still complete; omit no operation merely because its image is not a stabilizer.  Finish the source and trace arrays before writing the group signature so that a missing target or trace cannot be hidden by a correct-looking count.

## Repair and transfer

If a parser correction changes a transformed coordinate, recompute its site grouping, stabilizer, closure product, fixed-site profile, operation orders, group signature, and all downstream occupancy totals. This procedure transfers to site-symmetry, periodic-orbit, and affine-action audits in other crystallographic records.

## Numerical and algorithmic details

Use exact rational arithmetic for translations and source decimals whenever practical. For a decimal with a standard uncertainty, the uncertainty does not become a second coordinate; it determines how conservative the comparison tolerance should be. A periodic difference is close when it differs from an integer by no more than that tolerance, including across the zero/one boundary.

The following order of operations avoids hidden dependencies:

1. Parse and validate all actions.
2. Build a canonical action key `(W, t mod 1)` for closure lookup.
3. Compute the full ordered composition map.
4. Group atom rows under the actions.
5. Build every representative trace.
6. Derive stabilizers, fixed-site counts, and operation orders from those traces and the composition map.
7. Recompute the group signature and only then assign its status.

For operation order, start with the identity and repeatedly compose the candidate on a fixed side. Stop at the first canonical identity key. A missing identity or a bound exceeded without a return is an unresolved order, not evidence that the operation has infinite order. The supplied finite action set is the only bound source; do not import a conventional order from a label.

For fixed-site profiling, count representative stabilizations, not every generated atom image. This makes the profile independent of how many equivalent rows happen to be listed. Keep both the per-operation map and the histogram because the map is the evidence and the histogram is the compact signature.

## Failure interpretation

If two source rows are within tolerance but their element tokens differ, retain one site with multiple row contributions. If a coordinate is too imprecise to decide, keep the rows separate only provisionally and set the affected site and group result to `unknown`; do not manufacture a general position. If a composition is absent from the supplied list, preserve the unmatched pair and let closure-dependent chemistry remain unresolved.

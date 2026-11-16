---
name: occupancy-formula-reconciliation
description: Use when testing whether occupancy-weighted periodic-site contributions agree with all supplied formula and formula-unit evidence while preserving disorder and unresolved chemistry.
license: Custom
metadata:
  role: composition-reconciliation-procedure
---

# Occupancy and formula reconciliation

## Boundary

Invoke this method only after periodic site orbits and their closure states are available. It tests supplied chemistry; it does not infer oxidation states, charge balance, or a preferred chemical model.

## Keep source quantities separate

For every atom row retain the raw element/type token, raw occupancy token, parsed occupancy or `null`, source row, and the derived orbit size of its site. A mixed-element site is one coordinate site with one contribution per supplied row. Do not split or merge rows merely to make a formula match.

Parse every supplied formula scalar independently. Keep its tag, raw string, source line, parsed element/count map or `null`, and parse status. Formula aliases can disagree; inventory all of them before selecting the primary token. Parse parenthesized groups, integer or fractional counts, and whitespace without erasing the raw string. An unparseable formula is `unknown`, not an empty composition.

## Compute contributions

For each row with a parseable element, occupancy, and closed orbit, compute the per-cell contribution as occupancy multiplied by orbit size. Keep a contribution ledger keyed to the source row and site. Sum by element without renormalizing occupancies. If an element token is missing, retain the row and mark its contribution unknown; a label-derived fallback element must carry a fallback flag.

When a formula-unit count is supplied and parseable, multiply every parsed formula count by that count to form expected per-cell totals. Compare both directions: a derived extra element and a formula element absent from derived totals are both evidence of conflict. Use a tolerance justified by occupancy precision and retain it with the comparison.

## Dispositions

Use `supported` only when all contributing rows are known, every orbit used is closed, the selected formula and formula-unit count parse, and the derived and expected element maps agree within tolerance. Use `conflict` when both sides are available but disagree, including competing formula tags or a non-closed operation result. Use `unknown` when required evidence is absent or unusable. Keep the available derived totals even when the final status is unknown or conflict.

Carry `unknown_atom_rows` (or an equivalent resolvable list) for every row excluded from arithmetic. Give a reason that distinguishes missing occupancy, missing element, unresolved orbit, missing formula, missing formula-unit count, and parse failure. Never call an unsupported comparison a conflict merely because a value is absent.

## Evidence contract

At formula level retain `formula_raw`, `formula_units_z_raw`, `derived_totals`, `expected_totals`, `status`, `unknown_atom_rows`, `formula_tag_inventory`, and `formula_tag_relation`. Every inventory item uses the raw tag, raw token, source line, parsed counts, and parse status. A contribution ledger should point to the atom row and site orbit that generated each number.

## Reconciliation checks

Before closing a record, verify that the sum of contribution rows equals the derived totals, that every site row appears once in the ledger, that mixed rows were not deduplicated, and that element keys are compared case-sensitively after a documented token normalization. Recompute totals after any orbit or parser correction. Propagate formula status into the record disposition and recompute aggregate status counts only after all records are closed.

This method applies to disordered structures, partial occupancies, and other evidence-bound composition audits where a clean-looking formula must not hide missing source information.

## Contribution ledger pattern

Keep one ledger item per atom-loop row. A useful item contains the record file, source row, site identifier, normalized element, raw occupancy, orbit size, weighted contribution, and a state. The sum of known ledger contributions is the derived element map; unknown items are listed separately and never silently dropped. This ledger also prevents a common error in mixed sites: two rows at one coordinate contribute two element totals while the orbit is counted once for each row.

Formula parsing should be conservative. Accept element symbols with optional integer, decimal, or fractional counts and nested parenthesized groups when their syntax is unambiguous. Reject trailing punctuation, malformed parentheses, and unknown markers as unparseable. Keep the raw formula unchanged so a reviewer can see why parsing failed.

When comparing maps, compare the union of keys. A zero-valued key is different from a missing key when the source explicitly supplied that element; absence of a source value is an unknown state. Preserve the selected formula tag and the complete tag inventory, because a later correction may change which alias is authoritative.

## Tolerance and status examples

Derive a comparison tolerance from the least precise occupancy in the ledger, and record the numeric value used. If all rows and formula inputs are present but one element differs beyond tolerance, status is `conflict` and both maps remain. If the formula matches but one occupancy is `?`, status is `unknown` with the row listed. If the formula itself is absent, retain row totals but do not claim a formula agreement.

Do not use the chemical symbol, space-group number, or an assumed valence to fill an absent occupancy. The reconciliation is an accounting check over supplied evidence, not a structure-refinement or chemistry-inference step.

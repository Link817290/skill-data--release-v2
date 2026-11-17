---
name: structured-scientific-json
description: Produce auditable scientific JSON registers from heterogeneous source records, with explicit evidence links, uncertainty states, and recomputable summaries.
license: Proprietary
metadata:
    domain: scientific-data-curation
---

# Structured scientific JSON

## When to use

Use this method when a request asks for a machine-readable scientific register assembled from multiple source records. It is suited to a result whose conclusions depend on a chain of observations, normalization, calculations, and decisions rather than on one copied scalar.

## Layer the report

Keep four layers separate:

1. **Source custody.** Preserve the exact input inventory, source order, row text, and metadata that a reviewer may need to challenge.
2. **Normalized observations.** Represent parsed dates, coordinates, measurements, and labels as a view of the source. Every normalized value needs a pointer to its source file, row, and field or cell.
3. **Derived calculations.** Store the included observation identifiers, units, formula label, and enough precision to recompute each statistic.
4. **Adjudication.** Store the adopted state, confidence, rule version, supporting observations, and counter-evidence separately from source facts.

Do not collapse these layers into a prose-only explanation. A later analyst should be able to replace one source row and see which derived fields are affected.

## Evidence boundary and identity

Enumerate the files actually present and use their exact names. Keep a manifest with a count. Prefer a source identifier; when none exists, create a deterministic fingerprint from stable normalized fields and record that it is derived. List order is not an identity.

For each item, retain a small evidence object such as `{source_file, source_row, field}`. For a calculation, repeat the included identifiers and row pointers near the calculation so a reviewer does not have to infer them from free text. A conclusion without a resolvable pointer is an unsupported assertion.

## Absence and conflicts

Use a consistent state vocabulary. `supported` means all prerequisites and pointers are present; `partial` means useful information exists but one requested branch is unavailable; `unknown` means the supplied evidence cannot resolve the question; `conflict` means supplied values disagree. Keep nulls and raw tokens visible. Never turn a missing value into zero, and never average contradictory observations without exposing both operands.

## Numeric discipline

Keep source precision intact. Normalize units and time zones before arithmetic. Report finite JSON numbers; represent an undefined result with `null` and a status/reason. Do not round inputs before computing. A displayed rounding convention belongs beside the derived value, not in place of the source value.

## Closure checks

Before writing the report, verify that:

- the manifest equals the discovered file set;
- every source row is accounted for exactly once, including malformed rows;
- every normalized evidence pointer resolves;
- event and status counts close from detailed arrays;
- comparison tables are generated from the same record objects as the aggregate.

Parse the emitted JSON again and reject non-finite numbers, accidental comments, duplicate identities, or an aggregate that was typed independently. The report should remain valid if keys are reordered.

## Transferability

This custody-and-closure pattern transfers to laboratory assay logs, sensor observations, ecological surveys, and any scientific review where another analyst must reproduce a conclusion from supplied records.

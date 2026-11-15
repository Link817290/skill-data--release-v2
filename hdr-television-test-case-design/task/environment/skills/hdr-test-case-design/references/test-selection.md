# Selecting a Defensible HDR Test Set

Use this note to decide which candidate cases belong in the requested function test list. It is a scope-control method, not a catalog of tests for any particular television.

## Start from named device capabilities

Create a compact matrix whose rows are the HDR capabilities explicitly named by the device material. Preserve the manufacturer's naming. For each row, record only the behaviors that are both relevant in the HDR reference and executable with a documented stimulus or observation method.

Create a second matrix from the project acceptance table. Keep one row per acceptance relationship and record: target format, controlled condition, measured or observed quantity, comparison boundary, and decision direction. Cross-link the two matrices before choosing cases. This prevents a short plan from silently dropping a project requirement while still avoiding an exhaustive feature catalog.

## Prefer core function evidence

Prioritize cases that directly establish a named HDR function's operation: activation or recognition, its characteristic processing or rendering behavior, and compatibility or transition behavior when that relationship is material. Add color, luminance, metadata, or fallback cases only when the supplied evidence supports the corresponding relationship.

Do not expand a function test list into a general television regression suite. Connectivity stress, applications, audio, power recovery, panel protection, broadcast reception, and user-interface behavior belong only when the requested HDR objective and the supplied materials make them directly relevant.

## Control granularity

- Merge observations that use the same setup, stimulus sequence, and acceptance decision.
- Split a candidate when it changes format, measurement method, controlled variable, or pass/fail decision.
- Remove duplicate cases that differ only by wording or repeat generic setup.
- Prefer a smaller closed set over a long list containing weakly supported peripheral scenarios.

A split is acceptable when different measurements need different setup or evidence. A consolidation is acceptable when one procedure genuinely produces every required result. In either case, review coverage by relationship rather than by final row count.

## Handle incomplete evidence

If a useful HDR behavior is supported but the supplied instrument cannot perform the required action, do not invent an instrument feature. Either use another documented observation method named in the materials or omit the candidate from the executable list. If an acceptance threshold is missing, use a reproducible comparison or observable condition instead of manufacturing a number.

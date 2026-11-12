---
name: progress-meter-formatting
description: Method for auditing textual progress-meter formatting. Use when duration text, totals, prefixes, custom layouts, or width-bounded terminal output are incorrect or inconsistent.
---

# Progress Meter Formatting

## Inventory rendering surfaces

Locate the exported pure-formatting helpers before investigating terminal emulation. Map which helper owns time text, count and total normalization, composed meter layout, visible-width measurement, and final stream output. Treat each layer as a separate contract. Do not change low-level Unicode or control-sequence handling unless a focused reproducer proves that layer is the first divergence.

## Exercise values and branches

Build a compact matrix from the public signatures, docstrings, and neighboring tests. For numeric inputs, test representatives on both sides of the neutral boundary and separate ordinary finite values from values for which the renderer's arithmetic or integer conversion is not closed. For optional inputs, keep absent, inferred, and explicit states separate. Record both returned text and exceptions; derive policy from local evidence rather than assuming every unusual value belongs to one catch-all case.

Before changing width helpers, inventory every syntactic return from the public renderer and use branch coverage or lightweight tracing to select one representative for each return path. Apply the same layout invariant to every representative, including paths that omit normal components. Make violations observable with adversarial but valid content, measure display cells with the library's own width helper rather than `len`, and compare sibling returns before deciding which layer owns the invariant.

Exercise each public output policy across ordinary, redirected, and degraded runtime resources. Resolve the effective sink first, then probe every public entry point that directly uses it and every context manager that temporarily coordinates it. Keep resource selection separate from formatting so a sink or lifecycle failure does not get mistaken for a serialization defect.

## Localize normalization drift

Trace representative values from the public call through normalization, derived arithmetic, branch selection, and final serialization. Compare equivalent normalization responsibilities that occur at more than one public lifecycle entry point. Patch the earliest stage that violates a documented or sibling-branch invariant, then rerun one ordinary case for every changed layer.

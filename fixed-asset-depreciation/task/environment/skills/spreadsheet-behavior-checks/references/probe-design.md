# Probe design

## Establish what the engine actually calculated

Inspect formulas and data-only caches separately. A missing cached value after
a library save does not prove that a formula is broken. Conversely, a plausible
cached answer does not prove that it updates when a driver changes.

Use an isolated Office profile and separate output path for native calculation.
If calculation cannot complete, retain that limitation instead of substituting
zeros. Reopen the produced file, inspect formula-error cells, and confirm that
the watched results belong to the file and input state just calculated.

## Choose a causal experiment

Start from an untouched copy for each independent scenario. Select a genuine
input and identify both its immediate dependents and the business summaries
that should receive the change. Alter one concept at a time unless a combined
experiment is needed to test an interaction.

Use three kinds of observations:

- A small independent numerical example for the modeled operation.
- A relation that should hold between equivalent business representations,
  derived from the model's definitions.
- A domain boundary with a valid neighbor, interpreting invalid input according
  to the documented business rules.

Do not expect every watched value to change. A future event may leave today's
report unchanged; a different department may receive no affected expense.
Reason about the dependency path before interpreting a zero delta as a defect.

## Avoid checks that share the same error

Two totals sourced from the same incorrect intermediate can agree perfectly.
Add an independent economic check or examine a known item's sequence before
using a portfolio reconciliation as evidence of correctness. When a check fails,
trace the original driver instead of inserting a balancing value downstream.

Inspect error types as well as numbers. Blank, zero, an unresolved input and an
error are different states. An invalid business input may appropriately produce
a visible diagnostic rather than a monetary answer; choose observations that
can distinguish these outcomes.

Choose tolerances using currency precision, scale and business materiality.
Distinguish stored amounts from display rounding. Avoid tolerances so loose that
they hide a repeated period error, or exact floating-point equality that rejects
a correct calculation.

Restore the original inputs or reload the source and confirm reproducibility.
After final edits, repeat the required native calculation on the actual delivery
file, and check preservation of features that a calculation engine may rewrite.

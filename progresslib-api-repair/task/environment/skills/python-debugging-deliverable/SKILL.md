---
name: python-debugging-deliverable
description: A reusable method for repairing a Python library from reproducible failures. Use when a source tree has caller-facing regressions and the handoff must preserve APIs, explain causes, and show local evidence.
---

# Python Debugging Deliverable

## Establish the delivery surface

Inventory the requested outputs, immutable inputs, editable modules, and commands available offline. Keep source changes, diagnostic notes, and verification evidence separate. Do not alter tests to silence a failure and do not add dependencies without a demonstrated need.

## Convert symptoms into contracts

For each independent symptom, write a short contract before editing:

1. Public entry point and accepted input shapes.
2. Observable result, including return type and exception behavior.
3. Normal, fast, and optional branches that callers may exercise.
4. A minimal reproducer and a nearby ordinary case.

Trace the call path from the public entry point to the first observation that diverges from the contract. Form at least two plausible ownership hypotheses before editing, then use a focused probe to distinguish them. Use a recording stand-in when a real terminal or external service obscures delegation.

Maintain a scratch coverage ledger with one row per public entry point or meaningfully different mode: input shape, focused probe, observed outcome, owning source path, and disposition. Seed it from package exports, helper modules, docstrings, and neighboring tests. Make one breadth pass across every reported symptom family before deepening any single candidate. A broad downstream symptom may have multiple branch-specific causes, so do not mark it closed after the first reproducer; inspect sibling implementations and return paths until every candidate row has either evidence or an explicit reason to exclude it.

Classify each surprising probe as confirmed, ambiguous, or unrelated. A surprising edge case is not automatically a defect: require a documented contract, a consistent sibling branch, or a reference operation that establishes the expected behavior. Patch only confirmed rows. This prevents speculative cleanup in a low-level helper from consuming the investigation while reported surfaces remain untested.

Treat the first breadth pass as a stage boundary. Before opening second-order hypotheses, every reported symptom family and every sibling branch already found on its call path must have a ledger disposition. Rank confirmed rows, patch and verify them, and create their report records before exploring adjacent modules or general standards-compliance improvements. Only reopen the search when a named symptom remains unexplained. Reserve the final third of the working window for confirmed repairs, the broad regression check, and report completion.

## Patch locally and preserve the boundary

Prefer a small correction at the point where the invariant is first broken. Preserve signatures, defaults, laziness, exception types, cleanup, and side effects for already-valid callers. Re-run the focused probe after each edit so coincidental downstream changes do not masquerade as a root-cause repair.

Before declaring completion, inspect the diff for edits outside the failing path, altered call shapes, duplicated cleanup, and new implicit conversions.

## Verify and hand off

Run focused reproducers first, then the broadest supplied local check that is feasible. Capture commands and outcomes. Keep one local defect record for each independent cause: bind the symptom to a source location, record the competing ownership hypothesis that the evidence rejected, explain the repair boundary, and name the focused result. State checks that could not run instead of implying success.

Reserve a finalization stage before the execution limit. Once confirmed rows are patched and checked, stop opening new ambiguous branches, complete every supported defect record, and run the broad regression check. An incomplete report after exhaustive exploration is weaker evidence than a bounded investigation that clearly distinguishes repaired, unresolved, and excluded rows.

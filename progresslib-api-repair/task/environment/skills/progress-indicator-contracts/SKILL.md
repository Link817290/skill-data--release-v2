---
name: progress-indicator-contracts
description: Contract-oriented guidance for investigating Python progress indicators. Use when rendering, lifecycle, output-policy, or state-query behavior differs across supported operating modes.
---

# Progress Indicator Contracts

## Map state by lifecycle phase

Trace input discovery, option normalization, state initialization, refresh, iteration, reconfiguration, close, finalization, and process-exit hooks. At each phase, inventory which attributes and resources have been established before side effects. Use failure injection at phase boundaries to verify that rollback and cleanup depend only on state guaranteed at that point, and exercise repeated cleanup separately from the ordinary path.

Do not close the lifecycle row after one ordinary cleanup succeeds. The minimum lifecycle table covers successful construction, failure on both sides of each constructor side effect, explicit cleanup, repeated cleanup, public reconfiguration, and the callable actually registered for runtime finalization. Capture registered callbacks and invoke them under recording stand-ins that make any potentially blocking operation fail immediately; this distinguishes callback ownership from ordinary caller-driven cleanup without assuming they share a contract.

## Compare operating modes

Build a pairwise matrix over output policies, input observability, manual and inferred state, optional metadata, fixed layout constraints, and custom formats. When the same public option enters at multiple lifecycle stages, replay locally justified equivalence classes at each stage and compare normalized object state. Snapshot state and serialized output independently. Give probe inputs distinguishable markers so the first stage that changes a value can be observed rather than guessed from a later exception. A constructor and a later public state-changing method are separate matrix rows even when they accept the same option name.

## Preserve integration behavior

Keep iteration order, laziness, cleanup, locking, update calls, and exception behavior stable for unaffected callers. Pair every edge-case reproducer with a neighboring ordinary case. For background activity, test caller-requested and runtime-driven lifecycle events separately while controlling resources and elapsed time with recording stand-ins; derive each event's blocking and ownership contract from its caller.

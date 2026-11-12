---
name: async-iteration-protocols
description: Diagnose Python asynchronous iteration adapters. Use when a wrapper accepts async sources but iteration, termination, state updates, or exceptions vary by input implementation.
---

# Async Iteration Protocols

## Inventory roles before branches

List the protocol methods the adapter reads during construction and during each iteration step. For every stored callable, note its owner, return kind, and when it is invoked. Establish role identity from the actual protocol transition rather than extrapolating it from one common implementation shape.

## Trace minimal protocol shapes

Construct tiny inputs that each expose only one advertised capability, plus one ordinary async generator. Log special-method calls and values without eagerly consuming the source. Compare the trace with a direct `async for` baseline to locate the first missing, duplicated, or misdirected transition.

## Preserve iteration behavior

After changing dispatch, verify laziness, termination, explicit close, wrapper counter updates, and exception propagation. Pair the unusual input with ordinary synchronous and asynchronous cases so a broader fallback does not capture the wrong protocol.

---
name: concurrent-map-contracts
description: Analyze Python concurrent map wrappers. Use when progress metadata, warnings, or executor delegation vary with multiple inputs, generators, or pool options.
---

# Concurrent Map Contracts

## Establish execution semantics empirically

Compare the wrapper with the corresponding non-progress mapping operation. Before editing, complete a small permutation table containing a single sized input, multiple unequal sized inputs, a sized and unsized input in both orders, an empty input paired with work, and an explicit caller override. Vary one property at a time and record reference output separately from progress metadata and warnings. The table is evidence for semantics, not a list of assumed outcomes.

## Audit metadata uncertainty

Trace how the wrapper obtains optional size information and read the local runtime API contract for its fallback argument. Choose a fallback marker outside the valid metadata domain so unavailable information remains distinguishable from a measured boundary value. Record each input's observation and uncertainty before aggregation; verify explicitly whether an unavailable marker is being treated as measured data, whether a known observation is discarded, and what happens when no observations are available. Keep explicit caller metadata separate from inference.

## Instrument delegation and policy

Use a recording progress class and a minimal executor stand-in to observe received options without depending on scheduling. Route executor-only, map-only, and progress-only arguments to their actual consumers. Inventory every warning branch before editing; for each one, replace the execution handoff after input analysis and probe the full input permutation table on both sides of the policy threshold. Trace every policy input back to the execution or metadata observation that owns it rather than reusing a convenient aggregate without evidence.

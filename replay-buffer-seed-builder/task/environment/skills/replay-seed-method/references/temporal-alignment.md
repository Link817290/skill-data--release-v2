# Temporal alignment and representative sampling

## Determine the clock relation

Treat annotation indices as absolute state row indices when the sequence begins at the same episode origin, annotated boundaries fall within the state array, and no material declares a different sample rate. A longer corrected trajectory usually indicates an append only stitched tail, not a reason to stretch every earlier boundary. When the declared phases are ordered and exhaustive through the annotation endpoint, extend the terminal phase across a later stitched tail unless another event or reset is visible.

## Build a compact scaffold

Start with the episode origin and terminal state. Infer a coarse project cadence from repeated clean timing anchors, acquisition metadata, or stable long phase spans, then place interior anchors on that cadence across the trajectory. Ensure that every operationally important phase has a representative. If a short transition phase falls between coarse anchors, add one interior point near its temporal center instead of moving the whole scaffold.

Prefer stable cadence points over arbitrary decimal fractions when both give comparable coverage. Keep the sample set small enough that each row has a distinct training purpose. Sort only after the chosen source rows and their phase assignments are frozen.

## Verify

For every selected time, prove that it is inside the adopted state array and exactly one phase interval after any justified terminal extension. Compare the first and last selected times with the actual trajectory bounds. Reject proportional remapping when it changes the phase of a frame that already lies inside a declared absolute interval.


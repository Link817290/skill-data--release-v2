---
name: replay-seed-method
description: Build compact phase aware replay seeds from corrected robot state trajectories and annotations whose coverage may differ from the stitched trajectory.
---

# Replay seed construction

Use this method when a downstream learner needs a small, ordered seed artifact derived from an existing state trajectory and semantic phase annotations.

## Workflow

1. Inventory every candidate state array, its shape, and the coordinate frame described by the project. Prefer the corrected or reconciled state array when both raw and corrected variants exist, and preserve the chosen row identity through every derived field.
2. Decide whether annotations and states share absolute frame coordinates before assigning phases. Read [temporal alignment and sampling](references/temporal-alignment.md) when the annotation coverage differs from the stitched trajectory or when a compact sample set must be chosen.
3. Derive every observation from the same adopted state row. Treat the first translation block as base position only when the project state layout or the conventional generalized coordinate layout supports it, and bind the vertical component to the third translation coordinate.
4. Make action limits, target emphasis, and routing phase aware. Early approach data should favor imitation and conservative residual authority, contact data should emphasize contact establishment, and stable lift data should support reinforcement learning warm start with lift as an adopted objective.
5. Read [validation and closure](references/replay-seed-validation.md) before delivery. Close every record against its source row, phase interval, units, ordering, and downstream use rather than validating fields independently.

## Evidence discipline

Keep a local record ledger containing the emitted time, source row, phase decision, state statistic inputs, coordinate interpretation, and metadata branch. A value is closed only when its source row and adopted phase are both unambiguous. If the coordinate layout, annotation mapping, or policy branch cannot be supported, leave that conclusion unresolved instead of silently switching sources.

## Counterexamples and stop conditions

Do not scale annotation frame numbers merely because a stitched trajectory has more rows. Scale only when the project explicitly states that the annotation and trajectory use different sampling clocks. Do not copy live training bounds into a seed policy without checking whether the seed is intended to be conservative before contact. Stop when the state array cannot be tied to a coordinate convention, when annotations overlap without a precedence rule, or when two candidate rows claim the same emitted time.


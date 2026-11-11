# From manual sections to an executable procedure

Identify the starting condition, prerequisites, actions, observable confirmation
and next state. Manuals often spread these across loading, setup and diagnostics.
Put them together without losing model or installed-option boundaries.

Before changing hardware or settings, address active commands and retained state.
An idle-looking device can still receive queued host commands. Power cycling may
clear temporary formats or settings; saving and restoring belong in the sequence
when the manual identifies that behavior.

After a change, determine which calibration or validation is invalidated. A short
check that preserves sensor gain is not equivalent to recalibration that changes
it. Restore service only after the relevant validation, not merely after clearing
an alarm or dismissing a setup wizard.

Make the first-article check concrete: what is examined, how many pieces if the
business specifies a count, and what happens when one fails. A claim of conformity
requires results; an instruction for future conformity checking does not.

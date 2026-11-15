---
name: sequence-display-measurement
description: Measure sequence artwork, transparency, timing and coordinate alignment in Godot integrations without prescribing a task-specific repair.
---

# Sequence display measurement

Use this skill when a sequence animation looks displaced, delayed, unexpectedly bright, or inconsistent across backgrounds. It provides a measurement vocabulary for comparing a production contract with an actual display. Obtain required dimensions, timing, anchors and allowed materials from the current production documents; this skill does not define those requirements.

## Establish the observation boundary

Distinguish the source image, texture resource, animation frame and displayed pixel. A correct file on disk does not establish that the renderer uses it. A populated animation resource does not establish that a sprite is visible. Record the resource path, decoded dimensions, image mode, animation name, selected frame and observation time together. When content identity matters, compare decoded pixel bytes as well as source-file hashes: encoding differences and visual differences are different findings.

Count frames in natural numeric order. Record gaps, duplicates and fully transparent images separately. Duplicate frames can encode a hold, and transparent frames can encode a delay. Neither is automatically corruption. A sequence without reliable timing metadata has an unknown source rate; report the uncertainty rather than deriving a rate from a catalogue video's playback rate. Keep source indexing stable while evaluating a separately specified playback interval.

## Measure coordinate relationships

Use named coordinate spaces: image pixels, sprite-local coordinates, parent coordinates and world coordinates. Record the declared image-space anchor and transform it through the same chain as the visible image. Compare the resulting world point with the requested point using an explicit tolerance. Node position alone cannot prove this relationship. Centering conventions, offsets, scale, rotation and ancestor transforms can produce different internal values with identical displayed geometry.

Treat position, orientation and size as separate observations. For a directional graphic, compare its declared forward axis with the travel vector in a common coordinate space. Normalize angular differences around the wrap boundary. For nonuniform scale or skew, inspect transformed basis vectors rather than assuming a rotation field fully describes the result. A geometry comparison should accept equivalent representations and reject coincidental alignment at only one sample.

## Measure appearance and time

Check visibility through the ancestor chain, effective modulation, self-modulation, texture alpha and material behavior. A sprite may exist and advance frames while contributing no visible pixels. Conversely, a valid first frame can be wholly transparent by design. Evaluate visibility over the interval required by the production contract, separating the presence of an enabled renderer from the presence of nonzero image alpha.

Inspect dark and light backgrounds at matching timestamps. This helps distinguish edge contamination, lost highlights and inappropriate blending without relying on a single favorable background. Precomposed image sequences can have different blending needs from the layered source project. Record what was displayed rather than inferring material settings from a source format label.

Measure onset, progression and completion against the engine clock. Quantize tolerances to the sampling interval and state whether timestamps refer to calls, updates or rendered frames. Sparse contact sheets are useful for layout but cannot prove every intermediate frame. Combine them with frame-state samples and direct image checks when the claim concerns continuity.

## Record a bounded conclusion

Use the observation matrix in [display-observations.md](references/display-observations.md). Include the expected relationship, measured relationship, evidence path and unsupported rendering features. Report disagreements before choosing an implementation. Do not substitute parameter matching for visible correctness, and do not claim GPU validation from a CPU reconstruction.

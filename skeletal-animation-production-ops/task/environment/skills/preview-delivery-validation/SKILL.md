---
name: preview-delivery-validation
description: Validate reproducible animation previews and production handover artifacts against the delivered engine project, while documenting visual and execution limits.
---

# Preview and delivery validation

Use this skill when an engine integration must be handed to another engineer with reproducible visual evidence. It covers the relationship between a project, execution record, preview and delivery register. It does not supply task-specific output values or a reference implementation.

## Establish artifact identity

Identify the project that will actually be delivered. Record its relevant files and source-asset hashes before capture, and identify the tool version and invocation. A preview made from a nearby working copy may look correct while describing a different build. Reproduction evidence should therefore bind the command, project path and exported artifacts to one execution. Preserve original input assets when the production contract requires their identity.

Separate authoring files, runtime dependencies, generated evidence and administrative records. Each has a different completeness test. A project requires all resources its runtime loads. A preview requires the sampled data and image inputs used by its renderer. A register requires references that resolve in the delivered folder, not merely plausible filenames. A successful export process establishes that an operation completed; it does not establish that the animation met the production contract.

## Understand the capture model

Document whether a preview is a GPU framebuffer capture, an engine-state reconstruction or a standalone animation export. These methods support different claims. A reconstruction can inspect actual engine transforms and textures while omitting shaders, clipping, occlusion or draw-order effects. State those limits and verify that the delivered project stays within the supported model before treating the preview as evidence.

For reconstructed frames, verify the mapping from engine coordinates to image coordinates, the effective color and transparency calculation, and the treatment of centering and transforms. Keep timestamps and frame indices with each sample. Check that the renderer handles empty intervals explicitly; otherwise a missing sample can look like a deliberately empty scene. A contact sheet is an index into time, not proof of every frame between its panels.

## Compare evidence independently

Re-export from the delivered project into a fresh directory. Compare state traces and image artifacts with the submitted preview using the documented determinism assumptions. Byte equality is useful when the tool produces deterministic files, but equivalent encodings may need decoded-pixel comparison in other pipelines. Reproduction alone is insufficient: a consistently wrong or invisible animation can reproduce perfectly. Compare visual and behavioral claims against source artwork and the production contract independently.

Examine contrasting backgrounds and representative onset, overlap and completion intervals. Reconcile event traces with the visible sequence using the same clock definition. Record which observations are automated and which required direct inspection. Preserve failures and tool errors separately; an engine startup error is not evidence that every business requirement failed.

## Validate the handover record

For each delivery entry, check that the referenced files exist within the intended output, that the recorded command identifies the delivered project and preview destination, and that the evidence supports the claimed completion. Free text should name the changed area and link to an inspectable artifact. Nonempty text alone does not establish a meaningful handover. Conversely, wording differences should not fail an entry that provides equivalent, verifiable information.

Use [handover-evidence.md](references/handover-evidence.md) as an evidence checklist. Include tool versions, command context, artifact paths and known coverage limits. Avoid asserting that a local deterministic test is a calibrated model benchmark. A production handover is complete only to the extent demonstrated by the delivered files and measured behavior.

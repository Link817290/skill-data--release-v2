---
name: unified-patch-workflow
description: Use when a native repair must be delivered as an auditable unified diff as well as an applied working-tree change.
---

# Unified Patch Workflow

The working tree and the patch are two representations of one repair. Keep them synchronized
from the initial snapshot through final validation.

## Start with a stable state

Snapshot the source state with version control or a byte-for-byte copy, and identify the
smallest file set that owns the defect. Never build a patch from generated output or from a
tree that already carries unreported edits.

## Generate and apply one repair

1. Make one coherent edit at a time and inspect its surrounding context. Preserve line endings
   and unrelated whitespace where practical.
2. Generate a standard unified diff whose paths apply from the stated project root. Include
   enough context for a reviewer to identify the old and new contract.
3. Dry-run the diff in a clean copy before changing the working tree. Apply the exact diff,
   then inspect both the resulting source and the patch. A desired token in the source is not
   evidence that the recorded patch was applied.
4. If the source is version-controlled, test the reverse diff against the repaired tree. This
   catches stale, hand-edited, or partially applied patches.

## Review the boundary

Reject conflict markers, rejects, absolute machine paths, generated build products, credentials,
and unrelated refactors. Every changed hunk must be explained by the diagnosis. Protect source
and public headers when the failure is in build metadata; changing implementation code to hide a
package-interface problem is not a minimal repair.

## Close state

Run clean validation after applying the patch. If validation requires a further source edit,
regenerate and reapply the diff from the new captured state. Record the final patch path,
application result, and validation result together so a maintainer can reproduce the handoff.

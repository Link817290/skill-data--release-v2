---
name: build-validation-reproducibility
description: Use when a native build repair must be demonstrated from a clean source tree, isolated install prefix, and independent downstream consumer.
---

# Build Validation and Reproducibility

Validation is a proof of the repaired contract, not a rerun of whatever state happens to be
on disk. Separate producer state, installed state, and consumer state.

## Clean validation loop

1. Copy or export the repaired source to a fresh temporary tree. Use a new build directory and
   install prefix for each attempt; keep both outside the source tree.
2. Configure with the options that exposed the failure. Record the command, generator,
   compiler identity, and exit status. If configuration fails, do not report later phases as
   successful.
3. Build the producer with explicit parallelism. Run supplied tests when they are available
   and relevant, and distinguish test failures from build or install failures.
4. Install into the isolated prefix. Inspect the installed files and generated package/import
   metadata, including the target and dependency names used by consumers.
5. Configure a small downstream project in a separate tree through the public package entry
   point. It must compile against a public header and link the intended public target. Run the
   binary when it has a meaningful smoke behavior.
6. When relocation is part of the observed workflow, copy the installed prefix to a new path,
   remove the original, and configure consumers with only the moved prefix discoverable. Test
   each relevant target variant; leaving the old prefix in place makes absolute-path leakage
   indistinguishable from a correct relocatable export.

## What the report proves

Record commands rather than paraphrases and give an explicit result for producer configure,
producer build, install, prefix relocation when applicable, each consumer configure/build,
and smoke execution. Use stable symbolic paths in the report when temporary directories are
involved. State the exact source and patch that were validated, and keep the report's overall
status consistent with every phase; a producer pass with a consumer failure is still a failed
repair.

When layout independence is part of the claim, run at least one deliberately non-default
combination whose library and include destinations have different shapes from the defaults.
Record those configured values and the installed locations of the config and pkg-config files.
The accompanying diagnosis should state the invariant being tested, tie observed generated
values back to their producer inputs and runtime base, and explain what the perturbation rules
out. This turns a passing layout test into causal evidence rather than an unexplained command
transcript.

Reports may use a top-level status or a structured summary, but they need one unambiguous
aggregate result consistent with every captured scenario. Also retain explicit per-scenario
results so a reviewer can locate any partial failure without inferring it from prose.

## Failure interpretation

A consumer pass that supplies a manual include directory or raw archive path may hide a broken
exported interface. Distinguish package-provided usage from test scaffolding. If a clean run
fails because a compiler or external dependency is unavailable, preserve that output and state
the boundary as deferred or blocked instead of claiming a successful build.

## Final consistency check

Compare the report with the current source and unified patch. Remove temporary build trees and
generated files from the deliverable. A final clean run should be independently repeatable and
should not depend on a prior build directory, an ambient linker search path, or network access.

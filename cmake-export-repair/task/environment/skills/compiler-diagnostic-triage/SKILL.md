---
name: compiler-diagnostic-triage
description: Use when a native build failure may be caused by configuration, compilation, linking, installation, or runtime loading and the correct repair boundary is not yet known.
---

# Compiler Diagnostic Triage

Native build output is a sequence of state transitions. Classify the first actionable
failure before editing; later messages are often consequences of the same missing input.

## Triage sequence

1. Capture the complete command, working directory, relevant options, and exit status. Re-run
   only after the first failure is reproducible; verbose output should answer a question.
2. Classify the emitting phase: configure/generate, compile, link, install, downstream
   configure, downstream link, or runtime loader. The tool name alone is not a phase.
3. Rewrite the message as a falsifiable claim. Examples: “the compiler was never invoked,”
   “the object exists but the archive is absent from the link search,” or “the import file
   names a target that the package never exported.”
4. Trace the claim to the owning input: cache or toolchain settings for configuration,
   source and headers for compilation, target properties for linking, and install/export
   rules for package consumption.
5. Check whether the message is primary. A missing generated file can be a configuration
   failure; a long undefined-reference cascade can be one missing archive or ABI mismatch.

## Evidence ledger

For each candidate cause, record the phase, exact diagnostic, owning file or generated
artifact, a minimal reproduction command, and an observation that would disprove it. Rank
causes by proximity to the first failure and by whether the proposed edit changes the owner
of the broken contract. Keep warnings, notes, and errors separate; a warning promoted by
`-Werror` is still part of the configured contract, not proof of a source defect by itself.

## Boundary checks

Configuration failures mention policies, generators, options, or missing packages and occur
before compilation. Compilation failures identify a source location and a compiler message.
Link failures identify an object or executable and an unresolved symbol, library, or file.
Installation failures expose missing install rules or inconsistent export sets. A failure
that appears only after installation belongs to the package interface until source and ABI
evidence shows otherwise.

Do not add arbitrary search paths to make a link line pass before checking the target's
declared interface and installed files. Do not silence a diagnostic with a flag when the
build contract requires a real correction. A successful producer build cannot prove that a
fresh downstream consumer can use the installed package.

## Handoff and stop conditions

Write the diagnosis before the repair. State why secondary messages are not separate defects,
what behavior must remain unchanged, and which clean command will demonstrate closure. Stop
and report an environment or dependency boundary when the suspected phase cannot be reached;
do not convert an unavailable compiler or package into an unsupported claim about the source.

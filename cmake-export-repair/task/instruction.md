# Task

A native library project in `/workspace/project` does not complete its captured build-and-consume workflows. Diagnose the failures, repair the project, and leave a reproducible record for the maintainer.

Use only the materials under `/workspace`; no conclusion may depend on information that is not supplied there. Preserve the supplied source and evidence files except for the smallest necessary repair, do not use network access, and create the empty deliverable files before beginning your analysis.

Deliver `/workspace/analysis/diagnosis.md` with an evidence-based root-cause analysis, `/workspace/patches/patch_0.diff` as a standard unified diff, the applied repair in `/workspace/project`, and `/workspace/build_report.json` recording the commands and final validation results. Completion means the repaired project builds, installs, and every captured downstream scenario succeeds from clean state.

Before you start, review the procedures already provided in this environment and follow any whose stated scope matches the failures you observe.

---
name: review-measurement-control
description: Reconstruct measurement-control baselines and evaluate instrument checks with the correct scale, degrees of freedom and grouped decision rule.
---

Separate measurement records from the approved control rule before calculating limits. Identify the reference regime, instrument, unit, baseline membership and independent record key. A printed sample count is a claim to reconcile, not a substitute for reconstructing the baseline.

Read [baseline discipline](references/baselines.md) when old summary cards conflict with raw records or later observations are available. Read [scale and grouped checks](references/scale-and-groups.md) when instruments use fitted correction curves or several reference points jointly qualify a run.

Use [control_limits.py](scripts/control_limits.py) for transparent pooled-repeatability and simultaneous-control calculations. Pass all parameters explicitly. The helper does not choose a baseline, validate an instrument, or authorize removal of records.

For a reusable command-line tool, read [rerunnable checks](references/rerunnable-checks.md). Validate method selectors and incomplete groups, then challenge the tool with both representation changes and changed measurements.

Verify signed intermediate values as well as final flags. An absolute-value decision can conceal a reversed correction sign. Report pointwise failures, process-pattern evidence and missing workload links separately. Do not infer product acceptance from process control alone.

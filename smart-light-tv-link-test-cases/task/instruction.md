# Ambilight and Hue Linkage Test Design

You are preparing a test-design workbook for the TV function QA team. Use the supplied functional specification, product connection guide, test SOP and model reference documents to design a practical Ambilight/Hue linkage suite. This is test planning: no equipment execution records are supplied, so do not report tests as having passed or invent measurements.

Cover the basic connection and linked-mode workflow, real-time and concurrent performance, interruption/recovery and competing controls, and environmental adaptation and long-duration reliability within the documented linkage scope. Keep component-level electrical/protocol debugging, unrelated App UI testing and undocumented model-specific capabilities outside the suite. Identify prerequisites that depend on a release, supported device or configurable policy.

Deliver an English Excel workbook at `/workspace/output/linkage-test-cases.xlsx`. Each case must identify its module, objective, MoSCoW priority, preconditions, actionable ordered steps, observable expected results, an execution-result field and relevant remarks. Include an equipment/environment checklist and a brief priority explanation. You may organize sheets and rows as appropriate; case IDs, sheet titles and wording need not match a reference layout. Leave execution results blank or explicitly unexecuted.

Design steps that a tester can actually carry out, including the triggering action, observation endpoint and any recovery or configuration dependency. For quantitative expectations, identify the measured quantity, units, timing origin or baseline, applicable limit and evidence source. Derive acceptance criteria from the applicable source, distinguishing an authored test stimulus from a product guarantee. Where documents leave endpoint scope, a release policy or a capability unresolved, explain the condition or pending decision rather than asserting an unsupported fact. Explain any source conflict affecting the planned verdict in the case remarks.

The functional specification supplies normative product behavior; use the SOP for reproducible setup, measurements and exit requirements within its stated scope. Keep requirements for different endpoints distinct and disclose a same-scope conflict that cannot be resolved from these documents. Model manuals and catalog facts establish context only where applicable. Do not infer native linkage support from a product name alone.

Put all final deliverables in `/workspace/output/`. Preserve the supplied materials.

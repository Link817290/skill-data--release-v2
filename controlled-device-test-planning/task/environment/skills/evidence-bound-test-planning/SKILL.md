---
name: evidence-bound-test-planning
description: Build executable device and host test plans from conflicting product documents, using scoped acceptance authority, controlled experiments and explicit measurement definitions.
---

# Evidence-bound test planning

Use this method when a device relies on a host platform, when documents describe
different revisions, or when successful behavior could travel through several paths.
The plan must let another tester reproduce the initial state, apply an input, observe
an outcome and make a supported decision. Keep proposed tests separate from results.

Read [references/applicability-and-authority.md](references/applicability-and-authority.md)
when sources disagree about hardware, firmware, timing, capacity or feature support.
Read [references/causal-tests-and-metrics.md](references/causal-tests-and-metrics.md)
when an experiment involves multiple communication routes, several target devices,
recognition rates, latency, environmental stress or persistence across a reset.

## Establish the testable claim

Separate the controlled device, host, accessory and service. Record which entity each
source describes. A host's radio version or bundled accessory does not identify the
device under test. Discover actual hardware and software applicability before choosing
actions that depend on construction or menus.

For each selected function write a claim in this form: under a named initial state
and applicable configuration, a defined input produces a defined observable outcome.
If no source supports the feature, leave it outside acceptance. If applicability is
unresolved, name the decision that is pending and the observations that can still be
collected. Do not fill the gap with a plausible manufacturer guarantee.

## Design the experiment

Work backward from the claimed outcome. Specify prerequisites, the action that changes
state, the observation that would distinguish success from failure and the control
that rules out a competing cause. Restore the starting state between comparisons.
Keep test selections, such as repetitions or geometry points, distinct from published
product limits.

Use separate cases when the controlled variable, failure mechanism or acceptance
authority changes. Shared setup is useful when explicitly linked to the affected cases.
Keep the evidence chain readable within each case rather than scattering decisive
conditions across unrelated notes.

Before finalizing a case, walk it as the next operator: identify the entity that
changes state, the evidence that its starting state holds, the input, the observed
endpoint, and the restored comparison state. If a shared prerequisite supplies one
of these, link it explicitly and check that it controls this experiment's variable.
An applicability register records what is supported; it cannot perform a missing
measurement or causal control on the operator's behalf.

## Close the plan

Check that every acceptance statement names its configuration and measured quantity.
Trace numerical limits to the applicable source and event definition. Reconcile steps,
expected behavior and acceptance so they describe the same experiment. A measured
response does not by itself establish the route, binding, persistence or service that
caused it.

Prioritize by consequence and dependency: loss of primary control, unsafe operations
and failures that invalidate later measurements deserve earlier attention. Keep actual
results empty until execution; use an explicit planned state. Reopen an affected case
when later evidence invalidates its setup or authority.

Stop the affected test when safe setup is unknown, the required capability cannot be
confirmed, an instrument cannot resolve the requested quantity, or competing causes
cannot be isolated. Describe the next observation or owner decision needed to proceed.

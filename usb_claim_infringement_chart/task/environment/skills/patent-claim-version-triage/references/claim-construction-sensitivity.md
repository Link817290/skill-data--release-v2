---
name: patent-claim-construction-sensitivity
description: Identify claim-construction dependencies in technical infringement triage, distinguish them from evidence gaps, audit proposed evidence bridges, and propagate one hypothetical interpretation at a time into claim-level outcomes. Use after claim normalization and source scoping, before finalizing a chart whose result may depend on protocol-to-claim mappings.
---

# Patent claim-construction sensitivity

## When this method applies

Use this skill when a technical comparison cannot be closed without deciding what
a claim term covers, when a protocol uses labels that resemble but do not exactly
match claim language, or when counsel asks how an outcome changes under a stated
interpretive assumption. It complements element comparison; it does not replace
formal claim construction by a court or a legal opinion from counsel.

The central discipline is to keep three questions separate:

- what the target record says;
- what the claim requires under a selected interpretation;
- whether the supplied record links an external rule to the exact target and mode.

A missing target fact is not cured by calling it a construction issue. A genuinely
ambiguous claim-to-protocol mapping is not resolved merely because a product
document is detailed.

## Create a construction-dependency register

Start from normalized limitations and mark every comparison that depends on a
semantic mapping rather than a directly shared proposition. Common dependency
types include:

- a protocol phase proposed as the claim's start or end event;
- a channel proposed as a claimed conductor;
- one information field proposed as another information category;
- a static state proposed as a pattern, transition, or sequence;
- a physical response proposed as a communication act;
- an implementation label proposed as a particular operating mode.

Write each dependency as a neutral question. Avoid phrasing it as the desired
answer. Identify the claim versions and normalized features affected by the
question so that a later decision can be propagated without re-reading the entire
chart.

## Use intrinsic text before technical intuition

Read the claim, its dependencies, and the specification passages that use the
same term. Look for explicit definitions, consistent examples, contrasts among
neighboring claims, and grammatical actor or timing constraints.

Three outcomes are useful in working notes:

- the intrinsic text resolves the proposition affirmatively;
- the intrinsic text resolves it negatively;
- the supplied intrinsic record leaves a construction dependency.

Reserve the third outcome for a real interpretive dependency. Do not use it where
the text plainly assigns the wrong actor or requires a physical relation absent
from the proposed fact. Conversely, do not convert a recurring embodiment into an
exclusive definition unless the supplied text makes it limiting.

Claim differentiation can expose distinctions but is not an automatic rule. If
neighboring claims separately recite voltage, current, and power information,
that structure is relevant to whether those concepts can be collapsed. Record the
textual contrast and leave legal weight to the requested scope of review.

## Audit an evidence bridge as a chain of premises

A composite inference needs all of these links:

1. the direct record identifies the exact target, version, port, and operating mode;
2. that record reliably invokes the external specification or rule set;
3. the external proposition is mandatory for that identified mode, not optional;
4. the proposition has the same actor, object, channel, and timing as the feature;
5. no supplied record limits the link to a different region, variant, or state.

Classify the link separately from the proposition. A standard may clearly state a
mandatory behavior while the product-to-standard link remains missing. Or the
link may be established while the standard proposition proves only part of a
claim feature.

Use the smallest source combination that closes the chain. Cite the target record
for identity and the reference rule for the mandatory proposition. A citation to
the standard alone cannot establish product identity.

## Do not turn one implemented path into an exclusion

Evidence that a target uses one channel or mechanism generally establishes that
path, not the absence of every additional path. Before treating a different
mechanism as contradictory, test whether the two can coexist in the same product
or mode.

An exclusion needs target-specific evidence such as an exhaustive architecture,
a mandatory prohibition, a mutually exclusive state, or a complete test that
would necessarily observe the claimed behavior. A connector pinout or protocol
label often leaves room for optional or proprietary signaling.

This distinction matters in open-ended method and apparatus claims. A required
feature can be absent from the evidence without being disproved by the presence
of another feature.

## Preserve product modes and variants

Do not generalize a statement across voltage regions, firmware versions, ports,
or operating modes merely because the model number is shared. Build a mode key
whenever the source assigns different capabilities or labels to different
conditions.

For each mode, ask whether the evidence bridge is independently complete. If only
one mode is linked to a protocol, use the reference rules only in that mode. A
claim-level result for another mode remains based on its own record.

## Run one-variable sensitivity analysis

A sensitivity scenario changes exactly the hypothesis stated. Begin with the
record-limited baseline result and its decisive open or incompatible features.
Then:

1. identify the features directly affected by the hypothesis;
2. update only those feature states;
3. leave every unrelated feature unchanged;
4. recompute the all-elements claim result;
5. list the decisive features that remain after the change.

Do not report that an assumption changes the result merely because it improves
one row. It changes the claim result only when the updated row was the last
obstacle, or when it introduces a dispositive contradiction.

Likewise, a hypothesis can change the rationale without changing the terminal
result. Record that as no result change and preserve the remaining decisive
features. This makes the sensitivity matrix useful to counsel deciding which
construction or discovery issue deserves attention.

## Distinguish baseline, hypothetical, and controlling views

Never overwrite the evidence-limited baseline with a favorable hypothetical.
Keep three layers visible:

- baseline: what the supplied target record supports under unresolved mappings;
- hypothetical: the result if the stated premise alone is accepted;
- controlling: the result counsel has instructed the analyst to use, if any.

If no construction has been selected, the baseline remains controlling for the
technical triage. A sensitivity result is not an assertion that the hypothesis is
legally correct.

## Review checks

Before delivery, verify that:

- every construction dependency cites intrinsic text rather than general memory;
- every composite inference contains a target link and a mandatory proposition;
- no standard is used as proof of a product without a supplied bridge;
- no implemented path is treated as exclusive without an exclusion premise;
- modes and variants remain separate;
- every hypothetical changes only its named premise;
- every changed terminal result follows the all-elements rule;
- every unchanged result identifies what still prevents closure.

Stop if the supplied record lacks the claim text, target-mode identity, or the
reference rule needed to test a proposed bridge. Name that missing link instead of
inventing it from industry familiarity or external research.

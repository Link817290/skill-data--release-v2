# Publication and Artifact Control

Use this reference when the assignment contains multiple process stages, structured records, delivery objects, or external access points.

## Close every process transition

Build a transition table before prose:

| From population | Trigger | Activity | Decision rule | To population | Parallel disposition | Time boundary | Channel | Authority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Treat a trigger, main outcome, exception, absence rule, tie rule, shortage rule, review route, and later communication as separate claims. Approval of the main stage does not authorize customary consequences.

For computed decisions, retain:

- named numerator, denominator, reference set, or capacity;
- comparison direction and equality behavior;
- ranking and tie handling;
- rounding only when authorized;
- the population to which the result applies;
- the downstream action.

Test the rule at a value below, equal to, and above its boundary. Also change the population while holding the displayed value constant. If the result should change, the population binding is material and must be published or retained in the operational control.

Trace forward from each entry point until every applicant reaches a defined result. Trace backward from each result to its source population, rule, and authority. Record an open issue when either trace terminates early.

## Control repeated claims

Give each repeated claim one register identifier and list every destination. Update the register first, then propagate the claim. After generation, extract the repeated text or structured value from each destination and compare object, status, number, boundary, and qualifier.

Do not compare sentences only. Two differently worded statements may encode the same controlled claim, while identical phrases may govern different populations.

## Map structured information

For every table, worksheet, form, or interactive record, create a field map:

| Field | Owning object | Meaning | Source | Required status | Display rule |
| --- | --- | --- | --- | --- | --- |

Keep the owning identity visible when a row can move through sorting, filtering, page breaks, print areas, exports, or navigation. Verify headers, merged areas, hidden cells, formulas, validation lists, and blank prompts. A blank field is still a collection request and needs purpose and authority.

When condensing duties, preserve:

1. the action;
2. the object acted upon;
3. the owned outcome, safeguard, or control;
4. any role boundary that prevents responsibility from moving to another position.

Counterexample: reducing "review supplier evidence and authorize release within the assigned category" to "handle supplier work" loses the control outcome and scope. A shorter sentence is acceptable only if those meanings remain recoverable.

## Build the endpoint graph

Represent each public reference as a directed edge from a source surface to one typed endpoint. Endpoint types may include delivered files, authoritative web resources, application services, or approved repositories.

For each edge:

1. Copy the controlled target identity from the manifest.
2. Resolve it to exactly one endpoint of the declared type.
3. Confirm that the endpoint contains or exposes the promised business payload.
4. Confirm that the intended audience can use the access path.
5. Check whether stability, authentication, or timing limits need explanation.

Do not invent a local attachment when the authorized target is external. Do not substitute a similar filename when the requested interface declares a literal identity. Identity and payload are separate checks.

## Transform without corrupting content

Classify each transformation:

- Content transformation changes wording, structure, or operative values and requires claim reconciliation.
- Presentation transformation changes layout and requires render inspection.
- Metadata transformation changes properties or hidden provenance and requires privacy and identity inspection.
- Serialization transformation changes the container encoding and requires parser and transport inspection.

Metadata cleanup or safe reserialization may be acceptable when operative content is unchanged and byte identity is not part of the delivery contract. Conversely, a byte-identical file can still be wrong if its visible identity or promised business role is wrong.

## Handle conflicts and omissions

If a missing operational detail is unnecessary for current applicant action, omit it or name the authorized later channel. If it changes eligibility, timing, submission, review, or disposition, escalate it. Record the unavailable decision, affected transition, safe interim state, owner, and outputs blocked.

Do not fill gaps with common practice. A package may be intentionally less detailed when the missing detail has no authorized basis.

## Synthetic graph check

Suppose a seasonal staffing process publishes roles on a portal, hosts a certification taxonomy on a regulator site, and collects applications through a separate service. A later decision changes one alternative eligibility route.

Update the claim register, test both alternative routes, propagate the change to every repeating surface, and verify the portal edges to the taxonomy and application service. Do not create an extra local taxonomy file or leave the old route in a secondary view. This example tests the method without prescribing an artifact set for another assignment.

# Release Quality Assurance

Use this reference after drafting. Inspect the publication package as claims, relationships, files, and rendered surfaces.

## Use explicit inspection states

Every check must end in one of four states:

- Confirmed: evidence supports the expected condition.
- Confirmed missing: inspection succeeded and the expected item is absent.
- Ambiguous: available evidence supports more than one interpretation.
- Inspection failed: the required surface could not be parsed, opened, reached, or rendered.

Ambiguous and inspection failed are unresolved. They are not evidence that a claim is correct or absent.

## Separate four endpoint layers

Inspect each endpoint independently:

| Layer | Question | Typical evidence |
| --- | --- | --- |
| Identity | Is this the exact requested object or access point? | Name, label, URL, manifest match |
| Payload | Does it carry the promised business content? | Extracted claims, worksheet values, form fields |
| Transport | Does the required container or protocol work? | Signature, parser result, HTTP or service response |
| Presentation | Can the intended audience read and use it? | Render, page image, interactive test |

Do not require a particular binary signature unless the delivery contract specifies that container. An extension by itself does not prove a container, but a compatible application-readable serialization may satisfy a format request when the contract permits it. Record the actual type and the basis for the decision.

Business payload equality is not byte equality. Properties, archive ordering, timestamps, local paths, or safe serialization may differ without changing the operative content. Compare the extracted business model separately from metadata and container structure.

## Inspect structured and narrative outputs

Use both structural extraction and rendering.

For structured outputs:

- enumerate sheets, tables, fields, formulas, validation, hidden content, print areas, and record identities;
- verify each field against its field map and owning object;
- recalculate or independently check derived totals and process formulas;
- inspect rendered pages or supported views for clipping and detached headers.

For narrative outputs:

- extract paragraphs, tables, headers, footers, links, properties, comments, revisions, and embedded objects where supported;
- compare controlled claims by object, logic, boundary, and status;
- render every page and inspect headings, page breaks, signatures, labels, and reference usability.

If a surface cannot be inspected with available tools, record the limitation and its release effect.

## Reconcile claims and relationships

Maintain three ledgers.

1. Claim ledger: source, public claim, object, logic, destinations, and result.
2. Relationship ledger: source surface, reference label, target endpoint, endpoint type, resolution evidence, and result.
3. Inspection ledger: artifact, layer, method, observed evidence, state, reviewer, and issue link.

Run these checks:

- Recompute totals from atomic role or cohort records.
- Compare every repeated claim across destinations.
- Re-evaluate each threshold, ranking, rate, ratio, or capacity rule from its named inputs and reference set.
- Resolve every public reference to exactly one typed endpoint.
- Confirm each endpoint's payload is the one promised by the referring surface.
- Trace each final disposition backward to an authorized transition.

Deduplicate failures by root cause for diagnosis, but preserve every affected destination in the issue record.

## Verify privacy and provenance

Search visible and hidden surfaces for personal data, stale organization identities, comments, revisions, hidden records, local filesystem paths, creator properties, and embedded content. For every retained item, confirm purpose, authority, audience, and necessity.

Do not confuse private provenance with public policy. Retain internal evidence only where authorized and publish only the minimum applicant facing claim or review route.

## Make the release decision

Make the release decision from the issue register, not from a repeated topical checklist. Release only when every issue with a material release effect has a recorded disposition, reviewer, evidence basis, and affected scope. A closed issue must point to the inspection or reconciliation record that resolved it; a topic label or self-declared completion is not closure.

For an authorized exception, record the exact affected object, business impact, approving authority, scope, and expiry or recheck condition. If the available inspection never reached the relevant surface, keep the issue unresolved rather than converting it into a pass.

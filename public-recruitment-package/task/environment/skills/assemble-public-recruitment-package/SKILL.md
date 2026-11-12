---
name: assemble-public-recruitment-package
description: Build and verify a publication ready recruitment package from mixed decisions, governing sources, role records, templates, external resources, and private evidence. Use when eligibility logic, process stages, privacy boundaries, structured outputs, and cross artifact delivery relationships must remain consistent.
---

# Assemble a Public Recruitment Package

Use this method to turn heterogeneous recruitment records into coordinated applicant facing outputs. It applies across employers, role families, jurisdictions, document layouts, and publication channels. It does not prescribe a fixed artifact set or reuse facts from a prior package.

## Create the control records

Before drafting, create four working records.

1. A source authority matrix lists each source, the decisions it may control, its applicable objects and period, its precedence, and any unresolved conflict.
2. A claim register gives each public claim an object, source, authority status, logical type, destinations, evidence need, and privacy status.
3. An endpoint manifest gives each requested output or access point a controlled identity, endpoint type, format or protocol, business function, creation source, and inbound references.
4. An issue register records missing decisions, conflicts, inaccessible sources, failed inspections, owner, and release effect.

Do not treat a polished template, an older publication, or a personal record as authority merely because it contains usable text. Read [Source Authority and Eligibility](references/source_authority.md) when sources overlap, a qualification depends on a governed taxonomy, or a personal record resembles general policy.

## Normalize roles and conditions

Create one role or cohort record for each eligibility object. Bind its identity, capacity, duties, qualifications, preferences, alternative routes, exclusions, evidence, and review owner.

Translate each eligibility sentence into condition atoms before rewriting it. Give every atom:

- an object and scope;
- a status such as mandatory, preference, exclusion, exception, or evidence requirement;
- a comparison operator and boundary when applicable;
- a source and applicability period;
- an owner for ambiguous or unmatched cases.

Represent compound logic explicitly. Cumulative conditions use AND. Independently sufficient routes use OR, while conditions within a route retain their own AND relationships. Keep qualifiers, exceptions, and evidence requirements attached to the atom they govern. A preference must not become a gate, and a review path must not become a promise of acceptance.

When a condition uses a governed professional, licensing, academic, or occupational vocabulary, record the taxonomy name, hierarchy level, affected role, matching rule, and treatment of renamed, ambiguous, or unlisted entries. Verify both membership and scope; a term found somewhere in a directory is not automatically valid for every level or role. Keep the source period separate from the applicant evidence period.

## Model the process as transitions

Represent each approved stage as a transition record:

| Field | Required question |
| --- | --- |
| Entering population | Which applicants or roles enter? |
| Trigger | What event or condition starts the stage? |
| Activity | What happens? |
| Decision rule | Which inputs, reference set, operator, and boundary apply? |
| Resulting population | Who advances, remains pending, or exits? |
| Parallel disposition | What happens to ties, absences, exceptions, or shortages? |
| Time boundary | Which event opens or closes the action? |
| Communication | Where and how is the decision conveyed? |
| Authority | Which source authorizes this transition and each exception? |

For a threshold, rate, ranking, ratio, or capacity rule, write the named inputs, denominator or comparison set, direction, equality behavior, rounding rule if authorized, and downstream action. Test one value below, at, and above the boundary. Similar displayed numbers do not make two rules equivalent.

Trace the graph forward from application through final disposition and backward from every published result to its entering population and authority. This exposes gaps such as an outcome with no authorized trigger, a review with no closure route, or a later stage attached to the wrong cohort.

Read [Publication and Artifact Control](references/publication_control.md) for transition closure, structured outputs, repeated claims, and endpoint relationships.

## Transform controlled content

Draft only from closed claim and transition records.

- Condense duties as action, object, and owned result or control. Remove narrative detail only when scope, responsibility, and outcome remain unchanged.
- Copy controlled identities, dates, values, labels, and cross references from the registers rather than memory.
- Map every structured field to its owning role or cohort. Repeat identifying context when pagination, sorting, filtering, or layout could detach content from its owner.
- Keep mandatory, preferred, alternative, and excluded conditions visibly distinguishable.
- Separate the identity of an artifact from its business payload. A permitted metadata cleanup must not alter operative content; a correct extension must not conceal the wrong container.
- When a missing detail is not needed for applicant action, omit it or identify the authorized later channel. When it is needed, keep the issue open rather than inventing a customary rule.

## Minimize and separate personal data

Build a field purpose ledger for every visible field and hidden data surface. Record purpose, authority, audience, retention need, and whether a less sensitive substitute works. Inspect populated values and blank prompts, properties, comments, revisions, hidden rows or sheets, headers, footers, text boxes, links, and embedded objects.

An applicant record may evidence that person's history. It does not define organization wide eligibility, deadlines, contacts, or policy unless an authorized decision explicitly adopts the fact for that purpose. Remove private evidence from public outputs while retaining only the provenance necessary for authorized internal review.

## Verify endpoints in layers

For each manifest row, verify four independent layers:

1. Identity: the requested name, label, URL, or access point is exact and unambiguous.
2. Payload: the operative business content matches the controlled claims and relationships.
3. Transport: the container, parser, protocol, or external access path works as required.
4. Presentation: the intended rendered or interactive view is readable and usable.

Do not infer payload fidelity from byte identity, and do not infer format correctness from an extension alone. Metadata or serialization may legitimately differ when the business payload is unchanged and the delivery contract does not require byte preservation.

Perform bidirectional reconciliation:

1. Source to output: every authorized claim reaches every required destination with the correct object, status, value, logic, and boundary.
2. Output to source: every assertion and collection field has an authorized source and purpose.
3. Graph closure: every reference resolves to exactly one typed endpoint and every endpoint has its promised payload.
4. Render closure: every delivered surface and required external access path is opened, inspected, and recorded.

Read [Release Quality Assurance](references/release_quality_assurance.md) for inspection states, evidence ledgers, and release decisions.

## Stop conditions

Stop and report the affected record when:

1. a material conflict has no authorized resolution;
2. a required applicant action depends on a missing decision;
3. a governing source or required access path cannot be reached or reproduced;
4. an endpoint fails identity, payload, transport, or presentation verification;
5. private or stale content cannot be removed safely;
6. a forward or backward trace ends without an authorized transition or disposition.

Release only when the registers agree against the same frozen inputs. A complete looking package is not a substitute for closed authority, logic, privacy, relationship, and inspection records.

---
name: work-permit-reconciliation
description: Draft a controlled electrical work permit by reconciling approved plans, circuit drawings and utility rules, with explicit evidence, discrepancy handling and release boundaries.
---

# Work Permit Reconciliation

Use this workflow for utility work-permit drafting, not for operating equipment.
Local rules and authorized field verification take precedence over this method.
This workflow is not an engineering approval, switching instruction or safety certification.
It does not authorize an AI to issue a permit or to replace an authorized reviewer.

## Control The Basis

- Identify the supplied document revisions, job scope, approved work plan and requested
  document stage. A training example is not an approved plan for the present job.
- If an approved plan is supplied, preserve its equipment/actions, installation locations,
  quantities, identifiers, sequence and limits. Do not silently replace it with a plausible
  alternative. Record conflicts and refer them for authorized disposition.
- Do not assume that an unavailable reference contains facts that can be guessed. If the
  supplied sources do not establish a required fact, keep it unresolved rather than inventing it.

## Establish Scope

- Read the scenario before opening examples. Extract the role, employer relationship,
  asset owner, work object, crew, schedule and requested completion stage.
- Separate known facts, facts derived from the drawing, and unavailable information.
- Never invent a contact, system identifier, signature or performed operation.
- Find the controlling selection rules. Do not infer permit category from a sample title.

## Reconstruct The Circuit

- Read both the visual drawing and its text layer; confirm that text extraction has not
  moved a label to the wrong device. Record where each device lies relative to the bus
  and the worksite, rather than merely collecting identifiers.
- Start at the worksite and trace every path to a possible source, including branches.
- Pair each device with its station and intended operation. Distinguish a breaker,
  isolator, earthing switch, transformer and auxiliary secondary circuit.
- Check auxiliary backfeed paths independently of the main power path.
- Treat look-alike numbering as a reason to revisit the drawing, not a naming rule.
- Build a compact path-to-control record: source, intervening devices, isolation action,
  verification location, protective grounding and applicable signage, with source locations.
  A list of device numbers alone does not establish that every source path is controlled.

## Apply The Controlling Rules

- Locate utility requirements for isolation, verification, grounding and signage.
- Convert each applicable rule into an action attached to a specific location.
- Evaluate the circuit both before and after the proposed physical disconnection.
  A protective boundary that disappears after cutting a connection is not sufficient.
- Keep station-side measures distinct from work-crew grounding. Equipment at a distant
  station does not automatically replace protection at the work location.
- Derive the operation sequence from the rules; a list of the right nouns is not a sequence.
- Reconcile each portable grounding set as a record: physical installation point, protected
  work boundary, device type/phase configuration, set count, equipment identifier and source.
  A direction toward another tower is not the same assertion as installation at that tower.
- Never infer that separate phase leads and a combined grounding set are interchangeable.
  Do not substitute a row number for an equipment tag. Retain the supplied identifier mapping;
  if a numbering convention or tag is absent, record the gap for authorized resolution.

## Draft And Bind Evidence

- Organize the permit into business fields. Prefer station-by-station measures that can
  be reviewed independently and that retain the device's name and identifier.
- Reconcile the crew list and total according to the local counting convention.
- Separate preparation-stage obligations from later approvals and execution records.
- For major decisions, record the source document and clause, page or diagram region,
  the fact observed there, and why it applies to this case.
- Cite what the source actually supports; a citation alone is not an explanation.
- Keep a compact decision/evidence/check record in the working process. It need not become
  an extra deliverable when the task requests only a permit. Record results, not hidden reasoning.

## Control Discrepancies And Release

- Classify each unresolved issue by its effect on safe preparation and review. Missing or
  conflicting isolation, grounding, sequence or identifier evidence blocks issue-ready status.
- Continue only the nonconflicting draft work. Mark the unresolved safety fields or draft
  status without recording an operation, signature or approval that has not occurred.
- Request the missing fact or authorized disposition when interaction is available. Otherwise
  deliver only the allowed draft and make the blocking issue visible in the permitted channel.
- A self-check is not an independent review. Identify the required review as pending; do not
  invent a reviewer or simulate sign-off. A plan change requires authorized disposition and
  another affected-path/field check, not an undocumented edit.

## Verify The Artifact

- Reopen the produced document. Confirm that fields, line breaks and device identifiers
  survived export and remain readable.
- Cross-check every possible source path against isolation, grounding and signage.
- Cross-check every grounding location against the physical work boundary and the
  planned change in connectivity; verify unique portable-ground identifiers.
- Check personnel, schedules and unresolved information against the scenario again.
- Keep unresolved drawing or rule ambiguities explicit and request authorized review.
- Compare the exported document against the source-based records, not just strings copied
  from the generation code. Check both omissions and unapproved additions. Reopen the final
  revision after a fix and retain the visible check result and any remaining review blockers.

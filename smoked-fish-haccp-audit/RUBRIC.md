# Scoring rubric

Deliverable: `/workspace/haccp_audit.json`.

## Scoring summary

```text
reward_strict = source_integrity_gate * authorization_decision_gate * sum(weight_i * dimension_i)
reward_lenient = authorization_decision_gate * json_readable * decision_present * findings_present
                 * actions_present * evidence_boundary_present
                 * (recognized_anchor_count >= 8)
                 * (evidence_bound_anchor_count >= 7)
reward = reward_strict
```

The strict lens measures calibrated professional judgment. The lenient lens asks whether
the explicit brief was completed as a usable audit and whether most professional claims
are both recognized and individually traceable. The last two checks reuse strict anchor
evidence, so lenient is not independent of strict. Source-bound semantic judging
recognizes equivalent conclusions and separately checks the adopted authorization decision.
The package contains only the task, source-bound scorer, Golden, and required runtime
materials; runtime metrics and probe records are not scoring inputs or release files.

The source-integrity gate is one when both supplied PDFs retain their issued digests and
zero otherwise. It carries no additive weight. Golden strict and lenient scores are both
`1.0000`; `reward` is the strict compatibility alias. Scores are continuous outputs and
this package defines no passing score.

The authorization-decision gate is one only when the adopted overall decision
keeps this supplied packet unauthorized pending the missing controlled documents,
validation and review. This is the central decision requested by the brief, not
a choice of writing style. An affirmative authorization, a claim that the packet
is already ready, a materially contradictory final decision, or an absent
overall disposition sets this gate to zero for both lenses. Individual findings
remain visible in the diagnostic ledger but cannot compensate for reversing
the decision they must support. Equivalent refusal/defer/revision wording and
conditional future approval with an explicit current non-authorization are
accepted. Merely writing HOLD without substantive findings earns no additional
points; all existing capability and evidence requirements still apply.

## Strict capability dimensions

| Dimension | Weight | Anchor |
| --- | ---: | --- |
| decision_boundary | 0.08 | source location + expert judgment record |
| applicability_hazard_scope | 0.14 | source location + relation |
| botulinum_control_chain | 0.17 | source location + relation |
| process_validation | 0.09 | source location + expert judgment record |
| cooling_control | 0.11 | source location + relation |
| monitoring_limit_alignment | 0.08 | source location + relation |
| corrective_action_closure | 0.08 | source location + expert judgment record |
| verification_calibration | 0.07 | source location + relation |
| distribution_and_storage | 0.06 | source location + expert judgment record |
| postprocess_boundary | 0.04 | source location + expert judgment record |
| evidence_binding | 0.08 | source location + invariant |

### Decision boundary

Capability: preserve the difference between an inadequate authorization packet and proof
of an actual establishment failure. The supplied plan is an illustrative excerpt with
unresolved supporting records and authorization fields. A strong audit issues a clear
hold/revision disposition while limiting claims about implementation and compliance to
what the packet proves.

Verifier signal: the artifact pairs a non-authorization decision with the missing-support
boundary and does not claim observed production failure. Equivalent disposition language
is accepted.

Attention role: connect the dossier's status and blank authorization fields to the scope
of the requested decision; ignore the temptation to treat a published example as a
controlled establishment plan.

### Applicability and hazard scope

Capability: recognize that the generic product description does not supply the species,
source, product-form, and hazard-analysis decisions needed to close species-dependent
hazards. This includes holding open toxin-at-receipt analysis for susceptible species
rather than assuming frozen receipt or a later cook closes it.

Verifier signal: separate credit is awarded for the unresolved product/hazard-analysis
scope and for the conditional receiving hazard. The conclusion must remain conditional
where the discriminator is missing.

Attention role: connect the generic scope in the plan table to the species and process
routing instructions in the current control reference.

### Botulinum control chain

Capability: identify reduced-oxygen refrigerated smoked product as requiring an explicit
organism-specific barrier chain. The plan's generic pathogen description, brining input,
drying schedule reference, heat step, and refrigeration must be tested as linked but
non-interchangeable controls.

Verifier signal: credit requires both recognition of the target hazard and the failure to
demonstrate the formulation/drying endpoint through either direct monitoring or a supplied
scientific process establishment.

Professional identities are preserved when judging equivalent language. The target
organism must unambiguously be *Clostridium botulinum* (including `C. botulinum`),
with the relevant type A/proteolytic B and F versus type E/nonproteolytic B and F
distinction; a generic pathogen or a different organism is not an equivalent. The formulation endpoint is finished-product
water-phase salt (`WPS`), including a precise definition of that same aqueous-phase
concentration. Whole-product total salt and brine strength are different quantities.
A correct anchor ID or WPS statement in a different periodic-verification finding
cannot rescue an adopted wrong endpoint for process establishment. These distinctions
come from the unchanged supplied authority and Golden, not added task requirements.

Attention role: connect packaging atmosphere, smoke process, product inhibition, heat
damage, and refrigeration; ignore the complete-looking table cells when the support is
outside the packet.

### Process validation

Capability: distinguish validation from periodic verification. The cited schedule and
notes are not supplied, while the current authority conditions a recipe-based strategy on
a scientific study covering all critical factors. Periodic product checks cannot establish
an absent scheduled process.

Verifier signal: one score component tests the missing schedule/study boundary; another
tests whether the annual finished-product check is treated as inadequate support for the
proposed control unless a justified alternative is supplied.

Attention role: connect the plan's cross-references to the authority's process-
establishment and periodic-confirmation requirements.

### Cooling control

Capability: distinguish a cold-room setpoint from the cooling behavior of the warmest
product. The plan monitors ambient room temperature but supplies neither direct product
cooling data nor validated critical process factors.

Verifier signal: the finding must identify the measurement mismatch and request either a
worst-case product profile or a matching cooling study/process-factor strategy.

Attention role: connect heat-flow direction and product geometry to the monitoring
location; ignore a continuously recorded ambient value as automatic proof of product
cooling.

### Monitoring-limit alignment

Capability: test whether every limit in a referenced scheduled process is measured by the
stated instrument. The heating row names final time and center temperature but does not
show how the chart recorder measures both or where the product sensor is placed.

Verifier signal: credit requires a bounded evidence-gap finding and an action that closes
the instrument/parameter/worst-case product relation. The verifier does not require a
specific instrument brand or wording.

Attention role: connect the critical-limit parameter to the `what` and `how` cells rather
than accepting column completeness.

### Corrective-action closure

Capability: require both safe product disposition and restoration of process control.
The plan repeatedly stops at hold/evaluate, reprocess, adjust, or relabel language without
supplying evaluation authority, supported disposition criteria, cause correction, or a
lookback window.

Verifier signal: credit requires product and process tracks, including recognition that
relabeling cannot remedy product already exposed outside a limit.

Attention role: connect each vague action to the hazard and affected lot; ignore verbs
that sound decisive but do not close release safety.

### Verification and calibration

Capability: distinguish record review, functional recorder checks, accuracy checks, and
calibration. The excerpt includes some review frequencies but does not define the recorder
check or calibration/evaluation procedure.

Verifier signal: the audit must credit the stated record review while identifying the
unresolved instrument-control chain and the need for affected-record evaluation after an
out-of-tolerance result.

Attention role: connect verification labels to the actual activity and consequence.

### Distribution and storage

Capability: credit a conservative continuously monitored in-house storage setting while
rejecting a label check as proof that the described distribution exposure stayed under
control.

Verifier signal: the artifact must avoid falsely criticizing the safer storage setting
and must distinguish labeling from exposure evidence during distribution.

Attention role: connect each control to the segment of the chain it can observe; ignore
the intuitive but false equivalence between warning text and temperature control.

### Post-process boundary

Capability: avoid inventing a CCP merely because post-process contamination is possible.
The supplied excerpt does not contain the hazard analysis, sanitation controls, or
implementation records needed to determine the control system.

Verifier signal: the result preserves the issue as unassessable from the packet and asks
for the relevant hazard-analysis and sanitation evidence rather than declaring an omitted
CCP violation.

Attention role: ignore a generic “more CCPs is safer” heuristic and route the hazard to
the documented control system.

### Evidence binding

Capability: make each recognized conclusion independently reviewable. Each credited
finding must carry a valid location in the PDF that supports the plan fact or control rule;
a document title alone is insufficient.

Verifier signal: this dimension is the proportion of recognized substantive claims whose
individual finding records contain an accepted dossier or control-reference page location.
Field names, finding order, nesting, and prose structure are not scored.

## Lenient brief compliance

The binary lenient score is one only when the same artifact is readable JSON, states an
overall authorization disposition, contains discrete nonempty findings, provides at least
one concrete corrective recommendation, explicitly marks an evidence limitation or
not-determinable issue, recognizes at least 8 of the 13 professional anchors, and binds at
least 7 anchors to accepted page-level evidence. Disposition, corrective-action, and
evidence-boundary checks use the source-bound semantic judge and accept equivalent
professional wording rather than a fixed vocabulary. The two coverage checks use the
strict reference set; the remaining checks are delivery-shape checks.

## Anchor policy and accepted variation

Every substantive check is tied to a page in an agent-readable PDF and to a written
expert rationale describing the accepted boundary. The verifier resolves findings by
their meaning within one finding record, not by key name, list order, section title, or
gold prose. Equivalent professional terms, reordered findings, renamed fields, and
different JSON nesting are accepted. Unsupported certainty, a citation detached from the
claim, or a page number dumped elsewhere is not.

## Skill-attributable method

The evidence-state ledger and control-chain decomposition support decision boundary,
validation, corrective-action closure, and evidence binding. The seafood product-hazard
profile and barrier analysis support applicability, organism-specific controls, cooling,
heating, storage, distribution, and post-process boundaries. These are observable in the
substance and traceability of the final artifact, never in whether a skill was opened.

## Failure modes and anti-gaming

Common failures are filling missing species or process evidence from memory, treating an
illustrative table as implementation proof, accepting ambient temperature as product
cooling, merging validation with verification, and proposing an extra CCP without first
testing the control system.

The verifier is tested against synonym rewrites, renamed/reordered structures, empty
delivery, keyword stuffing, numeric and page-number shotgun text, source dumping, a
complete-looking blind stub, and source mutation. None of the stubs can obtain material
strict credit or a lenient score. A method-equivalent variant of the gold artifact retains
both full scores.

## Known limits

This package evaluates a bounded desk review of the supplied excerpt. It does not measure
site inspection, sensory examination, laboratory technique, plan execution, or the legal
status of an establishment outside the supplied record.

2026-10-24: Evaluate complete findings, including nested evidence and corrective-action lists. Explicit document-ID mappings are resolved for both lenses. Targeted meaning is judged from the supplied sources with exact candidate evidence. Evidence-binding denominator is recognized substantive findings, so missing findings lose their own content credit without a second binding loss. Finding length is not a scoring contract. Judge unavailability aborts scoring.

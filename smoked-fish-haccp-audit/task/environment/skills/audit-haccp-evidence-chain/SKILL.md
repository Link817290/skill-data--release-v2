---
name: audit-haccp-evidence-chain
description: Use before opening source files to audit an existing HACCP plan, hazard analysis, or verification packet for technical adequacy and authorization readiness. Connect hazards to controls, limits, monitoring, corrective actions, verification, and evidence without mistaking an example, assertion, or missing record for proof.
---

# Audit a HACCP Evidence Chain

Treat this runtime method as separate from the practitioner evidence set. It is not a
source record and cannot support a factual or compliance conclusion.

Use this method for a desk review of an existing plan or implementation packet. It is
not a plan-writing template and it is not a substitute for process authority or a site
assessment.

## Start with Text-Only Source Access

When a PDF contains embedded searchable text, do not invoke an image or PDF rendering
tool. Use text extraction so the review remains available in text-only runtimes. For a
long document, run the bundled page search helper from the base directory reported when
this skill is loaded:

```bash
python scripts/pdf_page_search.py --pdf DOCUMENT.pdf \
  --query "concept terms" --query "alternative vocabulary"
```

The helper returns PDF page numbers and bounded text snippets. Use `--extract-page` for
a small set of already identified pages. Treat search hits as navigation leads, not
evidence or conclusions; inspect relevant context before recording a claim.

## Set the Audit Boundary

Before evaluating a control, write down three boundaries:

1. Identify the product, process, packaging, intended use, consumer, storage, and
   distribution scope actually described by the supplied record.
2. Identify the decision being requested: document adequacy, authorization readiness,
   implementation evidence, or effectiveness. Do not silently promote one decision to
   another.
3. Identify the governing material in the packet and its status. Separate a current
   requirement, nonbinding guidance, scientific support, illustrative model, and the
   establishment's own controlled document.

Stop an applicability conclusion when the record does not define the product or process
feature on which the conclusion depends. Record the missing discriminator and its effect
on the decision. Do not fill it from general knowledge.

## Build a Source-State Ledger

Create a working ledger before drafting prose. Use one row per material claim, not one
row per document.

First enumerate every plan row and every cross-cutting applicability question revealed
by the product profile. Put that inventory in a scratch ledger outside the requested
deliverable. Do this before deep source reading so that a long authority document does
not displace an unresolved audit unit from working memory. Update the same ledger after
each unit; do not rely on a narrative note assembled only at the end.

For each row capture:

- the claim being tested;
- the plan element and process step;
- the precise source location;
- the source's role and authority;
- the evidence state;
- the consequence for authorization;
- the next evidence or revision needed.

Use these evidence states as reasoning controls:

- **documented**: the supplied record directly contains the needed fact;
- **referenced-not-supplied**: a note, schedule, study, or procedure is named but absent;
- **ambiguous**: the text supports more than one materially different reading;
- **conflicted**: two supplied records assert incompatible states;
- **not-applicable**: the record establishes that the rule's trigger is absent;
- **not-determinable**: the trigger or support needed for a conclusion is missing.

An assertion that a record exists is not evidence of its contents. A title such as
"process schedule," "validation," or "calibration check" cannot be credited until the
record supplies the parameters, scope, result, and approval state needed for the claim.

Persist the ledger while reviewing. Add the source location at the moment a conclusion
is made. A conclusion without a location remains a draft.

For a long authority, queries must come from the current audit unit and product-hazard
profile. Record a hit's source role in the ledger only after inspecting its page context.

## Decompose the Plan into Control Chains

Treat each significant hazard as a separate audit unit. Follow it through this chain:

```text
product/process trigger
  -> hazard significance decision and rationale
  -> control measure
  -> CCP placement
  -> critical limit
  -> monitored parameter and method
  -> frequency and responsibility
  -> deviation response for product and process
  -> records
  -> validation and ongoing verification
```

Do not give a row credit merely because every table cell is filled. The links must close.
For example, a monitored parameter must either be the limit itself or be a validated
surrogate whose relationship to the safety outcome is supplied.

When one hazard uses several barriers, audit the barrier chain as a whole and then each
barrier separately. Determine which barrier controls which organism or failure mode.
Do not let a strong barrier for one target stand in for a different target.

## Audit Hazard Significance Before CCP Detail

Test the hazard analysis in this order:

1. Confirm that all product and process discriminators needed by the supplied hazard
   reference are known.
2. Identify hazards introduced, increased, controlled, or able to recur at each step.
3. Confirm that a "not significant" decision includes reasoning tied to actual controls
   or conditions, rather than a generic statement.
4. Check whether control is located at the step where it can actually be exercised.
5. Revisit earlier significance decisions when later material reveals a different
   packaging state, intended use, species, formulation, or exposure condition.

Do not infer that every recognized hazard requires a CCP. Some hazards are appropriately
managed through prerequisite or sanitation controls. The audit question is whether the
chosen system provides an effective, documented control, not whether the table contains
the largest possible number of CCPs.

## Distinguish Limits, Targets, and Evidence

Keep four concepts separate:

- A **critical limit** marks the safety boundary at a CCP.
- An **operating limit** provides process margin before that boundary is reached.
- A **process parameter** is a controllable input or condition.
- A **product outcome** is the state the process is intended to deliver.

A miss against an operating limit is not automatically a critical-limit deviation.
Conversely, an operating target does not prove the safety boundary was met.

For every critical limit ask:

1. What safety outcome does it protect?
2. Where does its value come from?
3. Is its product and equipment scope the same as the plan's scope?
4. Are all critical factors that make the limit effective identified?
5. Is each factor monitored directly or supported as a reliable surrogate?
6. Does the record preserve actual observations rather than only a yes/no conclusion?

If a plan points to an external schedule or study, keep the adequacy decision open until
that support is supplied and matched to the product, equipment, loading, and worst-case
conditions.

## Separate Validation from Verification

Use the following distinction consistently:

- **validation** asks whether the designed control can control the identified hazard;
- **verification** asks whether the validated plan is being implemented and remains
  effective;
- **monitoring** observes the CCP in time to recognize loss of control;
- **record review** checks that monitoring and response records are complete and acted on.

Do not accept periodic finished-product testing as a substitute for an unvalidated
process unless the supplied authority explicitly makes testing the monitoring strategy.
Sampling may miss nonuniform failures and normally does not show what happened to every
lot.

For instruments, distinguish an operational check, an accuracy check, and calibration.
Audit frequency, reference standard, acceptable error, out-of-tolerance evaluation, and
the affected-record lookback. A bare word such as "check" does not establish these.

## Test Monitoring as a Measurement System

For every CCP, complete the following test:

1. **What:** the parameter that establishes control.
2. **How:** an instrument or observation capable of measuring that parameter at the
   required point and range.
3. **Where:** a location representing the worst credible unit or condition.
4. **When:** continuous or frequent enough to detect meaningful variation.
5. **Who:** a role with authority and a defined response.
6. **Record:** actual value, time, lot, observer, and review evidence as applicable.

An ambient reading is not automatically a product reading. A chamber recorder is not
automatically an internal-product measurement. A label check is not automatically
control of the exposure described on the label. Credit a surrogate only when its link to
the safety outcome has been established for the actual process.

## Test Corrective-Action Closure

Audit predetermined corrective action on two tracks.

**Product track**

- define the affected lot and time window;
- segregate or otherwise control it;
- evaluate safety using a named basis;
- document a disposition that prevents unsafe release.

**Process track**

- regain control of the CCP;
- identify and correct the cause;
- address recurrence where required;
- document the action and trigger reassessment when the event reveals a plan weakness.

Words such as "evaluate," "adjust," or "reprocess" are incomplete if the record does not
say who decides, by what basis, and what disposition follows. Do not invent those missing
steps. State the closure gap.

## Separate Design Evidence from Implementation Evidence

A plan table can support conclusions about its written design. It cannot prove that
operators followed it, instruments were accurate, deviations were handled, or product was
released appropriately.

Use implementation language only when the packet includes actual completed monitoring,
corrective-action, verification, and review records for the period at issue. Otherwise
state that implementation and effectiveness are not determinable from the supplied
record. Do not turn absence of evidence into evidence of a violation.

Likewise, blank signature or revision fields in an illustrative or uncontrolled copy may
show that the supplied copy is not authorization evidence. They do not by themselves
prove that no signed controlled version exists elsewhere.

## Rank Findings by Decision Effect

Prioritize findings by their consequence, not by table order:

1. **Authorization blocker:** the hazard/control chain cannot be shown adequate, the
   product scope is unresolved, or required support is absent.
2. **Control-system weakness:** a link is present but cannot reliably detect, respond to,
   or verify loss of control.
3. **Documentation gap:** the underlying control may be adequate, but the supplied record
   does not demonstrate it.
4. **Observation:** a control is supported or a proposed improvement is not required for
   the requested decision.

Explain whether a finding requires plan revision, supporting evidence, operating records,
or a site check. Avoid declaring the establishment compliant or noncompliant when the
review only covers a document excerpt.

## Close the Audit

Before delivery:

1. Reconcile the initial inventory row by row. Every plan row and every product-hazard
   trigger must end as supported, deficient, not applicable, or not determinable.
2. Confirm that each finding cites a source location that actually supports it.
3. Remove duplicate findings that charge the same broken link twice.
4. Check that positive controls are credited as well as weaknesses.
5. Re-read all "not-determinable" items and ensure no later evidence resolved them.
6. Compare the overall decision with the blocker findings.
7. Confirm that requested actions identify the missing evidence or control change, not a
   generic instruction to "update HACCP."
8. Keep supplied materials unchanged.

Stop when every authorization claim is either supported, explicitly bounded, or held
open. Do not manufacture certainty to make the report look complete.

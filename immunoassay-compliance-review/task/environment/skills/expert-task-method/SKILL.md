---
name: expert-task-method
description: Evidence-led methodology for independent review of in vitro immunoassay workbooks when protocol rules, validation statistics, system suitability, analytical runs, formulas, cached values, and manual dispositions must remain traceable without inventing acceptance criteria.
---

# Evidence-Led Immunoassay Compliance Review

Use this method when an immunoassay review must connect element-level data,
calculation logic, manual annotations, and final dispositions. It is not a
basis for clinical interpretation or for adding acceptance rules that are
absent from the governing documents.

## Choosing a calculation path

This skill includes a working [Python 3 calculator](scripts/calculate.py), with
no third-party dependencies. Before arithmetic becomes another handwritten part
of the workbook reader, consider whether an existing operation already matches
the quantity and precision convention. Reusing it leaves the custom code focused
on extracting and identifying observations rather than maintaining a second
implementation of the same calculation.

The [calculation interface](references/calculation-interface.md) explains file,
stdin, and Python usage with synthetic inputs. The tool accepts observations,
not workbook paths: extraction and admissibility remain review judgments.
An interface inspection establishes availability, not a recalculation. What
input-to-result record would show that a relevant operation actually contributed
to this review? If none fits, what specific mismatch justifies a custom path?

## The evidence-to-decision frame

Think of the workbook as a dependency system:

```text
governing rule
  -> admissible validation population
  -> global thresholds and correction factors
  -> system-suitability limits
  -> analytical-run decisions
  -> review disposition and evidence
```

A downstream conclusion cannot be more certain than the upstream evidence on
which it depends. A later finding that changes an admissible set, factor, or
label relationship should reopen the affected downstream conclusions rather
than coexist with them silently.

## Review units and closure

The natural review units are the validation population, each material global
metric, each system-suitability limit, each normalized analytical run, and each
material discrepancy. A closed unit has a recognizable rule basis, admissible
input set, independent result, source comparison, disposition, uncertainty
state, and resolvable evidence anchor.

A conclusion that exists only in analysis remains open. The durable review is
the deliverable itself. Breadth therefore precedes marginal depth: an explicit
state for every required unit is more valuable than perfect detail for early
units and silence for the remainder. Where evidence is genuinely insufficient,
`PENDING` preserves both honesty and closure.

The workbook should become one stable, reusable map rather than a sequence of
isolated discoveries. Repeated inspection of the same structure is a signal to
ask whether the representation is incomplete or whether the evidence is
already sufficient.

Would the current saved report still convey the settled findings if execution
ended now? A copied template or a private calculation does not preserve those
findings for the recipient. Unresolved units need not delay saving resolved ones.
What is the smallest settled unit that could already stand in the deliverable?
Treating all writing as one final phase leaves even completed calculations
unavailable to the recipient; task-tracker progress does not change that boundary.

## Evidence sufficiency

For each material conclusion, consider:

- Are sample, replicate, dilution, treatment, validity, and exclusion labels
  aligned well enough to identify the true calculation unit?
- Is the admissible input set explicit, including the reason for any exclusion?
- Can raw values, formulas, cached values, manual annotations, and summary
  fields be told apart?
- Would another inspection plausibly change the result or disposition, resolve
  a discrepancy, or supply a missing anchor?
- Could another reviewer reproduce the conclusion from the cited evidence
  without relying on the workbook's displayed summary alone?

Evidence is sufficient when those questions are settled for the required
decision. Additional detail that changes none of them has diminishing review
value.

Which labels establish each block's identity and extent? Adjacent panels need
not describe the same run, and similar-looking blocks need not have equal
lengths. Could each citation travel with its identified observation all the way
into the report, rather than being reconstructed from row position or memory?
If a summary omits a run, is its evidence absent, or only its summary entry?

## Calculation integrity

Confidence in a recalculation comes from the entire chain, not only the final
number. The meaningful comparison includes input membership, pairing, formula
references, intermediate precision, correction-factor provenance, rounding
order, source value, and independently obtained value.

Validation statistics should be based on the declared valid population.
System-suitability limits should preserve their intended direction, degrees of
freedom, and t-critical convention. Paired calculations remain valid only while
sample identity, treatment state, and control relationships remain intact.

An agreement caused by a stale cached value, a historical factor, or shared
rounding is not the same as an independently verified match. Conversely, a
small displayed difference is not material until the unrounded chain and the
applicable comparison convention have been considered.

Before a small mismatch becomes a claimed source defect, could it arise in the
review's extraction, pairing, or arithmetic? A half-unit boundary deserves
particular scrutiny: rounding an already perturbed binary intermediate cannot
recover the intended decimal value. Does the chosen numerical path preserve
the source convention from the observations onward, including custom calculations
outside the packaged tool? The interface reference describes the limited
`rounded_mean` operation for an explicitly chosen decimal mean convention.

What does an audit count actually count: stored formula records, expanded
calculation instances, or independently recomputed comparisons? Shared formulas
can represent more calculations than the explicit formula text suggests. A
credible coverage claim distinguishes inspected, recomputed, matched, different,
and unresolved items; counting formula cells alone does not establish agreement.

## Decision integrity

Keep three decision planes distinct:

- `objective_status`: what the supplied criteria and admissible element-level
  evidence support;
- `source_status`: what the workbook records through rejection, exclusion,
  removal, out-of-control language, or other manual disposition;
- `PENDING`: what the available rule or evidence cannot decide.

Manual status may explain why data were handled a certain way, but it does not
become an objective failure criterion by repetition. Likewise, an observed
statistic should not become a rejection rule merely because it looks unusual.

Are the requested status fields present in the source, or are they conclusions
the review must derive? Their absence as literal column names need not mean the
underlying evidence is unavailable. What supplied criterion connects individual
comparisons to a run disposition? Neither one adverse comparison nor the absence
of one answers that question without the applicable admissibility and acceptance
conditions. After exclusions, does the remaining evidence still support those
conditions? A missing criterion is a reason for uncertainty, not an invented rule.

How narrowly can that uncertainty be located? An unresolved overall disposition
need not erase an established element comparison, exclusion, input count, or
numerical finding. Which parts are supported, which exact missing premise blocks
the remaining inference, and which additional evidence would settle it? Conversely,
local numerical agreement does not justify filling an unsupported overall status.

When that distinction is unresolved,
[review reasoning](references/review-reasoning.md) explores evidence sufficiency,
element-level exceptions, and the authority of run-level conclusions.

Historical factors call for impact boundaries. Their presence in a downstream
formula does not imply that independently established global metrics or
unrelated suitability limits are affected. The review should distinguish the
fields that inherit the factor from those that do not.

## Coherence across a long review

The same admissibility and status conventions should govern every comparable
unit. A later discovery matters beyond its local sheet when it changes an
upstream premise; otherwise it should not trigger wholesale re-analysis.

A coherent deliverable makes its coverage visible, binds conclusions to
evidence, reconciles the inventory with the reported units, and leaves no
unspoken gaps. Reusable anchors may support related conclusions without being
duplicated. Completion means that required units are either closed or openly
pending, not that every cell has been explored.

Could the table, narrative totals, and evidence index be views of the same
identified review records? Independently composing them invites disagreement
after a status changes. An unreviewed unit is not a passing unit merely because
it is absent from a failure list.

In the saved artifact, does each value still sit under the intended heading,
with its metric identity, unit, disposition, and evidence intact? Matching the
number of columns is necessary but not sufficient: a well-shaped row can still
attribute another run's evidence. A final consistency judgment concerns the
persisted content, not only the data or intentions used to compose it.

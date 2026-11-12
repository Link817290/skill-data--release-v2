# Scoring Rubric

This rubric is derived from the supplied residential floor plan DXF, the supplied fire safety code PDF, and the reference handoff. The evaluator reads the submitted output directory together with the supplied source files, and judges the substance of the inspection, the plan-view repair, and the evidence binding them; it does not score trajectory prose, skill invocation, wording, or presentation order.

## Score Form

```text
strict = positive_earned * retention
         positive_earned = sum over the positive items of (weight * completion)
         retention       = product over damage instances of the smallest
                           coefficient among the deduction items in that instance
```

Weights and coefficients are read from `tests/scoring_params.json`. The result is a continuous value in `[0,1]`, reported as `reward` and `rewards.strict`. The independent binary lenient lens passes only when the source files remain intact, the route-width finding is supported, the proposed DXF geometry reaches the required width and agrees with the JSON polygon, and the door clear-width and swing limitations are both carried as correctly bound holds.

Each positive item is one pass/fail check, so its completion is 0 or 1, except P10, which bundles four independent bindings and reports their mean. A reversed conclusion loses the judgment and cross-file closure items that carry that conclusion; it does not erase independently demonstrated geometry, source evidence or file integrity.

A submission that omits or leaves empty any of the eight requested deliverables, whose JSON or memo cannot be parsed, whose repaired DXF cannot be read, or for which the supplied source drawing cannot be read, takes 0 completion on every item and scores 0.

## Scoring Dimensions

Each item is one positive item of one of the four dimensions — inspection judgment, geometry repair, evidence closure, artifact integrity. Weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| P01 | Inspection judgment | `F-HALL-WIDTH` reads as non-conforming and carries, in its own fields, the observed route clear width (1.016 m, 40 in), the 1.1 m route minimum it is compared against, a disposition that moves the boundary, and both supplied source files | `violations_before.json`, `inspection_report.json` | 0.07 | Domain judgment |
| P08 | Geometry repair | The repaired drawing carries a note, new to it, about the door operation that reads as a review hold, with the source entities retained | `repaired_plan.dxf` against the supplied drawing | 0.09 | Domain judgment |
| P09 | Evidence closure | Both thresholds are bound to the code: `fire_safety_code.pdf` cited with clause 5.5.30 or physical page 61, the 1.1 m route minimum is applied to the route, and the 0.90 m door threshold is recorded as a conditional comparison pending confirmation of door classification and effective clear width | `inspection_report.json`, `repair_memo.md`, `changes.json` | 0.09 | Evidence binding |
| P10 | Evidence closure | Four bindings, scored as their mean: drawing evidence cited beside `residential_floor_plan.dxf` (a source entity handle, the HALL label anchor, or a recorded wall-face coordinate); the native and converted units of the route or the door shown together; the fixed identifiers repeated across the records; and the layer inventory naming and counting the source layers | All requested records | 0.04 | Evidence binding |
| P12 | Evidence closure | The change log carries a route row bound to `HALL-ROUTE-01` with its original 1.016 m width and its actual repaired width at or above the 1.1 m minimum, and a door row bound to `HALL-DOOR-01` that reads as a hold, so confirmed repairs are distinguished from what remains for coordination | `changes.json` | 0.09 | Multi-step reasoning/self-checking |
| P13 | Evidence closure | The memo's route section carries both clear widths and a move disposition, the door section distinguishes the plan opening line from verified clear width and keeps the classification/clear-width conclusion on hold, and the swing section carries its separate hold | `repair_memo.md` | 0.09 | Domain communication |
| P16 | Artifact integrity | The recorded original clear width, the repaired clear width, and the change log's before and after agree pairwise, and the repaired width is not the original one | `extracted_original_layout.json`, `repaired_layout.json`, `changes.json` | 0.07 | Multi-step reasoning/self-checking |
| P21 | Geometry repair | A local route boundary reaches the required width, overlaps the original HALL, retains its lateral extent, and preserves the north face or documents necessary linked coordination | `repaired_layout.json` | 0.09 | CAD geometry |
| P22 | Geometry repair | The closed local DXF boundary preserves the north face or documents necessary linked coordination | `repaired_plan.dxf` | 0.09 | CAD geometry |
| P27 | Geometry repair | The local drawn boundary reaches at least 1.1 m clear width, in either justified repair direction | `repaired_plan.dxf` | 0.09 | CAD geometry |
| P23 | Geometry repair | The drawn repair boundary and the repaired room polygon are the same rectangle within CAD tolerance | `repaired_plan.dxf`, `repaired_layout.json` | 0.08 | Self-checking |
| P28 | Artifact integrity | The recorded original room carries the HALL label anchor at (-368.741, 151.037) | `extracted_original_layout.json` | 0.09 | CAD geometry |
| P26 | Inspection judgment | The inspection report carries a substantive overall decision that identifies the route-widening coordination concept and the unresolved door evidence | `inspection_report.json` | 0.02 | Domain communication |

The positive allocation gives 44% to plan-view geometry (P08, P21, P22, P23
and P27), because the principal repair must exist in both DXF and JSON and reach
the code width. Evidence closure carries 31% (P09, P10, P12 and P13) so a drawn
shape cannot pass without threshold, unit, identifier and unresolved-door
bindings. Source/artifact integrity carries 16% (P16 and P28), and inspection
judgment carries 9% (P01 and P26). This keeps geometry central while reserving
more than half the score for the professional evidence trail and source-bound
decision that make the CAD change reviewable. The shares do not impose a pass
threshold or force a preferred drawing direction.

### Accepted equivalent expressions

A record's disposition is read for its meaning, not its wording, and a hold outranks a failure, which outranks a pass.

- Failure: non-conforming, non-compliant, in violation, deficient, fails, insufficient, undersized, below the minimum, less than, does not meet, too narrow, must be widened or enlarged.
- Pass: complies, conforms, meets, satisfies, acceptable, adequate, retained, kept, unchanged, no change, as drawn, remains, above the minimum, exceeds, resolved, confirmed.
- Hold: hold, on hold, unresolved, cannot be determined, does not establish, pending, awaiting, to be confirmed, TBC, TBD, unverified, requires coordination, outstanding, left open, remains for coordination.
- Regular `-s`, `-es`, `-ed` and `-ing` inflections of these words read the same as the base word.
- A cue that is denied just before it is used does not count: "no further review is needed" is not a hold, and "no widening is called for" is not a failure.
- A disposition written as an enum value reads like the same disposition written as prose, because `_`, `-` and `/` are treated as word breaks before any cue is looked for.
- Identifier field names are free. Any key ending in `id` carries an identifier, so `finding_id`, `record_id`, `element_id`, `route_id` and `id` are the same declaration, and the change log need not be grouped into sections named as the reference names them.
- Quantities may be written in metres or in the drawing's native inches, and a minus sign typeset as U+2212 or as a dash reads as an ordinary minus. Coordinates and lengths are matched to 0.18 drawing units, metric declarations to 0.06 m.
- In the memo, a heading and the bullets under it are read as one block belonging to the item the heading names, so a wrapped bullet stays whole and a door paragraph is not read into the route block.

### Target identity and independent evidence

`HALL-DOOR-01` must bind one explicit handle that exists in the locked source DXF. The instruction does not designate a unique handle; separate identifier, HALL-location evidence, opening measurement and scope checks establish that the selected source object is the door under review. The finding must use that handle consistently and hold the compliance conclusion pending classification plus jamb, leaf, hardware and operation evidence.
The door and swing findings must bind the same admissible source opening before P08/P09/P12/P13 can receive
credit. D09 also detects wrong object binding and inconsistent opening units.
Judgement reversals lose their own judgement checks; they do not scale unrelated
geometry, source evidence and file-integrity items to zero.

## Deductions

Each damage instance multiplies the score by its coefficient.

| Item | Error | Damage instances | Coefficient | Rationale |
| D01 | A locked source file no longer matches its recorded digest | once | 0.1 | The supplied originals are the evaluator's independent anchors and must stay unchanged |
| D02 | A north-face relocation without documented necessary linkage/impact coordination and a correctly bound swing hold | once | 0.9 | Unexplained adjacent impacts are unsupported |
| D05 | No closed repair boundary was added to the DXF | once | 0.6 | Reissuing the source drawing is not a plan-view repair |
| D08 | A repair polygon lying wholly outside the HALL | once | 0.5 | Design changes are confined to the first-floor HALL egress geometry and its immediately affected door operation |
| D09 | Wrong target-door binding, inconsistent 36 in/0.9144 m plan-opening units, or a plan span represented as a different measured quantity | once, however many records | 0.7 | The record must identify the opening actually adjacent to the route and preserve what the supplied drawing does and does not establish |
| D11 | Geometry added on a new layer whose name does not begin with `REPAIR-` | once, however many layers | 0.7 | The record conventions fix where added geometry is drawn |

Interactions with the dimensions:

- D01 also reports the four dimension scores as zero. If the source drawing cannot be located or read at all, nothing is scored and the submission takes 0.
- D05 is decided on the same repair boundaries the geometry items read, so a submission that adds nothing closed loses P22, P27 and P23 as well as taking the deduction.

## Anti-gaming boundaries

Numbers or target phrases in an unrelated section do not substitute for the corresponding record: a measurement is read only from the finding or the record bound to the identifier it belongs to, a width is not read from a requirement field, another opening, or a face coordinate stored inside a width, and a hold counts only when it is an argued limitation about the opening in question while the other two findings still carry a decision. A report that repeats the source text without a measured route, a drawn boundary and linked dispositions receives only the structural share it actually demonstrates.

Field aliases and column/row JSON tables normalize to the same finding records; memo
Markdown table rows are read separately. The target opening must be named consistently
across the submitted records and must resolve to an opening entity in the locked source
drawing. Nearby openings and their dimensions are independent source objects and do not
establish the selected target's plan span, effective clear width or classification.

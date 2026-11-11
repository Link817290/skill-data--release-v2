# Scoring Rubric

This rubric is derived from the two immutable workspace records — `materials/每日供需.csv` and
`materials/機組發電.json` — and from the three deliverables the minutes fix: `output/dispatch_review.json`,
`output/dispatch_trace.csv` and `output/dispatch_model.py`. The validator reads both records, independently
reconstructs the in-scope gas unit register and the latest fourteen dated records, recomputes the stress
profile, the plant adjustment envelopes and the per-step dispatch bounds, and reruns the submitted program
in a clean workspace. Scoring evaluates facts and relations: unit conversions,
time relations, bounds, balances, and source-bounded operational meaning. JSON
key order, trace row order, float formatting, and synonymous Traditional Chinese
expression do not affect credit. P15 and P17 are decided by a source-bound LLM
judge with cited candidate and source units; keyword presence cannot award them.

## Score Form

```text
strict = positive_earned * retention
         positive_earned = sum over the seven positive items of (weight * completion)
         retention       = product over damage instances of the smallest
                           coefficient among the deduction items in that instance
```

Weights and coefficients are read from `tests/scoring_params.json`. Each item's completion is the share of
that item's underlying checks that the deliverable satisfies (0 to 1). A binary lenient lens is reported
next to the strict score (see below).

A fact counts only where it is bound. An envelope fact counts inside the `scenario`/`model` node that owns
that plant; a per-step value counts on the trace rows of that step. A value appearing merely somewhere
else in the report does not count.

If either material digest does not match, or any of the three deliverables is missing, empty or
unparseable, the validator returns before any item is measured, so every completion is 0 and the strict
score is 0.

## Scoring Dimensions

Each item is one scored proposition. Weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| --- | --- | --- | --- | ---: | --- |
| P06 | Stress and envelope derivation | A declared current operating band (a pair of fractions, `0 <= lower < upper <= 1`); for every step the normalized `壓力指數` and the `目標出力_MW` recomputed from that declared band and the source-derived stress; and, per plant, the adjustment envelope disclosed inside the `scenario`/`model` node that owns it — its eligible dispatchable capacity, a declared adjustment fraction, the observed adjacent absolute change series, and prose stating the derivation rule | `dispatch_review.json` and `dispatch_trace.csv` | 0.4 | Multi-step reasoning/self-checking |
| P08 | Bounded dispatch constraints | Per unit and step: source-bound capacity and snapshot output, causal adjustment limit and bounds, actual/command output, outage flags, load factor recomputed from source capacity, and row-level step total/residual/reachability. A missing step fails all twelve per-unit constraints for every required unit and separately loses coverage credit | `dispatch_trace.csv` | 0.12 | Multi-step reasoning/self-checking |
| P12 | Headline metrics | Headline metrics reconciling to the trace: step count, units per step, trace row count, reachable step count, maximum absolute residual, maximum unit load factor, and final-step total output | `dispatch_review.json` `metrics` and `dispatch_trace.csv` | 0.05 | Multi-step reasoning/self-checking |
| P15 | Limitations | Source-bound semantic coverage of temporal separation, daily rather than sub-hourly resolution, aggregate-to-unit mismatch, and omitted network/fuel/reserve/stability constraints | `dispatch_review.json` `limitations` plus source records | 0.28 | Domain judgment |
| P16 | Rerunnable program | `output/dispatch_model.py` rerun in a clean workspace on the two materials alone regenerates the submitted report and trace, and after a controlled shift of one plant value in the last daily record the last step's historic plant value follows it (1 or 0) | `dispatch_model.py`, rerun | 0.05 | Reproducibility |
| P17 | Conditional operational decision | The decision is substantively conditional, avoids an actual-system or unconditional deployment claim, and binds at least one material caveat to the recommendation | `dispatch_review.json` `decision` plus source records | 0.05 | Domain judgment |
| P18 | Traditional Chinese classifications | No classification, status, verdict or dispatchability string in `unit_register`, `decision`, `scenario` or `metrics` is in Latin script or simplified characters - the D04 test, credited when it is clean (1 or 0) | `dispatch_review.json` | 0.05 | Instruction compliance |

Partial credit is the rule: every item is the mean of its underlying checks, so a trace that satisfies most
bounds, or a metrics block reconciling most headline figures, earns proportionally. `P15` to `P18` are the exception
in practice — each is a single check, so it is all or nothing.

Stress/envelope derivation receives 40% because it defines the scenario and
every downstream target. Limitations receive 28% because this prospective
screening must not be presented as a real-system dispatch approval. Per-unit
bounds receive 12% as the direct physical consistency layer. Headline
reconciliation, rerunnability, the conditional decision, and language
compliance receive 5% each: each is independently necessary for auditability or
safe use, while none can compensate for an incorrect dispatch model. The
weights encode relative engineering responsibility rather than a uniquely
correct numerical split.

### Accepted equivalent expressions

- Facts are located by value inside the object the contract names for them, not by the reference report's
  key spelling, nesting or container shape. JSON key order, trace row order and float formatting are free.
- Metrics are recognised by the function their key performs, across Chinese and English key wordings. Load factor is always recomputed from source capacity; a candidate capacity cannot validate its own derived metric.
- Conditionality and the meaning of the operational conclusion are owned by the source-bound P17 semantic review. Keyword scans may locate evidence but cannot independently trigger the unconditional-decision deduction when P17 confirms a substantive condition.
- The current operating band and the per-plant adjustment fraction are scenario assumptions the minutes
  leave to the report: the minutes fix the deliverables, the eight objects, the header, the facts to bind
  and disclose and the conditional decision, and state no admissible range for either quantity. Neither is
  therefore settled against a range. The scorer reads the value the report declares and measures the
  deliverable built on it — all targets must recompute from the declared band, all step limits and bounds
  from the declared fraction — so another defensible band or fraction and its resulting minimax schedule can
  receive full credit. The only bound applied is definitional: both are fractions (the band of the pre-event
  dispatchable output, the adjustment fraction of installed capacity), so `0 <= lower < upper <= 1` and
  `0 < fraction <= 1`. A pair or a value outside that domain, or a degenerate band with `lower >= upper`, is
  not a readable declaration and the item is charged as if none were declared. The nearest-rank 90th
  percentile of the observed relative changes is the reference derivation only, and is neither required nor
  a threshold.
- A report that carries more than one admissible declaration — a band beside an unrelated pair of fractions,
  an adjustment fraction beside the band's own lower and upper fractions — is read through the one its own
  trace is built on, measured as the share of the trace that reconciles with it; ties keep the first
  declaration in document order. A report whose trace reconciles with none of its declarations still counts
  as declaring one, and is then charged on the values its trace actually carries.
- The greatest observed loss is the reference screening choice, not a required identifier: any credible
  online dispatchable unit, declared under a key that names the event, is accepted, and the whole scenario
  is then evaluated against that declared unit.

## Deductions

Each damage instance multiplies the score by its coefficient, so a failure that opens N instances of one
item costs `coefficient^N`.

| Item | Error | Damage instances | Coefficient | Rationale |
| --- | --- | ---: | ---: | --- |
| D01 | The output contract is broken. Five aspects, each its own damage instance at the same coefficient: (a) `dispatch_review.json` is missing one of the eight required top-level objects, or `dispatch_trace.csv` does not carry the exact prescribed header; (b) the trace does not carry a row for every in-scope dispatchable unit at every one of the fourteen source dates; (c) trace rows dispatch an output outside the bounds those same rows declare; (d) the `decision` object's declared verdict contradicts the trace it is built on, or declares no verdict at all; (e) the decision is not conditional - it claims the result holds unconditionally or states no condition | (a) once; (b) once, plus one per further 15% of the required rows absent, capped at 3; (c) two affected rows are a slip and cost nothing here, beyond that once, plus one per further 25% of the trace affected, capped at 3; (d) once; (e) once | 0.9 | The minutes fix the eight objects, the header, one row per in-scope unit per source date, and a conditional operational decision. A review that carries the objects but not the content, that dispatches against its own stated bounds, or whose recommendation contradicts its own trace, cannot be read as the agreed deliverable. Bulk loss is banded because a systematic failure is not the same damage as a single slip |
| D02 | The submitted program cannot reproduce its own submitted artefacts: it fails to run from a clean workspace on the two materials alone, or the regenerated report and trace do not match the submitted ones | once | 0.3 | A deliverable another engineer cannot regenerate is not a reproducible analysis, and the numbers it reports are unverified |
| D03 | The deliverable does not follow the source records. Three aspects, each its own damage instance: (a) the program reproduces cleanly but does not react to a controlled source-record change - after one plant value in the last daily record is shifted, the last step's historic plant value does not follow; (b) the trace dispatches a nonzero output for a unit outside the in-scope dispatchable register, such as one the snapshot's `備註` takes out of service; (c) `scenario`, `decision` or `limitations` affirms that the two records are contemporaneous (`為同時量測`, `同時記錄`, `同時取得` and the like, unless a negator such as `不`, `未`, `非` stands earlier in the same clause, as in `兩者不是同時量測` or `不宣稱兩份檔案為同時量測`) | (a) once; (b) once; (c) once | 0.9 | A source-insensitive program has hard-coded its results rather than derived them from the records, and scheduling a unit the source record marks `檢修` or `歲修` is the same failure stated on the dispatch side |
| D04 | A derived classification, status or decision string is written in Latin script or in simplified characters | once | 0.9 | The minutes require Traditional Chinese for explanatory text, decisions, limitations and status reasons |
| D05 | The record dates are not bound: `source_binding`, read as digits, does not carry the first and last selected daily record dates (`20260718`, `20260731`) and the snapshot date (`20260914`) | once | 0.3 | The minutes require the review to "bind the two record dates"; without them the 45-day separation the scenario rests on cannot be checked |
| D06 | The unit register is incomplete: an in-scope dispatchable snapshot unit has no classification in `unit_register`, or an in-scope unit the snapshot's `備註` takes fully out of service is absent or not classified as unavailable (`不可調度`, `不可用`, `停機`, `檢修`, `歲修`, `排除`, `不納入`) | once | 0.3 | The minutes require the review to "classify every in-scope snapshot unit" |

Interactions with the scored items:

- A deduction item names a property of the whole deliverable, so repeated manifestations of one failure stay a
  single damage instance - with the two banded exceptions named in `D01`, where missing required rows and
  systematic bound violations open further instances as the share of the deliverable they affect grows. The
  bands are capped, so no single failure can open more than three instances.
- `D01` (d) and (e) charge the `decision` object; `P17` credits a conditional decision that names a scoped
  caveat. An inverted recommendation on an otherwise correct deliverable is charged once under D01, at 0.9. The
  verdict is read only from verdict-bearing keys (`狀態` / `結論` / `決策` / `判定` / `結果` / `判斷` /
  `status` / `conclusion` / `verdict`), the negative forms are vetoed before the positive ones, and a marker
  inside a clause that negates it - "不支持無條件宣稱…" - is not a claim.
- Evidence pointers are not scored; the reproducibility of the deliverable is credited through `P16` and
  charged through `D02` and `D03` (a).
- `P16` credits the same reproduction and source-sensitivity runs that `D02` and `D03` (a) charge.
- `P18` credits a deliverable that `D04` does not charge.
- `D03` (c) is read from the report text and is independent of the reproduction.
- `D05` and `D06` read `source_binding` and `unit_register` only.
- `D02` and `D03` (a) are mutually exclusive: `D03` (a) is only reached when the clean reproduction
  succeeded. `D03` (b) is read from the trace and does not require the reproduction to have succeeded.
- `D01` is independent of the reproduction checks and can fire alongside `D02` or `D03`; when it does, the
  coefficients multiply.
- `D04` reads only the classification, status, verdict and dispatchability keys of `unit_register`,
  `decision`, `scenario` and `metrics`. Characters shared by both scripts are not violations, and free
  narrative outside those keys is not inspected.

## Automatic Failure

There is no automatic failure for formatting; every penalty is a multiplicative deduction rather than a
score cap. The score is 0 only when the validator can measure nothing: either material digest changed, any
of the three required outputs missing or empty, or the JSON or CSV unparseable. A deliverable that earns no
item credit scores 0 on its own.

Empty files, keyword stuffing, source dumping, numeric shotgun output, repeated identical steps and a
hard-coded source-insensitive program cannot satisfy the headline capabilities: the per-step values are
checked against independently recomputed bounds and balances, and the program is rerun both
unchanged and after a controlled source perturbation in an isolated workspace.

## Lenient Lens

A binary lens is reported next to the strict score. It requires P06 >= 0.75,
P08 >= 0.90, P12 >= 0.80, and full P15-P18 completion. Clean reproduction,
source sensitivity, record-date binding, and unit-register completeness are
mandatory. It is independent of a strict-score threshold and damage count.

The score measures the quality of this scoped dispatch review. It does not certify actual reserve,
transmission adequacy, fuel availability, stability, or physical ramp performance. No pass threshold is
defined, and scoring does not certify real-world operation.

## Equivalence Rules

Clean replay and source perturbation run `python output/dispatch_model.py` in a
fresh workspace without undisclosed arguments. Equivalent outage-status wording
is accepted when the outage marker, zero output, and bounds remain consistent.
Date/change evidence may be represented as records or numeric arrays. A shared
parent derivation may support both plants, but plant-specific evidence cannot be
borrowed from the other plant.

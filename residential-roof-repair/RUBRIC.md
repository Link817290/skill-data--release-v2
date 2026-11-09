# Roof Repair Enquiry Scoring Rubric

The required outputs are `维修询价清单.xlsx` and `施工范围说明.docx`. Both must
exist, be readable, and remain suitable for contractor pricing. The evaluator
reconstructs source quantities independently and uses a source-bound semantic
judge for scope and commercial meaning. Equivalent Chinese wording, row order,
and document organization are accepted.

## Strict Score

Strict uses five non-overlapping local closures: numeric catalog 0.55; roof scope
and assemblies 0.20; drainage interface 0.10; waste measurement 0.075; and
commercial/evidence control 0.075. Every closure uses the arithmetic mean of its
local owners, so one defect loses only its own fraction of that work package.
There is no global product, repeated owner exposure, score floor, or cap.

The numeric catalog closure contains four independently reported owners:

| Owner | Purpose |
| --- | --- |
| Known scoped quantities | Correct source identity, code, unit, and quantity for all 17 known lines. |
| Unresolved mixed waste | Both whole-building waste lines remain pending with a meaningful note. |
| Summary reconciliation | Eight summary groups reconcile to submitted scoped rows. |
| Quotation status | Expected rows exist and unsupported prices remain blank. |

The thirteen semantic owners are physical scope, waterproofing specifications,
the building-B and building-C bundles, drainage accessories, pipe material and
connection boundaries, shared-waste and measurement boundaries, measure-cost
boundaries, evidence status, commercial change control, and the roof-insulation
specification boundary. Each closure averages its declared owners; missing one
interface remains visible without erasing other correctly documented controls.

The 55% numeric catalog share makes the editable quotation workbook the primary
deliverable. The remaining 45% measures the technical and commercial boundary
analysis needed to price it. A missing upstream row cannot earn summary or
quotation-status credit; an unexpected scoped row reduces the known-quantity
owner once and remains visible to semantic physical-scope review.

## Lenient Score

Lenient is an independent usability conjunction. The file/format precheck requires
both published files. Business must-haves then require all known quantities, both
unresolved waste controls, reconciled summaries, no invented prices, the roof-only
physical and measurement boundary, and usable measure-cost, evidence-status, and
commercial change controls. Waterproofing wording and other technical detail remain
in strict. Lenient never thresholds or rescales strict.

## Semantic Judge

The thirteen semantic criteria are defined once in
`task/tests/mix_judge/contract.json`. Every response must contain each ID exactly
once with a binary score, a reason, candidate evidence, and source/reference
evidence. Source materials override Golden. New submissions use the standard
`LLM_JUDGE_*` fresh Responses-compatible runtime; replay requires an exact
request-bound cached response. Missing judge evidence is an infrastructure error,
not a candidate zero.

The Golden reference retains the original workbook and document structure. Its
scope note explicitly covers seasonal/night work and construction drainage; the
same measures may also be evidenced by workbook rows M02 and M06.

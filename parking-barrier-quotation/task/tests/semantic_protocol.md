# Semantic scoring protocol

## Reviewer

A fresh judge evaluates each artifact independently from the supplied source and
candidate evidence. It is not given another artifact's score or any target
score.

## Visible inputs

1. The current scoring contract in `RUBRIC.md`, with no condition labels,
target bands, or other artifact-specific metadata.
2. The instruction the solver was given, taken from the frozen run directory.
3. The permitted materials, read as images.
4. The frozen deliverables under neutral names, opened for formulas and for cached values; formulas evaluated by the reviewer where cached values are absent.

## Hidden inputs

The reference workbook's identity and any other artifact's output remain hidden
from the judge.

## Items the semantic view rules

All positive items and all deductions, with B1 placements (a) to (e), B2 components and quantities, and A2 units stated explicitly. D01, D02 and D05 are ruled by this view only.

## Output

Per artifact: per item judgement with evidence cells and one sentence of reasoning; per deduction fires or not, object key, exclusion applied; positive_earned, deduplicated_deductions, raw and final to four decimals. A separate file quotes every rubric sentence found ambiguous.

## Rules

Plain omission loses its own credit and is not additionally penalised. Style, sheet naming, column ordering and length that the rubric does not name are not scored. A predicate that cannot be settled from the visible inputs is reported as insufficient evidence together with what would settle it.

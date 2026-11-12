# Final-Review Closure Checklist

## Per-case checks

1. Every case ID must come from the case index.
2. Apply the case-level activation gate first. When the core-candidate set is empty, complete the case as an empty-conclusion case and do not add items back from the conditional set.
3. Check the text after every semicolon in long imaging descriptions so that a focal abnormality is not missed after a statement such as “normal in size.”
4. Check every explicit classification or conclusion-bearing item, coexisting findings in long imaging descriptions, and explicit specialty findings.
5. Verify that location, laterality, quantity, degree, characteristics, certainty, and status are complete and have not been invented.
6. Remove synonymous duplicates while retaining medically independent coexisting findings.
7. Review every proposed conclusion: it must cite at least one detail-row ID belonging to the same case.

## False-negative checks

Run these with the same weight as the false-positive checks. A gate that is applied in one direction only will quietly empty out cases that should have carried conclusions.

- Was a finding dropped because it reads as minor, rather than because the evidence failed a stated check? Degree is not grounds for exclusion.
- Was a quantitative item skipped as "just a number" without first testing it against the standing-readout tests?
- Was a description left unnamed even though the modality's vocabulary names it unambiguously?
- Was a present finding suppressed because it sat in the same row as a postoperative or historical state?
- Was a department skipped because it is routine, rather than because its records were negative?
- For every case marked `无异常结论`: can each removed candidate be tied to a specific check it failed? If a case went empty through accumulated hesitation rather than named failures, reopen it.

## False-positive checks

- Were isolated laboratory arrows or out-of-range values with no named conclusion, or general medical risks, entered directly into the final review? If so, return to the evidence hierarchy and screen them again. This asks whether the record named a finding, not whether the deviation was small.
- Were multiple value deviations from the same test group combined into a new diagnosis? Corroboration across rows cannot replace a conclusion-bearing item.
- Did a pure status item or incidental description activate the case by itself? If so, perform the counterfactual empty-case check.
- Was an examination not performed treated as normal?
- Was `possible` upgraded to a definite diagnosis?
- Was a description rendered as a named finding that the description does not uniquely determine — one a reader of that modality could reasonably have named differently?
- Was a number reinterpreted using a threshold the reader supplied, for an item that does not carry its own standing-readout rule?
- Were conclusions invented merely to fill a case whose doctor's final review should be empty?
- Was “clinically noteworthy” mistaken for “necessarily included in this institution's final review”?

## Output

- `总检结论`: one independent conclusion per row, numbered consecutively from 1 within each case.
- `证据明细行号`: at least one row ID, with multiple IDs separated by semicolons; do not cite another case.
- `病例汇总`: one row for every case in the case index; use `有异常结论` when conclusions are present and `无异常结论` when none are present.
- Do not add a “no abnormality found” placeholder row to `总检结论` for a normal case.

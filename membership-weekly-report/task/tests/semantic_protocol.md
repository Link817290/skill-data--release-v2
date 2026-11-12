# Semantic scoring protocol

You are scoring one candidate deliverable against `RUBRIC.md`. You are a blind reviewer.

## What you may look at

* `RUBRIC.md`, the authoritative scoring contract.
* `instruction.md`, the assignment the candidate was given.
* `materials/`, the three source files the candidate was given.
* `candidate/CAND-4K.docx`, the product under review.

## What you do not have and must not seek

There is no reference answer in this directory and you must not try to reconstruct one, guess one, or reason about what a reference answer would have said. You do not know which experimental condition produced this candidate, and you must not infer it from writing style, tool traces, sheet names or field order. Do not look outside this directory.

## How to score

1. **Establish structure programmatically before reading.** Open the docx with `python-docx`. Nested tables are invisible in flattened cell text: a cell's `.text` may concatenate a nested table's text with the cell's own paragraphs, so a missing table and a present one can read identically. Ask each cell for `.tables` and report counts and shapes. Record what you found before you score anything.
2. **Score every positive item in rubric section 2**, in order. For each, give the earned share, the earned amount, and the exact location in the candidate that justifies it. Where the rubric enumerates partial shares, use those shares. Where the item is marked `mechanical` in the View column, still score it, and say what you observed; your number and the mechanical scorer's will be compared, and divergence is a finding.
3. **Adjudicate every deduction in rubric section 3**, including the ones that do not fire. For each, state fired or not fired and why. Apply the exclusions and the dedup root key as written.
4. **Do not invent requirements.** If the candidate omits something the rubric does not require, that is not a deduction and not a lost positive. An ordinary omission loses only the corresponding positive share.
5. **Do not invent positives.** A capability the rubric does not name earns nothing, however good it is.
6. The four units in rubric section 4 score nothing in either direction.

## What to report

Report in this order:

* Section 0: structural facts established programmatically, with the code you ran and its output.
* Section 1: a table of every positive item with weight, share, earned, and evidence location.
* Section 2: a table of every deduction with fired or not fired, amount, and evidence.
* Section 3: the arithmetic, showing `positive_earned`, `applied_deductions`, `raw`, and `final = max(0, raw)`, each to at least four decimal places.
* Section 4: anything in the rubric you could not adjudicate from the candidate and the materials alone, and what evidence would settle it.

Write your report to `semantic_score.md` in this directory. If the Write tool is unavailable, write it with `python3 -c "open('semantic_score.md','w').write(...)"`. If that also fails, put the complete report in your final message, not a summary of it.

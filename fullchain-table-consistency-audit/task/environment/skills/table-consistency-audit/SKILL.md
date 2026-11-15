---
name: table-consistency-audit
description: Audit the tables of a long business document (proposal, report, tender, manual) for internal consistency before it is released, and write a report that lets the owner locate each problem and decide whether to send. Use when the scope covers table cells, the sentences that introduce tables, body text that restates table values, and tables typed inline as text.
---

# Table consistency audit

The reader of your report has to make one decision: send the document as it is, or fix it first. Every
finding you write either changes that decision or tells the author exactly what to change. A report that
lists thirty loosely related observations at the same weight is harder to act on than one that separates
the defects that block sending from the points the author only needs to confirm.

Before you open any input, read all three references in full:
`references/table-checks.md`, `references/cross-table-alignment.md` and
`references/grading-and-reporting.md`. Then work through the five passes below in order. Each pass
names the reference whose rules apply at that point.

## Pass 1: build the table inventory before judging anything

Walk the whole document once, front to back, and register every table in scope in a working list:
section number and title, the introducing sentence (quote it), the header row, and any body sentence in
the same section that repeats a value from the table. Register tables typed inline as pipe separated
text or placed in code blocks as well; they are tables for the reader even if they are not formatted as
tables. Do not start writing findings during this pass. Most missed defects in long documents come from
stopping after the first chapters or from never linking a table to the sentence above it.

For each table also note the entities it describes (a product, a model, a case, a service tier) and the
attributes it reports. Pass 3 needs this list to find the same entity in another section.

## Pass 2: single-table checks

For every registered table, run the checks in `references/table-checks.md`: column sums and what the
column means, derived columns replayed from their inputs, units and scales against the introducing
sentence, counts and conditions stated in the introducing sentence, and body sentences that restate the
table. Write down the replay (the numbers and the result) for every check that looks wrong, and also
for every check that looks wrong at first sight but holds under a reading the document supports.

## Pass 3: cross-table alignment

Use the entity list from Pass 1. For every entity or case that appears in two or more tables or in a
table and a body sentence, compare the same attribute under the same condition. Apply
`references/cross-table-alignment.md`: how to prove two rows describe the same object, how to align
tiers or levels that carry different names, how to test a stated range against measured values, and how
to decide which side is the outlier.

## Pass 4: grade every candidate

Give every candidate exactly one grade: confirmed defect, needs author confirmation, or checked and
consistent. Apply `references/grading-and-reporting.md`. A candidate is confirmed only when it survives
the most favourable reading the document itself supports; when a reasonable alternative reading remains,
it goes to author confirmation with that reading stated. Candidates outside the audit scope are dropped,
not graded.

## Pass 5: write the report

Follow the report structure in `references/grading-and-reporting.md`: a one line send decision at the
top, confirmed defects with location, conflicting values, the replay that proves the conflict and one
line of consequence (direction only when proven), the
items for author confirmation with the alternative reading, the checked and consistent items that a
careful reader would otherwise flag, and a disposition that ties each defect to what must happen before
sending.

## Self-check before delivering

Answer each with a count or a yes or no; fix the findings, not the summary, if one fails.

1. The inventory covers every chapter, including the last ones, and every inline or code block table.
2. Every table with an introducing sentence that states a count, a scale, a scale factor, a range or a
   condition was replayed against its rows.
3. Every entity that appears in two places was compared attribute by attribute under the same condition.
4. Every confirmed defect names which side is wrong only when the document proves it, and the wording
   does not blame the side that the replay shows to be consistent.
5. Every confirmed defect states both conflicting values and the replay, not only "inconsistent".
6. No confirmed defect is one that a supported alternative reading resolves; each such item is either
   graded for author confirmation or listed as checked and consistent.
7. No corrected value is asserted as the right figure unless the document itself determines it.
8. No finding is about figures, typography, general facts or outside regulations unless the scope asks
   for it.
9. The report ends with a send decision and a disposition that separates must-fix-before-sending items
   from items for the author to confirm.

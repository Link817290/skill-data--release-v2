# Grading and reporting

Use in Pass 4 and Pass 5.

## 1. Three grades

| Grade | Test | What the report must carry |
|---|---|---|
| Confirmed defect | two values or a value and a rule cannot both hold under any reading the document supports | location, both values, the replay, and one line of consequence; add a direction only when proven and an excluded reading only when a reader would plausibly raise it |
| Needs author confirmation | a difference exists, but a reading supported by the document (different metric, different object grade, different stage, example rather than full list, a different basis or setup the document states) would make it consistent | both values, the alternative reading and the words in the document that signal it, in one or two sentences |
| Checked and consistent | a check that looks wrong at first sight holds under a supported reading | the anomaly and the replay that clears it |

A reading counts as supported only when words in the document signal it (a different metric name, a stated
condition, a qualifier, a different case label); quote those words when you use it. A reading you had to
supply yourself, with nothing in the document pointing to it, is not a supported reading and does not
change the grade.

Severity labels (high, medium, low) are not a substitute for the grade. An item for author confirmation
can matter a great deal and still not be a confirmed defect; state both if you use severity.

## 2. The favourable reading test for apparent defects

Before confirming any candidate from a sum, a range or a ratio, try the readings the document supports:

- the column is a per-row split, independent rates, or a multi-select share, not a partition;
- the introducing sentence carries a condition (a threshold, a mode, a baseline) that selects which rows
  are compared;
- a range statement may describe single steps between adjacent rows rather than the extreme rows;
- a derived value may use a common base row or weights stated elsewhere;
- a unit conversion makes the ratio exact.

If one reading makes every number consistent, the item is checked and consistent, and you should say so:
computing the right numbers and then still calling the table wrong is the most damaging mistake an audit
can make, because the author will change correct figures. If a reading makes some numbers consistent and
the text does not say which reading it means, grade it for author confirmation.

## 3. Scope discipline

Report only what the audit scope covers. For a table consistency audit that means table cells,
introducing sentences, body sentences that restate table values, and tables typed as text. Do not add
findings about typography, placeholder names, outside regulations, general domain plausibility or body
facts unrelated to any table. Extra findings dilute the decision and some of them will be wrong.

## 4. Corrections

Recommend what the author must decide, not a new figure, unless the document determines the figure (for
example a total that follows from the rows under the document's own formula). When the right value
cannot be determined from the document, say so, for example "correct value: to be supplied by the
author". Never fill a qualitative cell with an invented quantity, and never invent the missing members of
a list the introducing sentence promised.

## 5. Report structure

1. **Send decision**, one line: whether the document can be sent as it is. If any confirmed defect
   exists, the answer is not to send before fixing.
2. **Confirmed defects**, one block each: location (section number and title, table header or quoted
   introducing sentence), the conflicting values, the replay, and the consequence. Add a direction line
   only when section 4 of `cross-table-alignment.md` proves one; when it does not, say nothing about
   direction rather than writing that it cannot be determined.
3. **Items for author confirmation**, one short block each with the alternative reading.
4. **Checked and consistent**, a compact table of apparent anomalies and the replay that clears each.
5. **Disposition**, grouping the confirmed defects by what must happen before sending (correct a figure,
   complete a missing part, remove an unsupported figure) and listing the items the author must confirm.

Keep each block short: a confirmed defect normally fits in four or five short lines. Quote only the table
header cells and sentence fragments needed to find the table, not whole headers of every table involved.
Do not add sub-lists of excluded readings, replay tables or repeated consequence lines for defects that a
single replay already proves. Restating the document's text beyond the values needed to locate and prove
the finding makes the report longer without helping the decision.

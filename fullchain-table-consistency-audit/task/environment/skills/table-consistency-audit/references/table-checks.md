# Single-table checks

Use in Pass 2 for every registered table. Each check says when it applies, what to compute, and what
result makes it a candidate. Record the numbers you used; a candidate without its replay cannot be graded.

## 1. What a column of percentages means

Before summing any percentage column, decide what the column is.

| Column kind | How to recognise it | What must hold |
|---|---|---|
| Partition of a whole | shares of one total, weights, allocation of one budget | the column sums to 100 |
| Pair of complements per row | two columns that split each row (ours versus theirs, work versus overhead) | each row sums to 100; the columns do not |
| Independent rates | frequency, incidence, adoption or probability of separate events | no sum is required |
| Multi-select survey shares | share of respondents naming each item | the sum may exceed 100 |
| Rates that apply to separate tiers | commission or discount per partner level | no sum is required |

Only the first kind is a candidate when the column total is not 100. A weight column that is short of
100 is a real defect even when every value looks plausible: nothing weighted can be computed from it.
When the same document has other weight tables that do sum to 100, cite them as the document's own
convention.

## 2. Derived columns

For columns such as uplift, change, ratio, priority score or total, replay every row from its inputs.

- Decide the basis first: relative change, `(new - old) / old`, or difference in percentage points,
  `new - old`. Replay every row both ways. A column that mixes the two bases is a defect even when each
  row is arithmetically right under one of them, because the reader cannot compare the rows.
- A decrease that is an improvement (fewer false alarms, lower cost) stored as a negative value in a
  column named as an improvement is a reading hazard; mention it with the basis finding.
- When some input cells are blank or a dash, look for a common base in the table (often the first row)
  before calling the derived value unsupported.
- When the weights behind a composite score are not printed, try the weights stated elsewhere in the
  section, or solve them from two rows and test the remaining rows. If every row replays, the column is
  consistent.
- Convert units before replaying ratios of durations, sizes or rates.
- A derived percentage whose inputs are text categories rather than quantities has no derivation. That
  is a defect of its own; do not invent a quantity to make it computable.

## 3. The introducing sentence

The sentence before a table often fixes the scale, the count, the unit or the condition that the rows
must satisfy. Treat it as part of the table.

- **Scale or quantity** ("for N units", "per year"): recompute every row that depends on it, for example
  unit cost times quantity plus fixed cost against a stated total. When one row matches and another does
  not under the same formula, the formula is the document's own and the mismatching row is the defect.
- **Count** ("a five step process", "three levels"): count the rows. A count higher than the rows, with
  no "for example" or "including", is a defect.
- **Scoring scale** ("rated 1 to 5", "scored as a percentage"): every row that feeds the weighted score must be
  on that scale. Raw measurements (milliseconds, currency, yes or no) in such a table make the weighted
  score impossible.
- **Range or factor** ("reduces cost by a quarter to a third", "several times faster"): replay the rows that
  the sentence refers to. Before calling it a conflict, check the condition in the sentence (above a
  threshold, when idle, compared with which baseline) and which pairs of rows the sentence compares.
  Adjacent steps, the first qualifying row, or the stated baseline may be the intended comparison; test
  each supported reading and see `grading-and-reporting.md` for how to grade the result.

## 4. Body sentences that restate the table

Search the same section for sentences that repeat a table value (a time limit, a rate, a threshold). A
body sentence that agrees with one of two conflicting tables is evidence for Pass 3. Compare like with
like: a handling time is not a response time, a detection rate is not an accuracy, a target is not a
measurement.

## 5. Tables typed as text

Inline tables use the same checks. Their formatting is not a consistency defect unless the scope asks for
presentation; report their content only.

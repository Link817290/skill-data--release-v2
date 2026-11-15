# Cross-table alignment

Use in Pass 3. Long documents are written section by section, and the same object is often described
twice with different numbers. These conflicts are the ones a client finds by flipping pages, and the ones
a single-table check never sees.

## 1. Proving two rows describe the same object

Two rows are the same object only when the label and at least one control attribute match.

- Same label and a matching control attribute (same power draw, same model name, same case, same service
  level wording): treat as the same object; a different value for another attribute is a candidate.
- Different labels for what might be the same class (a broad label in one table, a narrower one in
  another), or value ranges that do not overlap at all: the rows may describe different grades of object.
  This is at most an item for author confirmation.
- Same case in two stages of the same section (validation threshold and test target, pilot and
  production): compare only attributes that measure the same step. If one table's value is an end to end
  limit and the other allows a single step more time than the whole, the two cannot both hold. That is a
  conflict, not a difference of stage.

## 2. Aligning tiers with different names

Service levels, priorities and risk classes are often named differently in two tables (words in one,
codes in the other). Align them by their descriptions, not by position alone: match the escalation
condition, the impact wording and the number of tiers. A tier that agrees exactly across the two tables is
evidence that both describe one scheme. Before treating the differing tiers as conflicts, look for words
that signal a second scheme (a revision or effective date, a region, a customer class, a different
product). If nothing signals one, the differing tiers are conflict candidates for Pass 4; if something
does, grade them for author confirmation and quote those words. Then look for a body sentence in the same
section that states one of the tier values; section 4 explains when it identifies the outlier.

## 3. Stated ranges against measured values

A comparison table often states a typical range for a class ("class A: 31 to 39",
"class B: 17 to 19"), while another table in the same section lists measured values for named members
of those classes. Assign each named member to its class using the section's own labels and test each
value against the range. Report each class separately: two classes that both fall outside their ranges
are two independent conflicts.

## 4. Which side is wrong

Only name an outlier when the document proves it. Evidence, in order of strength:

1. **Internal consistency.** One table's other columns replay with its value (a ratio column computed
   from it, a total that includes it); the other table has no such support.
2. **A third carrier.** A body sentence or a third table in the same section states the same value as one
   side.
3. **A shared formula.** Under the formula the document itself implies, one row matches and the other
   does not.

Write the direction in terms of the side that fails the evidence. Wording matters here: saying that the
consistent side is "underestimated", "missing a component" or "incomplete" assigns the defect to the
wrong row and sends the author to change a correct figure. If the evidence points both ways or nowhere,
report the conflict without a direction and let the author decide.

Do not choose a direction by plausibility, by which value is rounder, or by outside knowledge of typical
products.

## 5. Things that are not conflicts

- Different scenarios or objects that share a metric name (thresholds for different cases, device
  classes or layers of a stack). Keep a scenario list per metric before comparing.
- A target and a measurement, or a limit for one stage and a benchmark for another stage, unless the two
  constrain the same step of the same case as in section 1.
- Values that differ because one is a range and the other a point inside it.

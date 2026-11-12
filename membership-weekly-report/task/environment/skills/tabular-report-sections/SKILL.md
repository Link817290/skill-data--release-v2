---
name: tabular-report-sections
description: Use when filling in a recurring status or progress report template whose sections carry multiple parallel items, time commitments, or numbers a reader will want to check. Covers deciding which sections need a table rather than prose, laying out schedule, register and supporting data tables, and building them inside an existing template without breaking it.
---

# Tabular report sections

A recurring report template gives you labelled sections and nothing else. What goes inside each section is your decision, and for some sections prose is the wrong answer even when it reads well.

The failure this addresses is specific: a competent writer fills every section with fluent paragraphs, delivers something that looks complete, and loses the two things the reader actually opens the report for, which are the ability to see many parallel items at once and the ability to check a claimed number against its source.

## Decide the shape of each section before writing it

Work section by section. For each one, look at the content you are about to put in it and ask which of these four it is.

**Several parallel items, each with its own timing.** Use a schedule table. A reader working through one paragraph per item cannot see that several of them land in the same period, or that one has slipped past the others. A reader scanning a table with items down the side and time buckets across the top sees it at once. This is the most common place a report gets written as prose and should not be. See [schedule table layout](references/schedule-table-layout.md).

**Several parallel items with attributes but no time dimension.** Use a plain register table: one row per item, one column per attribute that the reader compares across items, such as owner, severity, status, or category. Risk registers, open findings, outstanding decisions and rosters all land here. The reasoning is the same as for the schedule table, minus the time axis: the reader's question is comparative, and prose destroys comparability. Do not let the absence of dates push this content back into paragraphs.

**A claim resting on numbers.** State the finding in prose, then attach the underlying figures as a compact table. The prose says what moved and why it matters; the table lets the reader confirm it without going back to the source system. See [supporting data extracts](references/supporting-data-extracts.md).

**A single narrative point, or an explicit nil return.** Prose. Do not tabulate one thing. A table with one row is noise.

Sections where nothing happened get a short honest sentence. Do not pad an empty section and do not silently drop it, since the reader uses the section's presence to know it was considered.

## Do not restructure the template to make room

The template's shape is not yours to change. Keep its rows, columns, section labels, and their order as received, and put what you add inside the existing cells.

The reason is organisational rather than technical. The template is shared: colleagues read it by position, past periods are filed against the same shape, and whoever consumes it next, whether a person or a process, expects the shape they have always had. A report that reads well but arrives in a different shape creates work for someone else.

Building a table inside a cell that already exists is mechanically different from adding a table to a document, and the wrong approach quietly restructures the outer template. See [nested tables in documents](references/nested-tables-in-documents.md) for how to do it in document formats that support it, how to verify afterwards that you added structure inside a cell rather than beside it, and what to do instead in formats where nesting is impossible.

## Give the report one naming scheme and reuse it

A recurring report usually has more than one section organised around the same
underlying set of things: the problems section and the data section are both
about the same projects, seen from different angles. Decide once what those
things are called, and use the same names in every section that is organised
that way.

Two habits make this worth doing deliberately.

**Name the groups yourself rather than inheriting the source system's
classification.** The tracker or ledger you are working from groups things for
its own purposes, which is rarely how a reader locates them. It may put three
unrelated items under one category because they share an administrative
attribute, and split two things a reader thinks of together. Work out what
divisions the reader actually navigates by, name those, and let the source's
own categories fall where they may. Inheriting the source's grouping unchanged
is not organisation; it is passing the filing problem along.

**Reuse the same keys across sections.** If the problems section is grouped one
way and the data section another, the reader is invited to line the two up and
cannot, which costs more than leaving both ungrouped. One scheme, same keys,
with whatever section specific suffix each section needs. A reader should be able
to take a group from one section and go straight to the same group in the next.

Put the group name on its own line, with its content beneath it. A name written
inline at the start of a paragraph gives the reader a label but nothing to jump
to, and the content cannot be separated from it.

Not every section should be grouped this way. Sections that are a straight run
of per item entries, a status recap or a plan, often read better as one flat
list keyed by item name, and forcing groups onto them adds a level for nothing.
Group the sections where the reader arrives with a question about one group;
leave the rest flat. Where a previous edition exists, follow whatever it did.

**Let depth follow content.** Where one group holds several distinct matters,
put a second level between the group name and its entries. Where a group holds
two entries that need no such split, do not add a level just to keep the shape
symmetrical. Uniform depth across groups is a sign the structure was decided
before the content was read.

## Say nothing at length

When a section has nothing in it, the whole of the right answer is a word or a
short phrase saying so. Not a paragraph explaining why there is nothing, not a
note about what would have gone there, not a standing caveat parked in the
nearest empty section because it had to go somewhere.

This is the same judgment as deciding what belongs in a table, applied in the
other direction, and it is easy to get wrong because a one word section looks
like an unfinished one. It is not. The section's presence tells the reader it
was considered; its brevity tells them the answer. A reader who has to read
sixty characters to learn that there was nothing to report has been charged for
nothing.

## Write less than you want to

A report that goes upward competes for the reader's minutes, and the writer is
almost never the one who pays for length. Decide what does not go in.

Three habits cause most of the padding:

* **Filling a section that has nothing in it.** When a section genuinely has
  nothing to report, say so in as few words as the sentence needs and move on.
  A paragraph explaining at length that there is nothing to explain is worse
  than a single word, and the reader still has to read it to find that out.
* **Narrating what a table already shows.** Once the figures are in a table,
  the prose above it should say what moved and why it matters, not walk through
  the rows. If a sentence would be true by reading the table, cut it.
* **Adding caveats nobody asked for.** A standing caution, a rounding artefact,
  a low base effect: each is real, and each costs the reader time they did not
  choose to spend. Include one only when it changes a decision this period.
  Diligence that no one can act on reads as noise.

The test is not whether a sentence is true or well written. It is whether
removing it would change what the reader does. If not, remove it. Where a
previous edition of the same report exists, its length is the standard the
recipient is used to, and running several times longer is a change you should
be able to justify.

## Say what moved, and name what moved it

An aggregate that moved tells the reader something happened. It does not tell them
where to look, and a reader who cannot see which part moved cannot act on the
number. Whenever you report a movement in a total, name the component that
accounts for most of it and give that component's own movement.

The trap here is specific and costly, and a source table usually sets it for you.
Alongside each component's own change, the same table normally carries that
component's **share of the total**. The two are different questions with different
answers, they sit next to each other, and they often have similar names. Share of
total answers how big this component is. Own change answers how much it moved.
A report that says a component grew by its share figure has stated something
false while looking entirely reasonable, and nothing downstream will catch it,
because the number is real and it came from the right row.

Before you write a component figure, say out loud which question it answers. If
the answer is "how big it is" and the sentence is about movement, you have the
wrong column.

Where a source table already carries a computed change column, use it rather than
recomputing from the raw values. Recomputing invites a rounding or base period
disagreement between your report and the system everyone else reads.

## Point time references at the reader, not at the source

Source systems record time relative to themselves: next week, in two cycles,
after the next release, pending review. Those phrases were written on a date the
source knows and the reader does not.

Two places this matters.

**A section that is itself about a future period.** Writing "expected next week"
inside a section headed with next period's plans is self referential: the reader
already knows the section is about next period, so the phrase carries no
information at all. Convert it to a point the reader can hold against a calendar,
derived from the reporting period's own cut off date.

**Any commitment that will be read later than it was written.** A relative phrase
silently ages. An absolute one does not.

Convert by taking the source's relative phrase, anchoring it to the reporting
period's end date, and stating the result at the coarsest granularity the source
actually supports. Do not manufacture a precision the source never had: if the
source says next week, the end of that month is honest and a specific weekday is
not.

## Check a number before you write it, not after

Verifying that a table's cells match their source is a different check from
verifying the sentences around it, and the second is the one that gets skipped.

Narrative claims about data are assertions in their own right: a superlative
(the highest so far), a count (across the last several periods), a range (it has
run between these two values), a direction over time (it has grown every period).
None of these is checked by confirming that the extract's figures are correct,
because none of them appears in the extract. Each is a claim you derived, and
each can be wrong while every figure on the page is right.

A wrong claim of this kind is worse than a missing one. The reader has no way to
falsify it without reopening the source, which is the work the report exists to
save them.

Recompute each such claim against the source before the draft leaves your hands.
Counting claims are the ones that fail most often, because the count of rows in a
source table is rarely the count of periods the reader would name. See
[claims about the data](references/claims-about-the-data.md).

## Let house convention outrank anything here

Every default in this skill is a default. Where the team, the recipient, or the funder has an established convention for column order, row order, labelling, or layout, theirs wins. A report that is internally excellent and visibly unlike every previous edition costs the reader more than it gains them. When you cannot tell whether a convention exists, follow the previous period's edition.

## Check the structure, not the text

Reading your own output back as text will not tell you whether the tables are there, and the reason cuts both ways depending on the library. Some return a cell's nested table text concatenated with the cell's own paragraphs, so a missing table and a present one read identically. Others return only the cell's own paragraphs, so a table you did build is invisible in the text and a check written against the text reports it missing. Either way the text is the wrong thing to look at. Inspect the structure directly: ask the cell for its tables, count them, and check the shape of what you get back. Then, separately, confirm the figures you put inside them are actually reachable, because whatever consumes the report next may be reading the text.

Before you hand the report over, read it once as the recipient rather than as the
author. The question is not whether you did each thing you meant to do, which you
will always answer yes to, but whether the report answers what the recipient
opened it for. Where a section's shape was a decision, check the decision still
looks right against the content that ended up there, since content shifts while
you write. Where a figure or a claim came from a source, check it against the
source rather than against your draft, because a draft is not evidence of
anything except what you wrote earlier.

Two of those checks need a specific technique rather than a careful reading.
Structure has to be inspected as structure, for the reason given above: text is
the wrong thing to look at, whichever way your library happens to flatten it.
And anything you were told outside the source files has no source document
behind it, so nothing downstream can catch a value that drifted; those are worth
reading back against what you were actually told, word for word.

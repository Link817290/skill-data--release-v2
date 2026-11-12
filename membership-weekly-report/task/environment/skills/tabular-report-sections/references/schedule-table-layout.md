# Schedule table layout

Use this when a report section carries several parallel workstreams and each one has its own delivery commitment. The output is a small table that shows all of them against a shared time axis.

## When it applies, and when it does not

It applies when all three hold:

* Two or more items belong to the same section and are being reported together.
* Each item carries a time commitment, even a loose one.
* The reader's question is comparative: what lands when, what is crowded, what has slipped.

It does not apply to a single item, or to a section whose point is one narrative judgment rather than a set of parallel commitments.

Items with attributes but no time commitment do not belong here either, but they do not belong in prose. They belong in a plain register table with one column per compared attribute. Do not force a dateless item into a schedule table, where it will occupy a row with nothing in it, and do not let its datelessness push it into a paragraph.

## Layout

Items go down the side, time buckets go across the top. Not the reverse: reports grow by adding items far more often than by adding periods, and a table that grows downward stays readable while one that grows sideways does not.

Give the items as many identifying columns as the reader needs to locate a row, and no more. One column is right when item names are self explanatory. A second column earns its place when the items fall into groups the reader thinks in, such as a partner, a product line, or an owner, because repeating that context inside every item name hides the grouping. A third is rarely worth its width. When you split, normalize as you go: source trackers often carry the grouping inside the item name as a prefix or code, and copying the raw string into both columns leaves the grouping invisible.

Choose the time bucket that matches how the commitments are stated. Commitments expressed as period ends want period columns. Do not use a finer bucket than the commitments support, since that invents precision the source does not have. Where commitments are stated as durations rather than dates, such as a service level of so many days, project them onto the calendar first and say in the header that you have done so.

## Bounding the axis

Span the axis from the current reporting period through the latest commitment in the set, and no further. Trailing empty columns are not free: they make every row look like it stops early.

That rule assumes the commitments sit within a horizon a reader can scan. When they do not, bound the axis deliberately rather than letting it run:

* Keep the column count to what stays readable in the space available. Beyond roughly a dozen columns a schedule stops being scannable and becomes a wall.
* When commitments span a long horizon, bucket distant periods more coarsely than near ones. Near periods carry the detail a reader acts on; distant ones only need to show that something is out there.
* When the set mixes a near horizon with a far one, consider two tables, one for the periods in play now and one for the outer commitments, rather than one table stretched to cover both. A reader looking at this quarter should not have to scan past two years of blank cells.

## Translating a commitment phrase into a span

Source trackers state commitments in prose, not as ranges. Read each phrase for the period it ends in, then fill from the current reporting period through that period inclusive. The filled span means the item is live across those periods, not that work happens in each one.

Work through the phrase carefully, because the period that matters is the one the deliverable lands in, not every period the sentence mentions:

* A phrase naming one completion period fills through that period.
* A phrase naming a development milestone and a later release milestone fills through the later one, since the item stays live until then.
* A phrase carrying a conditional or an unassessed portion still fills through its stated period. Mark the uncertainty in the cell text rather than shortening the span, because a shortened span reads as a commitment that was never made.
* A phrase with no period at all belongs in the register table described above, not as an empty row here.

Where an item has phases with different endpoints, you can either give it one row carrying a span per phase, or one row per phase. Prefer the single row when the phases are the same piece of work moving through stages, since splitting it makes one commitment look like two competing ones. Prefer separate rows when the phases have different owners or could be cancelled independently, since the reader will want to track them apart.

Carry the commitment's own wording into the filled cells rather than paraphrasing it into a date. The wording holds qualifiers that a bare date drops, and the reader is comparing commitments as they were stated.

## Facts that arrive outside the tracker

Some commitments reach you verbally or by message and never make it into the source tracker before the report is due. These belong in the table exactly like the tracked ones, filled across their own span. Do not leave them out because the tracker does not carry them, and do not adjust their values to look consistent with the tracker.

## Verifying a schedule table

Check each of these against the source rather than against your memory of writing it:

1. Every item in scope appears as its own row, and no item appears twice.
2. Each row's filled span ends in the period its commitment names, and starts at the current reporting period.
3. Rows whose commitments share an endpoint have spans of equal length. This follows from every span starting at the same period, so an inequality means one phrase was misread, and one common cause is reading a phrase as naming a start when it names an end.
4. The identifying columns group rows the way the business groups them, not the way the source string happens to be formatted.
5. No row is filled to the end of the axis by default, and no row sits empty.
6. Every cell in the time columns carries a timing phrase rather than a status sentence. A grid is for scanning across items; a paragraph in one cell blows out the column width and defeats that. Status narrative belongs in the section's prose, not in the grid.

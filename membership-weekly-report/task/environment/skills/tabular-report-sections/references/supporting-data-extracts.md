# Supporting data extracts

Use this when a report section states a finding that rests on figures, for example a movement, a mix shift, or a comparison against a prior period. The finding goes in prose. The figures behind it go in a compact table underneath, so the reader can check the claim without opening the source system.

## What to carry, and what to leave behind

A working spreadsheet contains two kinds of columns and only one kind belongs in a report that goes upward.

**Business columns** are the quantities the business actually talks about: the totals, the components that sum to them, the breakdowns by product, tier, or channel. These go in.

**Internal working columns** are the ones the analyst added to check themselves: recomputations of a figure that already exists elsewhere in the sheet, share and ratio columns derived from neighbouring columns, reconciliation columns that exist to prove two totals agree. These stay out. They are scratch work. Carrying them in makes the reader wonder which of two similar looking columns is authoritative, and invites them to read a share as a change or a check column as a result.

Two signals identify a working column quickly: its header names a formula or a check rather than a quantity, and its value duplicates or is derived from a column already present. When a header and its neighbour differ only by being a ratio, keep the quantity and drop the ratio, unless the ratio is itself the reported finding.

Be careful of the reverse mistake: a column whose header sounds like scratch work can be the only place a genuinely wanted figure lives. Check what the value is before dropping the column, not just what the header suggests.

## How many periods

Enough for the reader to judge whether the current period is unusual, and no more. Two points cannot distinguish a rebound from a trend, so one prior period is never enough. The full history turns a supporting extract into a data dump and buries the periods that matter.

Derive the count from the metric rather than picking a number: carry enough periods to cover one full cycle of whatever cadence or seasonality the metric has, so that the reader can see the current period against its own comparable. For a metric with a weekly rhythm and no strong seasonality that usually lands at four or five rows. For something with a quarterly cycle it is more. For a metric whose whole point is a year on year comparison, the comparable period last year belongs in the extract even though the intervening ones do not.

Order most recent first, so the period being reported on is the first row the eye lands on, unless the recipient's own convention is chronological, in which case follow theirs. Finance and funder reporting is often strictly chronological and a reversed table reads there as an error.

## Formatting

Format for reading, not for machine round tripping. Group digits in large numbers. Render ratios the way the business states them rather than as raw decimals. Keep the source's own period labels rather than renaming them, so a reader can match a row back to the sheet.

Do not restate figures to more precision than the source carries, and do not silently round a figure that the prose above quotes exactly.

Where the recipient has an established format, theirs outranks everything in this section.

## Verifying a supporting extract

1. Every figure in the table matches the source cell it came from.
2. No internal working or reconciliation column came along.
3. No business column that the prose above refers to is missing from the table.
4. The period count is enough to show context, and the ordering puts the reported period first.
5. Any figure quoted in the prose appears in the table with the same value.

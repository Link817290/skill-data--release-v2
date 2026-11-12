# Claims about the data

A supporting extract is checked figure by figure. The sentences around it are not,
and they carry a different kind of assertion. This file is for those sentences.

## Four claim shapes, and how each fails

| Shape | Example form | How it goes wrong |
|---|---|---|
| Superlative | the highest since we started tracking | The window the claim implies is wider than the data you hold. A source that carries six periods cannot support a claim about a year |
| Count | across the last several periods | The number of rows in a source table is rarely the number of periods a reader would name. Header rows, subtotal rows, a partial current period and a blank spacer row all inflate a naive count |
| Range | it has run between these two values | Computed over the wrong subset, most often by including or excluding the current period inconsistently with the superlative in the previous sentence |
| Trend | it has grown every period | One reversal falsifies it, and a reversal in the middle of a series is easy to miss when reading down a column |

The count shape fails most often and is the cheapest to check.

## How to check

For each claim, before it goes in the draft:

1. Write down the window the claim asserts: which rows, which periods, inclusive
   or exclusive of the current one.
2. Recompute the claim over exactly that window, from the source rather than from
   the extract you built, since the extract is usually a subset.
3. Confirm the window you asserted is a window the source actually spans. A claim
   whose window exceeds the data is wrong even when the arithmetic inside it is right.
4. Where two claims in adjacent sentences share a window, confirm they used the
   same one.

## When to drop the claim instead

A claim of this kind earns its place only if it changes what the reader does.
A superlative across a window too short to mean anything, or a trend over three
points, costs the reader attention and gives back a fact they cannot act on.
Where the check in the previous section is awkward because the window is
ambiguous, that ambiguity is itself the answer: state the figure and drop the
characterisation.

## What this is not

This is not a rule against interpretation. The reader wants to know what moved
and why it matters, and a report that only restates figures has failed them in
the other direction. The distinction is between an interpretation that rests on
the figures in front of the reader, which is the job, and a derived assertion
about the wider series, which is a separate claim and needs its own check.

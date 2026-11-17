---
name: seismic-catalogue-statistics
description: Compute reproducible earthquake-catalogue diagnostics from event times, magnitudes, and coordinates, then make a cautious sequence screening decision.
license: Proprietary
metadata:
    domain: seismology
---

# Seismic catalogue statistics

## Preconditions

Run these calculations only after table rows have been normalized and quality-screened. Keep every source event in the inventory, but include an event in a statistic only when its required fields are finite and physically bounded. Report the included event keys for each statistic.

## Magnitude distribution

Preserve the magnitude scale or type supplied by the record; do not silently mix incompatible scales.

A magnitude--frequency slope is only meaningful above the catalogue's magnitude of completeness, so estimate completeness first. The standard diagnostic is a histogram of magnitudes at the reporting granularity of the catalogue, with the modal bin taken as the completeness estimate; the modal bin is where detection stops keeping up with the true power-law rise. Two conventions have to be pinned down before you compute anything, because both change the answer and neither is derivable from the data: the bin width, and which way a modal tie breaks. Take both from the governing rule for the audit and echo them into the report.

The maximum-likelihood (Aki--Utsu) slope is `log10(e)` divided by the mean magnitude of the usable set minus the completeness magnitude, with a half-bin correction on the denominator to compensate for binning. Two failure modes matter more than the formula:

- a denominator at or below zero, which happens when the usable set collapses onto the completeness bin, must return an undefined estimate with an explicit state — not a huge number that will then be compared against a threshold;
- a slope estimated from a handful of events is noise. Set a minimum usable count, state it, and return undefined below it.

Keep the full bin-count map, the usable set, and the included event keys, so a reviewer can recompute the slope without rerunning your code.

Report minimum, maximum, arithmetic mean, median, and maximum-minus-median dominance. Dominance is a screening indicator, not a physical parameter.

## Primary event and time behavior

Select the largest finite magnitude. Resolve an exact tie by earliest epoch and then by the stable event key. Compute the catalog span in hours and the primary's fractional position within that span. For post-primary behavior, retain only events strictly later than the primary and calculate elapsed-hour lags from epoch values, never formatted strings.

When at least three lags exist, use logarithmically spaced lag bins across the observed range. Record the edges, counts, and a least-squares slope of `log10(count + 1)` against log-lag-bin centers. A negative slope supports decay; a flat or positive slope is counter-evidence. A one-event or zero-span catalog has no meaningful fraction or decay estimate.

## Spatial behavior

Calculate the arithmetic latitude/longitude centroid from valid point coordinates and haversine distances from that centroid. State the earth-radius constant and report median and maximum radius in kilometres. Degrees are not kilometres. Treat these values as a diagnostic unless the governing screening rule explicitly supplies a spatial cut; for `regional-screen-v1`, they provide context and must not silently alter the classification.

## Screening rule

Adjudicate with a predeclared, versioned rule, and cite the rule's name and version in the report. The rule and its cut values come from the operating desk, the monitoring network's published procedure, or the assignment brief — never from inspecting this catalogue and picking cuts that produce a tidy answer. Post-hoc cuts are the single most common way a catalogue screening note becomes unfalsifiable.

A usable rule has this shape:

1. **An evidence floor, tested first.** Below a minimum event count, or with an undefined b estimate, the only honest disposition is insufficient evidence. This must be a separate outcome from "mixed": one says the data cannot answer the question, the other says the data answered it ambiguously. Collapsing them makes an empty page look like a considered finding.
2. **A mainshock-dominated test** combining three independent signals, because any one alone is weak: magnitude dominance over the population, the primary arriving early in the span, and enough later events for decay to be observable at all.
3. **A swarm test** keyed on the absence of dominance together with a magnitude-distribution slope in the range swarms occupy.
4. **A residual disposition** for supported records that match neither pattern.

Evaluate the branches in a fixed, documented order and stop at the first match, otherwise a record satisfying two branches gets a disposition that depends on your code's accidents. Carry a confidence level and record both the supporting and the opposing indicators for the disposition you chose — a mainshock call with a flat decay slope should say so.

## Common mistakes

Do not call every largest event an aftershock sequence, infer decay from row order, discard lower-magnitude events merely because they are below the modal bin, or impute a missing magnitude from another feed. Keep physical sequence status separate from the source page's publication status.

## Transferability

The separation of distribution, temporal rate, spatial spread, and adjudication transfers to volcanic swarms, induced-seismicity monitoring, acoustic event streams, and other finite scientific event catalogues.

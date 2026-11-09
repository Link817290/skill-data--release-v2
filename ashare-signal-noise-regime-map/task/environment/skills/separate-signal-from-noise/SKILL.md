---
name: separate-signal-from-noise
description: Organise A-share market observations into independent evidence clusters, using binary anchors, collinear-dimension dedup, cross-cluster confirmation, contradiction retention and review boundaries.
---

# Separate signal from noise

Use this Skill when a task asks you to tell durable signal from short-lived shock across market-state samples.

## Core principle: evidence only confirms when it is independent

Two highly correlated indicators moving the same way are **not two pieces of evidence**. The usual trap in a market panel: the breadth proxy and the earnings proxy are themselves built from price, so all three moving together looks like three-dimensional confirmation when it is one price series counted three times.

Before you start, check the pairwise correlations between fields, or read the field notes describing what each one is composed from. Indicators that explain each other belong in **one cluster, and a cluster emits one direction**.

## The four independent clusters

| Cluster | Members | Emits |
|---|---|---|
| Trend | price persistence, market breadth, earnings impulse | direction (positive / negative / none) |
| Odds | drawdown and valuation percentile, equity risk premium | direction (positive / negative / none) |
| Liquidity | turnover liquidity, credit conditions | direction (positive / negative / none) |
| Event | policy intensity, event noise, volatility shock | **intensity only, no direction** |

The event cluster emits no direction: a high-intensity policy event can be support or disturbance depending on whether other clusters confirm it. Treating an event as directional evidence is the most common source of misjudgement.

## Anchors are binary triggers, not continuous scores

Do not score each dimension 0–1 and take a weighted sum. Set one cut line per dimension; **crossing it records an anchor**, not crossing records nothing. The downstream decision depends on how many clusters emitted a direction, and continuous weighting lets a pile of weak evidence accumulate into a falsely strong conclusion.

## How to set the cut lines

Do not reach for remembered numbers or industry rules of thumb, and do not reverse-engineer them from the template. Calibrate against **the sample's own percentiles**: for instance, take the trend cut line at an upper/lower percentile of that field across the full panel, and treat extreme events at a high percentile. The lines then adapt to the panel and stay reproducible.

## How a cluster picks its direction

- Trend: each of the three members votes `+1` / `-1` / `0`, and the **net vote must be at least +2 or at most -2** before the cluster emits a direction. One vote or a split means "no direction": `[+1,+1,-1]` nets to +1 and remains neutral. This is deliberate — an opposing member is not an abstention, and a single net vote does not confirm a trend.
- Odds and Liquidity: the sign of the members' net vote is the direction.
- Event: hitting any member records one unit of intensity.

## Regime is a sequence, not a row-by-row verdict

The samples are ordered in time and **must be processed in order**. A cluster reading for the current window is only a raw reading, not the final regime: regimes have inertia, and one window's change is not enough to declare a switch.

Compute the raw reading for every window first, then hand it to the regime mapping for a second, time-aware pass. Do not reach a final verdict on the first pass.

## Change evidence and the full anchor set are two different things

The task contract asks `evidence_ids` to report only **what changed relative to the previous window**. But when you judge whether a regime can persist, what matters is the **complete anchor set for the current window** — whether the regime's defining conditions still hold — not the change.

The two answer different questions, so do not mix them: the evidence column answers "what changed this period", the persistence test answers "does this regime still stand".

## The evidence set is one convergence pass, not a running list

`evidence_ids` is a **set**: one missing entry and one extra entry both stop it from being that set. Appending as you analyse rarely produces a big error — it produces a one-or-two-entry difference on every sample, which looks close everywhere and is exact nowhere.

### Derive the change set, do not judge it

What the column reports is a **difference between two windows**, not a description of this
window. That distinction is where most of the error comes from: judging "did this change?"
while reading a single window means comparing against a remembered impression of the previous
one, and impressions drift.

Compute it instead, in two passes over the panel:

**Pass 1 — full anchor set per window.** For every window, write out the complete set of
anchors that hold in it: every dimension that has crossed its cut line, regardless of whether
it also held last window. This is a property of the window alone, so it can be built without
looking at neighbours, and it is the same set the persistence test needs later.

**Pass 2 — difference adjacent sets.** For each window, take the set difference against the
previous window's set in both directions. Anchors present now but not before are the additions;
anchors present before but not now are the disappearances. Both belong in the column — a
dropped anchor is a change, and forgetting the disappearances is the single most common way the
set comes out short.

Three consequences follow directly, and each is easy to get wrong by hand:

- An anchor that held in both windows is **not** in the change set, however important it is to the regime. A strong, stable signal can legitimately have almost nothing in its evidence column.
- The first window has no predecessor, so it carries its full anchor set.
- If two adjacent windows have identical anchor sets, the difference is empty; fall back to the current window's full set rather than leaving the column blank.

Attach the event IDs the event table associates with the sample after the difference is taken;
they are not part of the anchor comparison.

Once the change set is derived this way, use the rules below to decide what belongs in it.

1. **Enumerate first, then cut.** List every dimension that moved this period, including the ones you immediately judge unimportant, and only then rule each one in or out. Working the other way — writing entries as they occur to you — guarantees you miss whatever did not come to mind at the time.
2. **Use only the anchor line to decide.** Deciding "does this go in" is the same act as deciding "is there an anchor": crossing the cut line goes in, **"close to it" and "nearly there" do not**. Never make an exception because a move feels narratively important; that is exactly how the set gets contaminated.
3. **Deduplicate votes, enumerate anchors.** When collinear dimensions move together, the cluster emits one direction, but every triggered anchor still belongs in the full anchor set. Compute the change set from those complete sets; do not replace several anchor IDs with a representative.
4. **Do not delete corroborating changes.** Removing one anchor may leave the label or action unchanged because other anchors corroborate it. That does not remove it from the reported change set. A deletion test checks the independence of a vote, not whether a triggered anchor must be reported.
5. **Keep one ruler across samples.** The hardest error to notice is a ruler that drifts between samples: a move of the same size gets recorded early on and skipped later. Once the set is drafted, sweep the samples side by side and confirm that comparable moves were handled the same way everywhere.

Point 5 is **the easiest one to violate while judging sample by sample**, because each sample looks defensible on its own. It is also the main reason every sample ends up slightly off.

The per-cluster checklist is in `references/evidence-matrix.md`.

## Discipline

- Do not use future data or outside news.
- Do not let the strongest narrative replace structured evidence.
- Keep contradictions; do not average positive and negative evidence away. Cheap valuation with earnings still falling is not a clear bottom.
- Anchor every conclusion to an evidence ID from the task contract; never invent IDs.
- Record every anchor that was hit, not just the strongest few.

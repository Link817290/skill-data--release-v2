---
name: map-ashare-strategy-regime
description: Map independent evidence clusters onto regime labels, allocation actions and flag fields, then run the workbook closure checks.
---

# Map A-share strategy regimes

Use this Skill once the evidence is already organised into independent clusters, to produce the final output.

## What the labels mean

- `SIGNAL`: several independent clusters point the same way, with no cluster pointing the other way.
- `NOISE`: the event cluster has intensity but the trend cluster emits no direction — the disturbance is real, but nothing confirms it.
- `MIXED`: positive and negative clusters coexist; the directional conflict is genuine.
- `REVIEW`: fewer than two clusters emit a direction, so the evidence cannot support a position decision.

## Decision order (must short-circuit in this order)

The order is itself the method: rule out "this is only a disturbance" first, then "there is not enough evidence", and only then talk about direction.

```
1. Event cluster has intensity AND trend cluster has no direction  → NOISE
2. Fewer than 2 clusters with a direction                          → REVIEW
3. Positive and negative clusters both present                     → MIXED
4. Otherwise (>=2 clusters agreeing, none opposing)                → SIGNAL
```

The common mistake is inverting the order — checking direction before noise — which reads a great deal of event-driven jitter as trend confirmation.

## Action mapping

An action is a portfolio response, not an index forecast. Gross exposure changes and structural
rotation answer different questions, so decide them separately.

Work the label down this order and stop at the first line that matches. The order matters: the
overrides sit above the default, so checking the default first gets the wrong answer on exactly
the windows the overrides exist for.

```
REVIEW                                                → REVIEW_ONLY
NOISE   and near-horizon decline is pronounced        → REDUCE_RISK
NOISE                                                 → HOLD
SIGNAL  negative direction                            → REDUCE_RISK
SIGNAL  positive, style dispersion crosses its line
        and valuation no longer cheap                 → ROTATE_STYLE
SIGNAL  positive, resting on policy support
        while breadth has not spread                  → ROTATE_INDUSTRY
SIGNAL  positive                                      → ADD_RISK
MIXED   style dispersion crosses its line             → ROTATE_STYLE
MIXED   breadth evidence holds (spreading or narrowing)→ ROTATE_INDUSTRY
MIXED                                                 → HOLD
```

Three things this order encodes, each of which is a common miss:

- A positive `SIGNAL` does not default to `ADD_RISK`. Two conditions divert it to a rotation first, and both are checked against evidence you already have in the clusters — they are not judgement calls to skip when you are unsure.
- `MIXED` never moves gross exposure. It rotates or holds; there is no path from `MIXED` to `ADD_RISK` or `REDUCE_RISK`.
- `NOISE` is `HOLD` unless the near-horizon decline is pronounced. Do not read event intensity as a reason to act.

Derive the action from the **final** regime after the inertia layer, never from the raw reading,
then apply the turnover constraints. An action that is right for the raw reading and wrong for
the final regime scores as wrong.

## Second layer: regime inertia (process in time order)

The four branches give you a **raw reading for the current window**; the final regime still has to pass through inertia:

```
no previous window                        → final = raw reading
raw reading == previous final regime      → hold
raw reading == previous raw reading       → two consecutive windows agree, switch confirmed
otherwise                                 → hold the previous regime (switch unconfirmed)
   but the previous regime must still be supported this window:
     NOISE  needs event-cluster intensity again this window
     SIGNAL needs >=2 directional clusters again this window
     MIXED  retains the previous unresolved conflict until a new raw reading is confirmed
     REVIEW retains the previous unresolved uncertainty until a new raw reading is confirmed
   if support is missing, fall back to this window's raw reading
```

The point: **a single window cannot flip the regime**, a switch needs two consecutive windows agreeing; but a regime cannot persist indefinitely either, and must be given up once its defining conditions disappear.

For `MIXED` and `REVIEW`, support in this inertia layer means the earlier conflict or
uncertainty has not yet been resolved by two consecutive matching raw readings. Their
current raw reading need not itself be `MIXED` or `REVIEW`. Retain them during an
unconfirmed switch; switch when the two-window confirmation occurs. Alternating raw
readings leave that uncertainty unresolved. This is a state-memory rule, not a claim
that opposed clusters or insufficient clusters must recur in every retained window.
Assess `contradiction_flag` from current clusters and `review_flag` from the final label.

Re-derive the action from the **final** regime; do not carry over the action implied by the raw reading.

### Working the layer

Do it in two passes over the whole panel, because the final regime for a window needs the
previous window's final regime, which does not exist yet while you are reading that window's
clusters.

**Pass 1** — walk every window in order and record only its cluster directions and the raw
reading from the four-branch decision. Nothing final, no actions.

**Pass 2** — walk them again in order, carrying forward the previous window's raw reading and
its final regime. Apply the inertia rules, derive the action from the final regime, then apply
the turnover constraints against the previous action.

One thing to get right: the switch test compares **this raw reading with the previous raw
reading**. Comparing it against the previous *final* regime is a different test and moves the
turning points.

Where a window is genuinely ambiguous, spend your effort on getting its label and action right
rather than on litigating whether it is a turn. The label and action are judged on every
window; the turning points are a smaller, harder set, and a well-labelled panel produces
sensible turns as a by-product.

## Third layer: turnover constraints on actions

A portfolio cannot rebalance heavily every period. `ADD_RISK` / `REDUCE_RISK` degrade to `HOLD` when:

- the previous action was the same (no consecutive adds or consecutive reductions)
- the previous action was its exact opposite (no direct flip between adding and reducing)
- the previous action was `REVIEW_ONLY` (after a review, observe for one period first)

`REVIEW_ONLY` and the two rotation actions are not subject to this constraint.

## Flag fields

- `contradiction_flag = TRUE` if and only if a positive and a negative cluster both survive the dedup. Assess it on the clusters themselves, never by reading it off the label: it is **not** equivalent to `MIXED`. A row can carry opposed clusters and still resolve to a directional or a review label, and a `MIXED` label can arise without two opposed clusters. Decide the label first, then assess this flag independently.
- `review_flag = TRUE` if and only if the label is `REVIEW`.

## Closure checks

The full action-mapping principles and two common mistakes are in `references/action-closure.md`.


- `REVIEW` ⇔ `review_flag=TRUE` ⇔ `action=REVIEW_ONLY`; all three must hold together.
- `REVIEW_ONLY` must not appear with `SIGNAL` / `NOISE` / `MIXED`.
- A label that has committed to a direction must not cite "insufficient evidence" IDs.
- Note that the evidence column carries **changes**, not assertions about the current state. So do not reverse-engineer whether a label holds from "how many directional anchors this row cites" — a stable, persisting SIGNAL may well have only one or two anchors that changed. Judge whether the regime holds from the **complete anchor set for the window**; decide what goes in the evidence column from the **changes**.
- Every row needs an evidence anchor, and each sample ID appears on exactly one row.

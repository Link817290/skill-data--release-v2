# Treasury-stock and pool reference

For a right with `N` shares, exercise price `K`, and scenario market price `P`, the incremental-share calculation is based on the cash exercise proceeds being used to repurchase shares at `P`. The result is zero for an out-of-the-money right. State the formula and the scenario inputs in the workbook so an alternate reviewer can recompute it.

Keep these concepts separate:

| Concept | Typical evidence | Workbook treatment |
|---|---|---|
| Potential shares | award balance and performance basis | scenario columns |
| Incremental option shares | options, exercise price, market price | formula row |
| Plan capacity | available pool and share-counting rule | pool schedule |
| Exercise activity | event counts and proceeds | exercise ledger |
| Dilution percentage | potential shares / chosen denominator | summary formula |

When a plan uses a share multiplier for full-value awards, apply it only to pool consumption. Never reuse that multiplier in the treasury-stock calculation.

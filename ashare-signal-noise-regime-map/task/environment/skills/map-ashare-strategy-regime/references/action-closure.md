# Action closure principles

An action answers "how should the portfolio respond", not "where will the index go".

## Gross exposure vs structure

- Adjust gross risk exposure when the direction is clear and no cluster opposes it (`SIGNAL`). The only non-SIGNAL exception is defensive: a `NOISE` window with a pronounced near-horizon decline may `REDUCE_RISK`; it never adds risk.
- When directions conflict (`MIXED`), leave gross exposure alone and express the view through structural rotation.
- When the direction is unclear (`REVIEW`), do not convert uncertainty into a trade.

## Choosing between the two rotation actions

- Style dispersion crosses its cut line → `ROTATE_STYLE` (growth/value, large/small rebalancing)
- Otherwise, if breadth evidence holds (spreading or narrowing alike) → `ROTATE_INDUSTRY`
- Neither stands out → `HOLD`

## Two things that are easy to get wrong

1. **Cutting into the bottom.** Valuation is cheap and the equity risk premium is high, but earnings are still falling — this is `MIXED`, not a clean negative signal, and should not be `REDUCE_RISK`.
2. **Reading a policy impulse as trend confirmation.** When policy intensity is high but the trend cluster has no direction, the answer is `NOISE`, never `ADD_RISK`. Use `HOLD` while the near-horizon decline is not pronounced; otherwise apply the documented defensive `REDUCE_RISK` override.

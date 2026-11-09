# Task: build an A-share signal-versus-noise regime map

You are a strategy research assistant. Using the frozen materials in `/workspace`,
judge each A-share market-state sample from 2020 to 2024 and save the result as:

`/workspace/regime_map.xlsx`

No network access. Do not use outside market data or news; use the workspace files only.

## Available materials

- `market_snapshots.csv`: market, valuation, liquidity, credit, earnings and style proxy variables for each sample window.
- `events.csv`: notable policy, event and noise annotations near each sample.
- `indicator_dictionary.csv`: field meanings, directions and missing-value handling.
- `regime_map_template.xlsx`: the output template.
- `output_contract.json`: the column names, enumerations and evidence ID list you must satisfy.
- `source_manifest.json`: runtime data sources, freeze date and cleaning notes.

## Output requirements

Fill in the template and save it as `/workspace/regime_map.xlsx`. Every `sample_id` needs
exactly one row, carrying at least:

- `sample_id`
- `regime_label`: `SIGNAL` / `NOISE` / `MIXED` / `REVIEW`
- `action`: `ADD_RISK` / `REDUCE_RISK` / `HOLD` / `ROTATE_STYLE` / `ROTATE_INDUSTRY` / `REVIEW_ONLY`
- `evidence_ids`: evidence IDs separated by `|`, `;` or line breaks; event IDs may be cited alongside them.
  **Record only the evidence anchors that changed relative to the previous window** — those
  that appeared and those that disappeared — not every anchor that holds this period.
  For the first window, record all of the current window's anchors; if two adjacent windows
  have identical anchors, fall back to recording all of the current window's anchors.
  In either case, attach the `EVT_` event IDs that `events.csv` associates with that sample.
- `contradiction_flag`: `TRUE` / `FALSE`
- `review_flag`: `TRUE` / `FALSE`
- `rationale`: a short explanation is required on every row. Its wording and prose
  quality are not scored, but the nonempty field is part of the output contract and
  supports human review.

## How to work through it

These are working rules for reaching each judgement, not the criteria your output is
marked against:

1. Separate durable signal from short-lived noise; a single day or single event shock does not substitute for cross-dimensional confirmation.
2. Record price trend, valuation odds, relative equity attractiveness, liquidity and credit, earnings impulse, sector breadth, style dispersion and event evidence separately.
3. When positive and negative evidence coexist, do not force a one-sided `SIGNAL`; consider `MIXED` or `REVIEW`, and flag the contradiction.
4. Distinguish "not enough evidence" from "event disturbance": when the evidence base cannot support a position decision, follow the review discipline; when event or volatility intensity is high but the trend is not yet confirmed, that is noise rather than review.
5. An action is a portfolio response, not an index forecast. `ROTATE_STYLE` and `ROTATE_INDUSTRY` express structural responses; `ADD_RISK` and `REDUCE_RISK` move gross risk exposure.

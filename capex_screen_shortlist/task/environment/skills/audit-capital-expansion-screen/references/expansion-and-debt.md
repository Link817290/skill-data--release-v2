# Expansion Intent and Debt Purpose

## Total-asset growth

Provide total assets for 2018 through 2021. Apply the annual-growth equation with a strict comparison against the bar you reasoned to, year by year. Do not replace annual observations with a three-year average or CAGR.

## Interest-bearing debt

Provide direct interest-bearing debt or a component-complete breakdown covering short-term borrowings, the current interest-bearing portion, long-term borrowings, bonds payable, and other explicit interest-bearing debt. State whether lease liabilities are included.

Distinguish three cases. A missing year, missing statement, or absent required field is unresolved and must not become zero. A present standardized provider field whose value is `null` follows the dataset manifest's `standardized_null` policy: record the raw null and normalize it as a non-reported line-item balance of zero for the reproduction profile. A disclosed numeric zero remains an ordinary zero. Do not apply this policy to arbitrary absent keys or qualitative facts.

Compute `cash_coverage` yourself, including the invalid-denominator behavior described in `evidence-and-missing-data.md`.

## Debt-purpose evidence

Provide annual cash paid to acquire or construct long-term assets and annual borrowing cash inflows as separate raw facts. The annual positive-capex gate is a quantitative deployment proxy, not a causal attribution of borrowing use.

Use construction in progress, additions to fixed assets, funded-project disclosures, and stated borrowing uses to grade the stronger purpose conclusion. Strong cash coverage, simultaneous borrowing, or a capex/borrowing ratio alone does not prove that borrowing funded capital expenditure. Use `QUANTITATIVE_PROXY_ONLY` when only co-movement is available and `REVIEW` for the stronger purpose claim. Never invent a capex-to-borrowing threshold to force agreement with a published list.

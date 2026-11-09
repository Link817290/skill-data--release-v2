# Evidence and Missing Data

## Evidence record

Keep a working record of `source_id`, `fiscal_year`, `scope`, `unit`, `raw_label`
and `raw_value` for every raw fact you use. This record is scaffolding, not a
deliverable: the worksheet has no column for it. It exists so that a ratio can be
rebuilt from its inputs when a later figure contradicts it, and so that a
`REVIEW` can be defended as an evidence state rather than a guess. The source id
is the one the snapshot itself carries in `official_audit_source_ids`; there is
no document page to cite. Where the structured mirror is internally inconsistent,
revise the input and everything downstream of it rather than footnoting a stale
number.

## Three states, not two

The structured mirror distinguishes states that look alike and are not:

| State in the source | What it means | Effect on a test |
| --- | --- | --- |
| Field present, value is a number including 0 | The company reported that line item, and it is zero | A fact. The test runs on it. |
| Field present, value is `null` | The line item is not a reported item for this company | Treat as a zero balance, reproduction profile only |
| Field, statement or year absent from the row | Evidence is missing | The test cannot be formed → `REVIEW` |

Never extend the null policy to an absent key, a missing statement, a missing year,
or an unresolved qualitative fact. Turning an absence into a zero manufactures a
conclusion the filings do not support — it is the single most common way this audit
goes wrong. `REVIEW` from incomplete evidence is a statement about auditability, not
a negative finding: say which input is missing and why it blocks the test, and never
upgrade it on plausibility.

## A zero denominator is a result, not an obstacle

A company that reports zero interest-bearing debt has an unbounded cash-coverage
ratio. That is a finding — no debt risk to cover — not a missing input. The
distinction that matters is the source of the zero, not the arithmetic:

- denominator components reported and summing to zero → the ratio is unbounded,
  the test passes;
- a denominator component absent from the mirror → the denominator cannot be
  formed, and the company holds at `REVIEW`.

Two companies can both show "no ratio" on screen and require opposite verdicts.
Check which situation produced it before recording anything.

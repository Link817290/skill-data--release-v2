# Slope-Support Tender BOQ Scoring Rubric

The scored deliverable is `边坡支护专业分包招标清单.xlsx`. The evaluator is
condition blind and uses the same contract for with-skill and no-skill outputs.
Equivalent Chinese or English headings, professional paraphrases, section-tab
layouts, row order, and consistently updated sequence identifiers are accepted.

## Strict Score

Strict is `0.30 * deterministic program checks + 0.70 * source-bound semantic business coverage`. There is no score
floor, hard cap, or score-target gate.

The program score is:

`0.10 coverage + 0.05 identity/unit + 0.10 technical content + 0.25 quantity accuracy + 0.05 pricing readiness + 0.20 scope completeness + 0.10 traceability + 0.15 control ledger`

The deterministic program score remains a mechanical floor for physical
quantity, formulas, structure, and link integrity. The final settlement gives
the source-bound semantic score 70% because the central professional outcome is
whether a bidder-facing regrouping preserves source-supported work objects,
measurement bases, conflict treatment, and completed controls; a parser cannot
reliably infer those relationships from exact line identity alone. This is a
business-boundary allocation, not a target fitted to any rollout identity.

The allocation makes physical quantity correctness the largest single check
inside the deterministic component:
wrong or zero quantities cannot be offset by a polished register. Exact
three-section scope remains substantial because omitted tender work creates
claims and non-comparable bids. Traceability and technical content distinguish a
source-led take-off from a copied item list. Pricing formulas are smaller because
they are mechanical once the physical BOQ is correct. The control ledger is
material but cannot outweigh the BOQ itself.

- `coverage` is the one-to-one matched share of the 95 professional items,
  reduced by unsupported traceable additions.
- `identity/unit` measures payable-object name equivalence and correct physical
  units for matched lines.
- `technical content` measures pricing-changing characteristic elements and a
  usable measurement rule. Open professional equivalence is reviewed by the
  semantic judge rather than isolated keyword counts.
- `quantity accuracy` compares matched numeric quantities with the author
  professional record only under the correct unit. Full credit uses the greater
  of `0.01` absolute or `0.1%` relative tolerance; credit declines continuously
  to zero at a 10% error.
- `pricing readiness` requires bidder unit prices to remain blank and the total
  cell to multiply that row's quantity and bidder-price cells.
- `scope completeness` measures progress toward 80% usable matched coverage in
  the weakest exact construction section. Other sections cannot compensate.
- `traceability` requires an issued-file locator, reproducible quantity basis,
  and accepted basis state on matched items.
- `control ledger` is `0.25 link integrity + 0.25 parameter coverage + 0.15
  uncertainty control + 0.35 quantitative closure coverage`. Closure carries
  the largest ledger share because it demonstrates an actual reconciliation,
  while a register that merely lists links is not completed engineering work.

Exact repeated rows in the selected BOQ receive a continuous integrity factor
`95 / (95 + exact_repeated_rows)`. Auxiliary indexes are excluded before this
calculation. There is no global duplicate-row zero.

The source-bound semantic score is a weighted mean over eight independently
reported dimensions: exact section boundary (.08), source-supported family
coverage (.17), equivalent decomposition (.17), quantity-basis reproducibility
(.16), technical characteristics (.10), uncertainty/conflict control (.10),
completed closure (.12), and audit-control usability (.10). Each dimension
accepts substantive partial credit at 0/.25/.5/.75/1. This keeps a valid
material-derived regrouping visible while retaining deductions for omitted
families, stale quantities, incompatible units, or future-only closures. Every
decision cites exact candidate and source evidence. A source-stated basis
identifies a field or cell; a calculated basis states material inputs and an
operation; a provisional basis states the remaining measurement path. Restating
only the final number is insufficient.

## Lenient Score

Lenient is an independent issuance-readiness conjunction. It requires a readable
workbook; all required BOQ columns; all three exact sections; at least 80% usable
matched rows, characteristics, complete traceability, and quantity accuracy;
the full control-ledger contract; no exact repeated selected-BOQ rows; and all
four semantic criteria. It is not derived from a strict-score threshold.

## Table And Header Handling

The evaluator first identifies real BOQ tables by the sequence, name,
characteristics, measurement-rule, unit, and quantity fields. A consolidated
audit index cannot displace complete section-specific quotation tables. Chinese
headings such as `税前单价（元）`, `税前合价（元）`, and `证据定位` are accepted
along with their documented equivalents. One physical column cannot satisfy two
semantic fields.

Golden contains a 95-row quantity-provenance ledger and reports the actual
linked values and numerical differences for C-01 through C-03. The exact Golden
fixture must score strict `1.0` and lenient `1.0` under both fresh and replay
semantic measurement.

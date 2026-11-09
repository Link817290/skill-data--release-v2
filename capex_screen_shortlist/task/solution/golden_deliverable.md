# Reference deliverable

The reference gives one call for every issued company: **6 PASS**, **47 FAIL**,
and **7 REVIEW**. REVIEW is reserved for companies whose unavailable binding
quantity could still change the call. A disclosed zero, standardized present null,
and absent field remain separate source states. An aggregate may be recovered only
through a disclosed same-statement accounting identity, with that source recorded.

`golden/shortlist.xlsx` contains four sheets:

- `Screen`: the 60 company calls and six source-recomputed decision metrics;
- `Conventions`: the adopted definitions and four controlling lower bounds;
- `Methodology`: window, profiles, calibration, source boundary and evidence limits;
- `Company audits`: both profile readings plus CIP, goodwill, debt-purpose,
  signed-profit, missingness, and annual numeric vectors for every company.

The reference uses the narrative profile for the committee call and reports the
strict profile separately. Its repaired round bars yield sequential admissions
of 27/48, 17/27, 12/17 and 6/12, so every gate contributes without emptying the
screen. `603233.SH`'s provider-null 2020 total assets equals the disclosed
liabilities-and-equity total in the same balance sheet.

Regenerate the workbook from issued sources with:

```sh
python3 solution/normalize_and_solve.py \
  --workspace environment/workspace \
  --output /tmp/answer.json \
  --workbook ../golden/shortlist.xlsx
```

The current scorer derives financial truth from the issued snapshots and uses a
source-bound semantic judge for workbook meaning and professional completion.
Programmatic arithmetic sets the evidence ceiling for the affected responsibility
only. See `RUBRIC.md` and `tests/scoring_contract.json` for settlement.

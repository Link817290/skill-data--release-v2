# Capital-Expansion Screen - Shortlist

This task asks for one source-grounded capital-expansion screen over 60 A-share
manufacturers. The deliverable is `/workspace/shortlist.xlsx`: one committee call
per company, the figures supporting it, both professional profile readings, and
the audits required to distinguish data-backed expansion from unsupported causal
claims.

## Scoring

The verifier has one source-bound path. It reads the actual workbook, asks the
semantic judge to normalize the workbook's own layout, definitions and prose, and
then recomputes every financial quantity from the 60 issued provider snapshots.
The judge cannot supply hidden bars or reference membership. Programmatic source
arithmetic limits only the responsibility supported by a wrong displayed figure
or audit vector; one bad number does not multiply unrelated responsibilities.

Strict is an additive weighted completion score:

| owner | weight |
| --- | ---: |
| structure | 5 |
| core method and calibration | 10 |
| committee decision | 25 |
| two profile readings | 15 |
| CIP consequence analysis | 10 |
| goodwill trajectory | 10 |
| debt-purpose discipline | 15 |
| signed-profit handling | 5 |
| missing-evidence handling | 5 |

The weights follow the decision's business use. The committee call is the largest
owner because it is the delivered action. Profile comparison and debt-purpose
discipline are next because either can turn a plausible screen into an unsuitable
financing recommendation. CIP and goodwill each receive a material but narrower
share because they can reverse the interpretation of asset growth. The remaining
controls each receive 5%: all are necessary, while none substitutes for the
company-level decision. The weights sum directly; they are not loss multipliers.

An unresolved call remains attached to its company and loses the relevant
decision credit once. There are no cascading gate multipliers, squared
over-selection discounts, hidden PASS-count requirements, or fixed wording list.

Lenient is independent binary business completion. It requires a readable screen
with all 60 source companies exactly once, source-correct displayed metrics,
calls coherent with the workbook's disclosed policy, and three separately judged
obligations: a substantive screen, professional analysis, and evidence restraint.
It contains no fixed PASS/REVIEW count or strict-score threshold. A missing or
unreadable candidate workbook is a valid zero; judge or source infrastructure
failure is `UNMEASURED` and writes no numeric reward.

## Golden

`golden/shortlist.xlsx` is generated from the issued structured statements by
`task/solution/normalize_and_solve.py`. It contains `Screen`, `Conventions`,
`Methodology`, and `Company audits` sheets. The repaired calibration uses four
round, source-audited bars: annual asset growth above 10%, cash/debt above 2x,
revenue/ending fixed assets above 3x, and operating cash flow/net profit above
1x. On 48 fully formable companies these admit `27 -> 17 -> 12 -> 6`; the final
distribution is 6 PASS, 47 FAIL and 7 REVIEW. `603233.SH` uses the same balance
sheet's disclosed `TOTAL_LIAB_EQUITY` for its provider-null `TOTAL_ASSETS`, with
that accounting-identity source recorded.

## Verification

The live verifier needs `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, and optionally
`LLM_JUDGE_MODEL`. Set `LLM_JUDGE_CACHE_DIR` to preserve exact source-bound
judge records and use `LLM_JUDGE_MODE=replay` for offline replay. `task/tests/test.sh` writes one strict reward and one
binary completion reward. A cache miss with no judge endpoint exits 2 and writes
only an `UNMEASURED` diagnostic.

The task is condition-blind: the same scorer, source packet, contract and judge
settings apply to with-skill and no-skill artifacts.

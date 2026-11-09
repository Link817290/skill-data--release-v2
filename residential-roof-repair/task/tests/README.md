# Evaluation

Run `python -B tests/entrypoint.py --submission-dir /external/output --input
environment/workspace/input --out /external/verifier`. The entrypoint reads the
two published Chinese filenames and recalculates submitted workbook formulas on
an isolated copy before scoring. A numeric-only author check is available through
`tests/verify.py`; the published reward always uses the complete mixed evaluator.

The semantic judge validates exact candidate and source citations. Configure the
six `LLM_JUDGE_*` variables documented in the package README. `auto` uses the
request-bound Golden fixture when its complete artifact hash matches and judges
other submissions live. `fresh` always calls the configured Responses-compatible
endpoint. `replay` fails closed if the exact fixture is unavailable.

No candidate macros or generation scripts execute. Missing semantic evidence,
an invalid model response, or a source/reference conflict is unmeasured rather
than numeric-only credit. Runtime receipts and general candidate caches belong
outside the package.

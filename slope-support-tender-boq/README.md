# Slope-Support Tender BOQ

This package asks an agent to prepare an editable specialist subcontract bill of
quantities from the supplied geotechnical report, support calculation, CAD
drawings, and procurement scope note. The required output is
`/workspace/边坡支护专业分包招标清单.xlsx`. The actor receives only the issued
workspace and, in the with-skill condition, the three packaged engineering
skills. Golden, evaluator references, and judge credentials remain evaluator
only.

## Build

All images use `harbor-claude-code-aggregated:1.3`, which provides the pinned
DWG and spreadsheet tooling required by this task:

```bash
docker build --target with-skill -t slope-support-tender-boq-with-skill:1.3 task/environment
docker build --target no-skill -t slope-support-tender-boq-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t slope-support-tender-boq-verifier:1.3 .
```

The actor is offline. The separate verifier may use public networking for the
source-bound semantic judge.

## Oracle And Evaluation

Run `task/solution/solve.sh` to reproduce the Golden workbook. Run
`task/tests/test.sh /workspace` to score a candidate. The mixed evaluator
combines deterministic workbook, quantity, formula, scope, traceability, and
control checks with evidence-bound professional semantic review.

Configure these evaluator variables:

- `LLM_JUDGE_BASE_URL`
- `LLM_JUDGE_API_KEY`
- `LLM_JUDGE_MODEL`
- `LLM_JUDGE_CACHE_DIR`
- `LLM_JUDGE_MODE`
- `LLM_JUDGE_TIMEOUT_SECONDS`

`LLM_JUDGE_MODE` accepts `auto`, `fresh`, and `replay`. The package includes
only the exact request-bound Golden replay fixture. Changed artifacts are judged
live in `auto` or `fresh` mode; `replay` fails closed when no exact fixture is
available.

The author professional XLS is retained under `golden/reference/` only to make
the benchmark quantity provenance reproducible. It is not copied into either
actor image and is not available during rollout.

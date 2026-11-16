# Construction Payment Application

Prepare the fifth progress-payment workbook and Chinese submission letter from the
issued project records. The actor receives only the workspace inputs and, in the
with-skill condition, the payment-application skill. Golden, the Oracle, evaluator
sources, and judge credentials are evaluator-only.

## Build

All images use `harbor-claude-code-aggregated:1.3`:

```bash
docker build --target with-skill -t construction-payment-application:1.3 task/environment
docker build --target no-skill -t construction-payment-application-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t construction-payment-application-verifier:1.3 .
```

The actor images share the same offline runtime and issued inputs. Only the
with-skill image contains `/skills`. The verifier is separate and may use public
network access for semantic judging.

## Oracle And Evaluation

Run `task/solution/solve.sh` to produce the two deliverables under
`/workspace/output`. Run `task/tests/test.sh` to evaluate that directory. The
deterministic evaluator derives quantities, prices, payment arithmetic, balances,
and cross-file amount consistency from the issued records. The evidence-bound
semantic judge evaluates professional equivalents for submission readiness,
pending-item handoff, document authority, and business scope.

Configure exactly these external judge variables:

- `LLM_JUDGE_BASE_URL`
- `LLM_JUDGE_API_KEY`
- `LLM_JUDGE_MODEL`
- `LLM_JUDGE_CACHE_DIR`
- `LLM_JUDGE_MODE`
- `LLM_JUDGE_TIMEOUT_SECONDS`

`LLM_JUDGE_MODE` accepts `auto`, `fresh`, and `replay`. Cache identities bind the
model, complete request, sources, criteria, and candidate. The package contains
only the exact Golden replay fixture; changed artifacts miss it and require a live
judge in `auto` mode or fail closed in `replay` mode.

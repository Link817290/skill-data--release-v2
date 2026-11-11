# Historical Sanctions Alert Review

This package asks an agent to complete the supplied sanctions-alert and AML review
template as `/workspace/alert_review.json`. The actor works offline from the supplied
transaction records, regulatory sources and ownership report. Golden, evaluator facts,
the Oracle and judge credentials are evaluator-only.

## Build

All runtime images explicitly use `harbor-claude-code-aggregated:1.3`:

```bash
docker build --target with-skill -t historical-sanctions-alert-review:1.3 task/environment
docker build --target no-skill -t historical-sanctions-alert-review-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t historical-sanctions-alert-review-verifier:1.3 .
```

The with-skill and no-skill images derive from the same `runtime` stage. Only the
with-skill image copies `/skills`. Both actor images use `network_mode = "no-network"`;
the separate verifier uses public networking for semantic judging.

## Oracle And Evaluation

Run `task/solution/solve.sh` with the supplied workspace to generate the reference
artifact. Run `bash task/tests/test.sh /workspace/alert_review.json` to score an artifact.
`AGENT_WORKSPACE`, `VERIFIER_OUT` and `ARTIFACTS_OUT` select isolated runtime paths.

The mixed evaluator uses deterministic structure, closed categorical, identifier, date,
affected-record, citation, source-hash and aggregation checks. Evidence-bound semantic
review is limited to the eight open Directive 1 historical-state equivalents and the
two wording-sensitive controls documented in the rubric. Configure exactly these
external variables:

- `LLM_JUDGE_BASE_URL`
- `LLM_JUDGE_API_KEY`
- `LLM_JUDGE_MODEL`
- `LLM_JUDGE_CACHE_DIR`
- `LLM_JUDGE_MODE`
- `LLM_JUDGE_TIMEOUT_SECONDS`

`LLM_JUDGE_MODE` accepts `auto`, `fresh` and `replay`. Cache entries bind the complete
request, model, sources and candidate. Only the exact Golden replay receipt is delivered;
changed artifacts miss it and are judged live in `auto` or fail closed in `replay`.
Provider caches and runtime outputs remain outside the package.

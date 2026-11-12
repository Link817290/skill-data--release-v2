# Product Launch Import

This package builds a staged Shopify import for ten camping-chair product
families from the supplied Chinese merchandising handover and product evidence.
The required deliverable is `/workspace/output/products.csv`.

## Build

Build the no-skill actor, with-skill actor, and isolated verifier from the
package root:

```sh
docker build -t product-launch-import:1.3 -f task/environment/Dockerfile task/environment
docker build -t product-launch-import-with-skill:1.3 -f task/environment/Dockerfile.skills task/environment
docker build -t product-launch-import-verifier:1.3 -f task/environment/Dockerfile.verifier .
```

All three images inherit from the standard `harbor-claude-code-aggregated:1.3`
base. The actor has no network access. Only the verifier requires network access
for a fresh semantic review.

## Score

The scorer combines deterministic catalog validation with a source-bound text
judge. Configure the isolated verifier with exactly these six public variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`,
`LLM_JUDGE_TIMEOUT_SECONDS`, `LLM_JUDGE_CACHE_DIR`, and `LLM_JUDGE_MODE`.
The default model is `gpt-5.6-sol`; `LLM_JUDGE_MODE` accepts `fresh` or `replay`.
Replay accepts only an exact request-bound response from the external cache
directory or the packaged Golden fixture.

```sh
docker run --rm --network host \
  -e LLM_JUDGE_BASE_URL -e LLM_JUDGE_API_KEY \
  -e LLM_JUDGE_MODEL=gpt-5.6-sol \
  -e LLM_JUDGE_TIMEOUT_SECONDS=600 \
  -e LLM_JUDGE_CACHE_DIR -e LLM_JUDGE_MODE=fresh \
  -v "$PWD/golden:/workspace/output:ro" \
  -v "$PWD/.score-logs:/logs" \
  product-launch-import-verifier:1.3 /task/tests/test.sh
```

The Golden must produce `reward_strict=1.0` and `reward_lenient=1.0`. A judge,
dependency, or input failure remains unmeasured rather than becoming a candidate
zero.

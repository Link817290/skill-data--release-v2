# Hotel GM Termination Settlement

Audit the supplied hotel general-manager termination materials and deliver a
reviewable settlement workbook at `/workspace/output/赔付清单.xlsx`.

## Build

From this package root:

```sh
docker build --pull=false --target actor-with-skill \
  -t hotel-gm-termination-settlement:1.0 \
  -f task/environment/Dockerfile task/environment
docker build --pull=false --target actor-no-skill \
  -t hotel-gm-termination-settlement-no-skill:1.0 \
  -f task/environment/Dockerfile task/environment
docker build --pull=false \
  -t hotel-gm-termination-settlement-verifier:1.0 \
  -f task/environment/Dockerfile.verifier task
```

All images explicitly use `harbor-claude-code-aggregated:1.3`. With-skill and
no-skill derive from the same `runtime` stage and differ only in whether `/skills`
is copied. Actors run offline; the separate verifier uses public networking for
fresh semantic review.

## Oracle And Scoring

Mount `task/solution` at `/solution` and run `bash /solution/solve.sh /workspace`.
Mount `task/tests` at `/tests`, provide a writable `/logs/verifier`, and run
`bash /tests/test.sh`.

Fresh scoring uses exactly six verifier-side variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`,
`LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` and `LLM_JUDGE_TIMEOUT_SECONDS`.
The judge uses OpenAI Responses. Replay cache entries are bound to the complete
request, source packet and workbook evidence. A cache miss, judge outage or invalid
response is `UNMEASURED`; it does not become a candidate zero.

Strict reward is the documented 100-point continuous rubric. Lenient reward is an
independent completion conjunction: every settlement owner must have a source-bound
adopted conclusion and its required deterministic amount or calculation chain; the
workbook must also cite enough source materials, show a calculation method, and keep
confirmed, conditional, unknown and continuing obligations separate. Lenient never
compares strict reward to a threshold.

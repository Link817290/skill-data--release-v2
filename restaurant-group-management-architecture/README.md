# Restaurant Group Management Architecture

This benchmark asks the agent to produce one Chinese management-design chapter at `output/control-system-and-long-term-architecture.md`. The chapter allocates decision authority and target/budget responsibilities across the Group, listed company, Hotel BU and Investment BU, then derives the management architecture for the settled N+1 and dual-sector long-term variants.

The with-skill condition receives `group-control-design`; the no-skill condition receives the same instruction and briefing material without that skill. The actor contains no Golden or evaluator assets.

## Runtime

Actor and verifier images derive from `harbor-claude-code-aggregated:1.3`. The actor is offline. The verifier combines deterministic structure and explicit-relation checks with one source-bound OpenAI-compatible semantic review. The semantic model is fixed to `gpt-5.6-sol`; configure `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY` for an unseen submission. A missing service or invalid response is an evaluator error and publishes no score.

The unchanged Golden uses the single request-bound replay in `task/tests/semantic_replay`. Replay identity includes the candidate, issued material, skill references, criteria, schema, model and semantic runtime. Cache misses require a fresh call.

Build from the package root:

```sh
docker build -t restaurant-group-actor task/environment
docker build -f task/environment/Dockerfile.verifier -t restaurant-group-verifier .
```

Run the verifier in its image with:

```sh
bash /task/tests/test.sh /workspace
```

Rewards are written to `VERIFIER_OUTPUT_DIR` (default `/logs/verifier`).

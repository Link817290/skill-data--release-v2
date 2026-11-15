# Rest-day attendance and compensatory-leave reconciliation

This package evaluates an evidence-bounded reconciliation of nine attendance events, compensatory-leave records, payroll status and unresolved follow-up work. The required outputs are `output/rest-day-review.xlsx` and the Chinese `output/review-conclusions.txt`.

Build the actor variants from `task/environment` and the verifier from the package root:

```sh
docker build --pull=false --target with-skill -t rest-day-hours-reconciliation-with-skill:1.3 -f Dockerfile task/environment
docker build --pull=false --target no-skill -t rest-day-hours-reconciliation-no-skill:1.3 -f Dockerfile task/environment
docker build --pull=false -t rest-day-hours-reconciliation-verifier:1.3 -f task/environment/Dockerfile.verifier .
```

The actors use the same workspace and runtime; only the with-skill target copies the issued skill into `/skills`. The verifier is built entirely from this package.

Event meaning, compensatory-leave status, disposition, payroll status, follow-up quality and report controls use the source-bound `gpt-5.6-sol` judge. Configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` and `LLM_JUDGE_TIMEOUT_SECONDS` outside the package. `fresh` scores a new candidate without a pre-existing cache. `replay` requires an exact request/runtime-bound cache. `auto` uses the single packaged Golden replay when it matches and otherwise performs fresh measurement. File parsing, event identity, citations and time arithmetic remain deterministic.

# Progress Library API Repair

Repair the supplied Python progress-reporting library while preserving its
public APIs and unrelated behavior. The task is offline and self-contained;
the source tree, focused verifier, reference solution, and repair report are
the only task inputs.

The strict score is continuous and evidence-based. The verifier imports the submitted source tree and checks eleven independent contracts across formatting, output policy, lifecycle, asynchronous iteration, concurrent mapping, and monitor shutdown. It also checks locally bound causal records in the required repair report. A report-only submission or a source stub cannot satisfy the checks.

The lenient score is a separate binary delivery-completion check over the same submission: the report is present, decodable and non-empty, carries the requested title and sections, holds populated defect records, every delivered module parses, and the delivered tree imports as a library with its own declared exports resolving. It reads no strict component. `reward` is an alias of the strict score, and the pass rate is the mean of the lenient score. Both are defined in `RUBRIC.md` and recomputed by `task/tests/validator.py`.

The runtime skills are mounted only for with-skill runs. The no-skill task copy uses the same source, instruction, solution, and verifier with the skill directory omitted.

## Package layout

The package root contains only `README.md`, `RUBRIC.md`, `dataset.toml`,
`MANIFEST.json`, `golden/`, and `task/`. Build images from the package root:

```sh
docker build --pull=false --target with-skill -t progresslib-api-repair-with-skill:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false --target no-skill -t progresslib-api-repair-no-skill:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false -t progresslib-api-repair-verifier:1.3 -f task/environment/Dockerfile.verifier .
```

All images use `harbor-claude-code-aggregated:1.3`. With-skill and no-skill
actors receive byte-identical workspace inputs; only with-skill receives the
runtime skills. Golden and verifier sources are not actor-visible.

## Contract

Follow `task/instruction.md`. Deliver the repaired source tree and
`/workspace/output/repair_report.md` in English. The Oracle is
`task/solution/solve.sh`; scoring runs through `task/tests/test.sh`.

The verifier accepts only these judge variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`,
`LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS`.
Executable behavior is checked locally. Report meaning is adjudicated by the
request-bound `gpt-5.6-sol` judge in fresh mode or by the packaged replay in
offline mode. Golden must score strict and lenient `1.0`.

## Scoring

`RUBRIC.md` is the public scoring contract and `task/tests/validator.py` is
the executable entry point. `reward` aliases the continuous strict score;
`reward_lenient` is an independent binary delivery lens. No score cap or
target-floor adjustment is applied.

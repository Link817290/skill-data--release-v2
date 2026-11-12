# Civil Appeal Petition

Prepare a Chinese civil appeal for the first-instance defendant from the issued anonymized judgment. Submit `artifacts/civil-appeal-petition.md` under `/workspace`.

The package contains `README.md`, `dataset.toml`, `RUBRIC.md`, `MANIFEST.json`, `golden/` and `task/`. Original case materials are under `task/environment/workspace/materials`; actor skills are under `task/environment/skills`. The original authored reference has Markdown and DOCX carriers in `golden/`.

Build the actor images from the environment directory and the private verifier from the package root:

```bash
docker build -t civil-appeal-actor-skill:1.0 -f task/environment/Dockerfile task/environment
docker build -t civil-appeal-actor-no-skill:1.0 -f task/environment/Dockerfile.no_skill task/environment
docker build -t civil-appeal-verifier:1.0 -f task/environment/Dockerfile.verifier .
harbor run -p task -a oracle
```

Use `task/task_no_skill.toml` as `task.toml` in a separate task materialization for the no-skill condition. Both use the same issued inputs, submission path and scorer. The actor has no network and contains neither tests, Golden nor judge credentials. The verifier is a separate public-network environment. The authorized base is `harbor-claude-code-aggregated:1.3`; Python, the standard library and `python-docx==1.2.0` are checked by the delivered build.

Externally export `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default `gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` (default `fresh`), and `LLM_JUDGE_TIMEOUT_SECONDS` (default `240`). Harbor resolves these only for the verifier. No judge credential is needed by the actor. The API must support Responses with the configured model.

Both task configurations declare a mixed judge with continuous reward and capture `/workspace/artifacts`.

The Oracle entrypoint is `bash task/solution/solve.sh /workspace`. It intentionally replays the evaluator-private authored reference fixture in `task/solution/reference`; it is not independent source-derived generation. Independently score the authored Golden by placing its Markdown at the submission path and invoking the same scorer:

```bash
VERIFIER_OUTPUT_DIR=/logs/verifier bash task/tests/test.sh /workspace
```

Scoring requires evidence-bound semantic judgment and deterministic record/legal checks. `reward.json` contains only numeric reward keys; explanations and source/candidate quotations are in `reward_detail.json`. Judge failure clears previous rewards, writes `UNMEASURED` status, and exits nonzero. Missing or unreadable candidate work scores zero.

`task/tests/golden_replay/` contains exactly one response keyed by the unchanged Golden's complete semantic-request SHA-256. It contains no ordinary candidate response, run/provider history or credential and is outside the actor image. The exact Golden can replay offline with origin `golden_replay`.

Any changed or new artifact misses that record and requires fresh external adjudication through `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY`. `LLM_JUDGE_REPLAY_ONLY=1` forbids live fallback; a replay miss is `UNMEASURED` and exits nonzero. The Golden response is never reused for another candidate. An externally managed replay directory may be supplied with `LLM_JUDGE_CACHE_DIR`, but it is not packaged.

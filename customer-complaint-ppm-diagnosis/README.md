# Customer Complaint PPM Diagnosis

Create an editable diagnosis workbook from the issued January–August complaint,
sales and reported-rate source. The public requirements and filename contract are
in `task/instruction.md` and
`task/environment/workspace/materials/output_contract.json`; the scoring contract
is `RUBRIC.md`.

## Build And Task Arms

Build the actor image from the package root:

```sh
docker build --pull=false \
  -t customer-complaint-ppm-diagnosis:1.0 \
  task/environment
```

The image uses `harbor-claude-code-aggregated:1.3`, runs as UID 20005 and has no
network. Its build verifies both issued material files and creates
`/workspace/output`. The verifier uses the same base image in a separate public
network environment; Harbor supplies the private tests and transfers only the
declared candidate artifact. The with-skill and no-skill task configurations use
the same scorer and instruction. Select `task/task_no_skill.toml` as `task.toml`
in an external task copy for the no-skill arm, without attaching the packaged
`ppm-diagnosis` Skill.

## Output And Oracle

The only accepted deliverable is:

```text
/workspace/output/cppm_diagnosis.xlsx
```

The authored Oracle entrypoint is `task/solution/solve.sh`. It copies the
packaged, validated reference workbook from `golden/cppm_diagnosis.xlsx`; it is a
reference-artifact Oracle, not an independent runtime recomputation. Golden and
the Oracle output are expected to be byte-identical and score strict/lenient
`1/1`.

## Scoring And External Judge Boundary

The verifier entrypoint is:

```sh
sh task/tests/test.sh /workspace/output
```

It recomputes numeric owners from the evaluator source workbook, then settles an
evidence-bound semantic review. Configure the isolated verifier, never the actor,
with `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY`. The endpoint must implement
OpenAI Responses and `LLM_JUDGE_MODEL` must name a GPT judge. A new request needs
verifier network access.

Set `LLM_JUDGE_CACHE_DIR` to an external writable directory to retain an exact
artifact/source/prompt/model-bound response. Set `LLM_JUDGE_MODE=replay` for
replay-only operation; the default is fresh.
`LLM_JUDGE_TIMEOUT_SECONDS` controls the fresh request timeout.
Otherwise a cache miss performs a fresh evaluator call. A cache miss in
replay mode, invalid judge reply
or evaluator failure is UNMEASURED: the entrypoint removes stale numeric rewards,
writes status/review receipts and exits nonzero rather than assigning business
zero.

The release contains exactly one verifier-only Golden response under
`task/tests/content_judge/golden_replay/<exact-key>/`. It has no credentials and
is not copied into the actor image. No generic cache or ordinary-candidate/provider
response ships. A new artifact never reuses this entry: cache
misses require fresh evaluator access or remain UNMEASURED.

Successful runs write `reward.txt`, `reward_strict.txt`, `reward_lenient.txt`,
`reward.json` and `reward_detail.json` under `VERIFIER_OUTPUT_DIR` (default
`/logs/verifier`). Preserved candidate artifacts
go to `ARTIFACT_OUTPUT_DIR` (default `/logs/artifacts`). Runtime caches, logs and
credentials are external process state and are not release-package files.

# employee-engagement-q12-diagnostic

This package produces a privacy-safe, auditable Q12 employee-engagement diagnostic from two survey waves, population margins, identity permissions, personnel timing and a matched variance design.

## Release Structure

The six root entries are `README.md`, `MANIFEST.json`, `RUBRIC.md`, `dataset.toml`, `golden/` and `task/`.

## Build And Conditions

```bash
docker build -t employee-engagement-q12-diagnostic:release \
  -f task/environment/Dockerfile task/environment
```

`task/task.toml` is the with-skill condition; `task/task_no_skill.toml` uses the same instruction, material, outputs and verifier without the skill mount.

## Material And Outputs

The task instruction is `task/instruction.md`. `/workspace/materials` contains 13 XLSX sources and the public `formula_reference.md`, including the two permitted calibration-population interpretations. Both conditions receive the same 14 files.

Required outputs:

- `/workspace/output/cleaned_samples.xlsx`
- `/workspace/output/engagement_analysis.xlsx`

## Reference Build And Oracles

```bash
bash task/solution/solve.sh /tmp/q12-workspace
python -B task/tests/validator.py /tmp/q12-workspace
```

The reference pipeline independently derives cleaning, calibration, replicate, reliability, organization, panel, decomposition, multiplicity and sensitivity results from task material. The program Oracle recomputes the same source-bound quantities and applies the A–F owner contract in `task/tests/scoring_params.json`.

`task/tests/test.sh` is the verifier entrypoint. It writes strict and lenient rewards and A–F dimension scores under `/logs/verifier/`.

## Reward Semantics

Strict reward is the earned A–F diagnostic evidence divided by 100 after dependency release limits and explicit unusable-release limits. Lenient reward is one only when all ten delivery, identity, action, disclosure, privacy and calibrated-trend quality checks pass. Lenient reuses section B evidence for its calibrated-trend floor and is not independent of strict.

Missing evidence earns no completion or restricts the dependent release. Explicitly wrong weights, populations, identity use, uncertainty or privacy disclosure are treated as errors rather than unknown states. Infrastructure or verifier exceptions are reported separately in the detail output and must not be reinterpreted as a valid diagnostic.

The Golden reference yields strict `1.0` and lenient `1.0` through both the direct program Oracle and the unified verifier entrypoint.

Numeric, formula and table owners are programmatic. D5 organization-action
meaning and E6 causal/response-rate/small-sample boundaries require the
source-bound semantic judge and enter the same final ledger. Judge failure is
UNMEASURED. The release contains only the exact Golden reply under
`task/tests/golden_replay/<key>/`; ordinary candidate/provider caches are not
release content. Actors cannot access verifier replies or credentials.
Fresh semantic measurement uses only OpenAI Responses with a GPT judge through
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY` and optional `LLM_JUDGE_MODEL`.
`LLM_JUDGE_MODE=replay` disables fresh calls and `LLM_JUDGE_CACHE_DIR` selects
the external request-bound cache directory.
`LLM_JUDGE_TIMEOUT_SECONDS` controls the fresh request timeout.
Incomplete, invalid or incompatible replies are UNMEASURED.

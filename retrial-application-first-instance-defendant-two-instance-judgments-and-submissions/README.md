# Retrial application from two-instance judgments and submissions

Draft a Chinese civil retrial application for the first-instance defendant from
the supplied first-instance judgment, effective second-instance judgment, written
opinion, and counsel submission.

## Package layout

The package root has exactly six entries:

```text
MANIFEST.json
README.md
RUBRIC.md
dataset.toml
golden/
task/
```

`task/instruction.md` is the actor-facing instruction. Source files are under
`task/environment/workspace/materials/`, the with-skill resources are under
`task/environment/skills/`, and the required deliverable is
`artifacts/retrial-application.md`.

## Environment

The actor image uses `harbor-claude-code-aggregated:1.3`:

```sh
docker build --pull=false \
  -t retrial-application-first-instance-defendant-two-instance-judgments-and-submissions:1.3 \
  -f task/environment/Dockerfile task/environment
```

The actor runs without network access. The harness supplies the skill directory
only for the with-skill condition; both conditions receive byte-identical source
materials.

## Scoring

`task/tests/test.sh` is the scoring entry point and
`task/tests/validator.py` publishes continuous strict and binary lenient scores.
The deterministic program judge owns carrier parsing, explicit figures, filing
regions, statutory references, damage instances, and the delivery contract.

P04, P13, P14, and P15 use one request-bound source adjudication with
`gpt-5.6-sol`. Configure fresh evaluation with:

- `LLM_JUDGE_BASE_URL`
- `LLM_JUDGE_API_KEY`
- `LLM_JUDGE_MODEL` (default `gpt-5.6-sol`)
- `LLM_JUDGE_CACHE_DIR` (optional writable cache directory)
- `LLM_JUDGE_MODE` (`auto`, `fresh`, or `replay`)
- `LLM_JUDGE_TIMEOUT_SECONDS` (default `600`)

The packaged cache contains only the exact Golden request. A new candidate uses
a fresh model call; replay mode fails on a cache miss instead of inferring a
business score. `RUBRIC.md` and `task/tests/rubric-contract.json` describe the
same weights, partial-credit rules, deductions, and lenient necessities.

The Oracle entry point is `task/solution/solve.sh`. Golden must score strict and
lenient `1.0` in both fresh and exact replay modes.

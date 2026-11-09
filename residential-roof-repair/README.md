# Residential Roof Repair Enquiry

This package asks an agent to turn the supplied Chinese repair schedules into a
contractor-ready roof-repair enquiry. The required files are
`/workspace/output/维修询价清单.xlsx` and
`/workspace/output/施工范围说明.docx`. The actor receives only the public input
files and, in the with-skill condition, the packaged scope-repair skill.

## Build

Both actor images use `harbor-claude-code-aggregated:1.3`:

```bash
docker build --target with-skill -t residential-roof-repair-with-skill:1.3 task/environment
docker build --target no-skill -t residential-roof-repair-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t residential-roof-repair-verifier:1.3 .
```

The actor images have no network dependency. The verifier image contains the
public materials, evaluator, Golden reference and exact Golden replay fixture;
semantic judging of a new artifact uses evaluator-side network access.

## Oracle And Evaluation

Run `task/solution/solve.sh` to reproduce the Golden deliverables. Run
`task/tests/test.sh` through the verifier entrypoint to score a submission. The
evaluator first recalculates submitted workbook formulas on an isolated copy,
then combines independent quantity checks with source-bound semantic review.

Configure these six evaluator variables:

- `LLM_JUDGE_BASE_URL`
- `LLM_JUDGE_API_KEY`
- `LLM_JUDGE_MODEL`
- `LLM_JUDGE_CACHE_DIR`
- `LLM_JUDGE_MODE`
- `LLM_JUDGE_TIMEOUT_SECONDS`

`LLM_JUDGE_MODE` accepts `auto`, `fresh`, or `replay`. Replay is allowed only
when the complete request hash matches. The package contains one request-bound
Golden fixture; new artifacts use fresh judging in `auto` or `fresh` mode.

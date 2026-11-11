# Fixed-Asset Depreciation

## Task

Complete the supplied fixed-asset workbook as an offline, formula-driven
depreciation model. Preserve inputs, sheets, formatting and charts while adding
four depreciation methods, opening balances, transfers, department/category
reporting and visible input controls. See `task/instruction.md` and `RUBRIC.md`.

## Inputs And Workspace

The original input is
`task/environment/workspace/materials/workspace.xlsx`. It is byte-identical to
the verifier's private `task/tests/material.xlsx`. With-skill additionally
registers the three skills under `task/environment/skills/`; no-skill receives
the same workbook without skills.

## Deliverable

Write `/workspace/output/fixed_asset_model.xlsx`. No separate report is required.
The authored reference workbook is `golden/output/fixed_asset_model.xlsx`.

## Runtime And Isolation

Actors run offline and contain no tests or Golden. Build from the package root:

```sh
docker build -t fixed-asset-depreciation:1.0 -f task/environment/Dockerfile task/environment
docker build -t fixed-asset-depreciation-no-skill:1.0 -f task/environment/Dockerfile.no_skill task/environment
docker build -t fixed-asset-depreciation-verifier:1.0 -f task/environment/Dockerfile.verifier .
```

The private verifier uses public networking only for fresh semantic evaluation.
Only verifier env receives `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`,
`LLM_JUDGE_MODEL`, `LLM_JUDGE_MODE`, `LLM_JUDGE_CACHE_DIR` and
`LLM_JUDGE_TIMEOUT_SECONDS`. The sole qualified transport is OpenAI
Responses with `gpt-5.6-sol`; Chat and Anthropic Messages fail closed.

## Oracle And Golden

`task/solution/solve.sh` copies the immutable authored reference under
`task/solution/reference/` into the requested actor workspace. The reference and
root Golden are byte-identical. Run `bash /solution/solve.sh /workspace` with
only `task/solution` mounted read-only.

## Scoring And Replay

`task/tests/test.sh` invokes `task/tests/validator.py`. Native LibreOffice
measurements exercise formulas under valid, boundary and invalid inputs. Strict
is the weighted completion of the accounting control owners. Lenient reports
the independent must-have checks and their failed IDs.

The verifier's `auto` mode replays only the packaged exact Golden binding and
sends every new artifact to fresh evaluation through the verifier-only endpoint.
`LLM_JUDGE_MODE=replay` can use an evaluator-owned artifact/request-bound cache
selected through `LLM_JUDGE_CACHE_DIR`. A cache miss,
judge outage or missing credentials is `verifier_error` with
`candidate_score_assigned=false`, not a candidate zero. Missing the required
workbook itself is a measured business zero.

## Package Map

- with-skill task: `task/task.toml`
- no-skill task: `task/task_no_skill.toml`
- source material: `task/environment/workspace/materials/workspace.xlsx`
- Golden: `golden/output/fixed_asset_model.xlsx`
- Oracle: `task/solution/solve.sh`
- strict contract/runtime: `task/tests/rubric-contract.json`, `task/tests/scoring_params.json`
- lenient contract: `task/tests/must_have.json`
- scoring entrypoint: `task/tests/test.sh`

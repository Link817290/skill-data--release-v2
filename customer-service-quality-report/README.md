# Customer Service Quality Report

Create an editable Chinese management workbook for the 26 March 2015 online
service-quality review from finalized quality records, disclosed operational
bases and the owner-approved reporting policy. See `task/instruction.md` for the
deliverable and `RUBRIC.md` for source ownership, dependencies and settlement.

## Build And Task Arms

Build the actor image from the package root:

```sh
docker build --pull=false \
  -t customer-service-quality-report:1.0 \
  task/environment
```

The build uses `harbor-claude-code-aggregated:1.3`, verifies the two issued XLSX
materials and the installed LibreOffice recalculation tool, creates
`/workspace/output`, and runs as UID 20005 without actor network access. The
separate verifier uses the same image with public network mode and private tests.
For the no-skill arm, use an external copy of `task/` with
`task_no_skill.toml` selected as `task.toml` and do not attach the
`service-quality-reporting` Skill. Both arms use the same instruction and scorer.

## Output And Oracle

The required deliverable is:

```text
/workspace/output/service-quality-report.xlsx
```

The authored Oracle entrypoint is `task/solution/solve.sh`. It copies the
packaged `task/solution/independent_reference.xlsx`, a separately validated
reference workbook whose table values and chart bindings are source-derived. The
Oracle does not regenerate the workbook at runtime. Golden and the independent
Oracle are both expected to score strict/lenient `1/1`, with five valid native
chart roles and no independent damage.

## Scoring And External Judge Boundary

With the candidate under `/workspace/output` and a writable verifier directory,
run:

```sh
VERIFIER_OUTPUT_DIR=/logs/verifier \
  bash task/tests/test.sh /workspace
```

`task/tests/validator.py` validates source-derived tables, totals, workload,
native chart bindings and formula caches; LibreOffice is used only when submitted
formulas lack stored values. It awards no open-semantic credit from keywords.
`task/tests/mix_judge/apply.py` requires source-bound A01-A09 decisions and settles
them with the program prerequisites and damages. Judge failure is UNMEASURED.

Configure only the isolated verifier with `LLM_JUDGE_BASE_URL` and
`LLM_JUDGE_API_KEY`; `LLM_JUDGE_MODEL` and `LLM_JUDGE_TIMEOUT_SECONDS` are optional.
Fresh measurement is required on a cache miss. `LLM_JUDGE_CACHE_DIR` must point
to external request-bound cache packages. `LLM_JUDGE_MODE=replay` uses only an
exact matching cache and works without network or credentials. Missing services,
cache misses in replay mode and invalid replies are UNMEASURED, remove numeric
reward files and exit nonzero; they are not business scores.

Successful runs write numeric `reward.json`, `reward.txt`,
`reward_strict.txt`, `reward_lenient.txt`, detailed `reward_detail.json` and
`semantic_review.json` to `VERIFIER_OUTPUT_DIR` (default `/logs/verifier`). Judge
caches, logs, credentials and generated process outputs stay outside this release
package.

The release ships exactly one verifier-only Golden replay under
`task/tests/mix_judge/golden_replay/<exact-key>/`. It contains the bound request,
evidence, raw response, validated review and integrity manifest, but no credential.
No ordinary-candidate or provider cache ships, and actors cannot access
the verifier test tree. A different artifact key misses this entry and must use
fresh measurement or remain UNMEASURED.

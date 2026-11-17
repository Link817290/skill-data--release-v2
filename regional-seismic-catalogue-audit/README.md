# Regional Seismic Catalogue Audit

This package asks an analyst to build an evidence-bound JSON register from
three supplied HTML catalogues. The output preserves every source row,
normalizes event observations, computes the published `regional-screen-v1`
statistics, reconciles repeated identities, and closes page/comparative totals.
The package is self-contained and actor networking is disabled.

## Package layout

```text
regional-seismic-catalogue-audit/
  README.md
  RUBRIC.md
  dataset.toml
  MANIFEST.json
  golden/seismic_catalogue_report.json
  task/
    instruction.md
    task.toml
    task_no_skill.toml
    environment/
      Dockerfile
      Dockerfile.verifier
      workspace/materials/
      skills/
    solution/
    tests/
```

The actor images are built from `harbor-claude-code-aggregated:1.3`. The
with-skill image mounts the four domain skills; the no-skill image uses the
same byte-identical workspace without that mount. The verifier is a separate
image and receives the workspace, tests, Golden reference and scoring code.

## Build and score

```sh
docker build --pull=false --target with-skill \
  -t regional-seismic-catalogue-audit-with-skill:1.3 task/environment
docker build --pull=false --target no-skill \
  -t regional-seismic-catalogue-audit-no-skill:1.3 task/environment
docker build --pull=false \
  -t regional-seismic-catalogue-audit-verifier:1.3 \
  -f task/environment/Dockerfile.verifier .
```

The Oracle is `task/solution/solve.sh`. The evaluator is
`task/tests/test.sh`; it writes `reward_strict.txt`, `reward_lenient.txt`,
`reward.json`, and the detailed ledger under the verifier output directory.
Golden must score `1.0` on both lenses.

The mixed configuration accepts exactly these verifier judge variables when a
deployment supplies an external semantic judge:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`,
`LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS`.
This task's published checks are source-bound numeric and structural checks;
they do not use keyword-only semantic fallbacks or a legacy mix gate.

## Scoring contract

`RUBRIC.md` explains the fourteen positive evidence items, their professional
weighting, fixed timestamp precision, canonical occurrence policy,
multiplicative deductions, and the independent lenient delivery lens.
`task/tests/scoring_params.json` is the executable weight/coefficient source;
the Golden and Oracle are generated from the same bundled HTML materials.

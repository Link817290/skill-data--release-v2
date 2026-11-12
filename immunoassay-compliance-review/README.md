# Immunoassay Compliance Review

Review the supplied immunoassay workbook and complete the Chinese Markdown report at
`/workspace/output/review_report.md`. The workbook is the only governing material in
the actor workspace. Golden, evaluator facts, Oracle code and judge credentials remain
evaluator-only.

## Package layout

The package has the standard six root entries: `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/` and `task/`. The original workbook and report template are under
`task/environment/workspace`; the actor-facing method is under
`task/environment/skills/expert-task-method`.

## Build

All images derive explicitly from `harbor-claude-code-aggregated:1.3`:

```sh
docker build --target with-skill -t immunoassay-compliance-review:1.3 task/environment
docker build --target no-skill -t immunoassay-compliance-review-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t immunoassay-compliance-review-verifier:1.3 .
```

Both actor images contain the same workbook, template, instruction and output path. Only
the with-skill target contains `/skills`. Actor networking is disabled. The independent
verifier has public networking only for semantic judging.

## Oracle and scoring

Mount `task/solution` at `/solution` only for Oracle validation and run:

```sh
sh /solution/solve.sh /workspace
sh /tests/test.sh /workspace/output/review_report.md
```

The mixed evaluator verifies numerical values, batch inventory, formulas, workbook cells
and file integrity in program code. An evidence-bound Responses judge evaluates semantic
metric identity, cross-table input binding, formal-rule sufficiency, conclusion
traceability and professional evidence boundaries. Equivalent professional language is
accepted; keyword accumulation and unsupported formal conclusions are not.

Configure exactly these verifier variables externally:

- `LLM_JUDGE_BASE_URL`
- `LLM_JUDGE_API_KEY`
- `LLM_JUDGE_MODEL`
- `LLM_JUDGE_CACHE_DIR`
- `LLM_JUDGE_MODE` (`auto`, `fresh`, or `replay`)
- `LLM_JUDGE_TIMEOUT_SECONDS`

An exact Golden replay is included under `task/tests/golden_replay`. It is bound to the
complete semantic request and Golden bytes. Changed artifacts miss that replay and require
an external cache or a live judge. Replay misses and provider/protocol failures are
`UNMEASURED`; they never become a candidate score of zero. See `RUBRIC.md` for the complete
strict settlement and independent binary lenient usability contract.

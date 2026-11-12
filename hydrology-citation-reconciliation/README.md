# Hydrology Citation Reconciliation

This package asks an agent to audit the author-date citations in the supplied
hydrology manuscript and deliver an English editorial handoff at
`/workspace/output/citation_reconciliation.md`. The actor works offline from the
manuscript PDF. Golden, evaluator facts, the Oracle and judge credentials remain
evaluator-only.

## Build

All runtime images use `harbor-claude-code-aggregated:1.3`:

```bash
docker build --target with-skill -t hydrology-citation-reconciliation:1.3 task/environment
docker build --target no-skill -t hydrology-citation-reconciliation-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t hydrology-citation-reconciliation-verifier:1.3 .
```

Both actor images derive from the same runtime stage and work from the same
manuscript. Only the with-skill image contains `/skills`. Actor networking is
disabled; the separate verifier may use public networking for semantic judging.

## Oracle And Evaluation

Run `task/solution/solve.sh` with the supplied workspace to create the reference
handoff. Run `bash task/tests/test.sh /workspace/output/citation_reconciliation.md`
to score an artifact. `AGENT_WORKSPACE`, `VERIFIER_OUT` and `ARTIFACTS_OUT`
select isolated runtime paths.

The mixed evaluator uses deterministic source-integrity, record, location,
mapping, control-total, repair-direction and relationship checks. Evidence-bound
semantic review is limited to professional equivalents that cannot be evaluated
safely from isolated terms. Configure exactly these external variables:

- `LLM_JUDGE_BASE_URL`
- `LLM_JUDGE_API_KEY`
- `LLM_JUDGE_MODEL`
- `LLM_JUDGE_CACHE_DIR`
- `LLM_JUDGE_MODE`
- `LLM_JUDGE_TIMEOUT_SECONDS`

`LLM_JUDGE_MODE` accepts `auto`, `fresh` and `replay`. Cache entries bind the
complete request, model, source evidence and candidate. The package includes only
the exact Golden replay fixture. A changed artifact misses that fixture and is
judged live in `auto` or fails closed in `replay`.

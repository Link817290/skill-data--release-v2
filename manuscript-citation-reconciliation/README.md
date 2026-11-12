# Manuscript citation reconciliation

Audit citations and bibliography differences across three supplied manuscript revisions.

## Package

The package root contains only `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/` and `task/`. Build all images from the package
root:

```sh
docker build --pull=false --target with-skill -t manuscript-citation-reconciliation-with-skill:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false --target no-skill -t manuscript-citation-reconciliation-no-skill:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false -t manuscript-citation-reconciliation-verifier:1.3 -f task/environment/Dockerfile.verifier .
```

All images derive from `harbor-claude-code-aggregated:1.3`. The actor runs
without network access. Both actor conditions contain byte-identical workspace
inputs; only the with-skill image contains `/skills`. Golden, Oracle and
evaluator sources are not actor-visible.

## Contract

The authoritative instruction is `task/instruction.md`. Required outputs:

- `/workspace/output/citation_audit.json`

The Oracle entry point is `task/solution/solve.sh`; the scoring entry point is
`task/tests/test.sh`.

The verifier exposes the same six judge variables as the other release
packages:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default
`gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` and
`LLM_JUDGE_TIMEOUT_SECONDS`. This task's required checks are deterministic and
source-bound: they independently parse the hash-gated DOCX materials and do not
call an external judge or read a judge cache. The variables remain part of the
standard interface so the package can be launched by the common harness without
special handling.

## Scoring

`RUBRIC.md` is the public scoring contract and `task/tests/validator.py` is
the executable entry. Deterministic checks own files, structure, arithmetic,
source-closed facts, and the explicitly documented equivalent serializations.
`reward` aliases the continuous strict score;
`reward_lenient` is the separate binary usability lens. Golden must score
strict and lenient `1.0`.

# Post-hearing construction payment argument

Prepare a Chinese post-hearing argument grounded in the supplied hearing and case-law materials.

## Package

The package root contains only `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/` and `task/`. Build all images from the package
root:

```sh
docker build --pull=false --target with-skill -t post-hearing-argument-2-4-with-skill:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false --target no-skill -t post-hearing-argument-2-4-no-skill:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false -t post-hearing-argument-2-4-verifier:1.3 -f task/environment/Dockerfile.verifier .
```

All images derive from `harbor-claude-code-aggregated:1.3`. The actor runs
without network access. Both actor conditions contain byte-identical workspace
inputs; only the with-skill image contains `/skills`. Golden, Oracle and
evaluator sources are not actor-visible.

## Contract

The authoritative instruction is `task/instruction.md`. Required outputs:

- `/workspace/output/post_hearing_argument.docx`

The Oracle entry point is `task/solution/solve.sh`; the scoring entry point is
`task/tests/test.sh`.

The verifier accepts exactly six external judge variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default
`gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` and
`LLM_JUDGE_TIMEOUT_SECONDS`. Fresh mode measures new artifacts through the
OpenAI Responses protocol. Replay mode accepts only a request-bound packaged or
external cache. A cache miss or judge/runtime failure exits nonzero without
publishing a business score.

## Scoring

`RUBRIC.md` is the public scoring contract and `task/tests/validator.py` is
the executable entry. Deterministic checks own files, structure, arithmetic and
source-closed facts. Where professional equivalence is required, the unified
source-bound judge evaluates meaning, negation, attribution and scope using
exact candidate evidence. `reward` aliases the continuous strict score;
`reward_lenient` is the separate binary usability lens. Golden must score
strict and lenient `1.0`.

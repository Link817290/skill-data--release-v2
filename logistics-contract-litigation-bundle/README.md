# Logistics contract litigation bundle

Prepare a consistent five-document Chinese litigation filing bundle from the supplied dispute record.

## Package

The package root contains only `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/` and `task/`. Build all images from the package
root:

```sh
docker build --pull=false --target with-skill -t logistics-contract-litigation-bundle-with-skill:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false --target no-skill -t logistics-contract-litigation-bundle-no-skill:1.3 -f task/environment/Dockerfile task/environment
docker build --pull=false -t logistics-contract-litigation-bundle-verifier:1.3 -f task/environment/Dockerfile.verifier .
```

All images derive from `harbor-claude-code-aggregated:1.3`. The actor runs
without network access. Both actor conditions contain byte-identical workspace
inputs; only the with-skill image contains `/skills`. Golden, Oracle and
evaluator sources are not actor-visible.

## Contract

The authoritative instruction is `task/instruction.md`. Required outputs:

- `/workspace/output/service-address-confirmation.docx`
- `/workspace/output/civil-complaint.docx`
- `/workspace/output/case-handoff.docx`
- `/workspace/output/evidence-list.docx`
- `/workspace/output/refund-account-confirmation.docx`

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
source-bound `gpt-5.6-sol` judge evaluates meaning, negation, attribution and
scope using exact candidate evidence. Its bounded settlement is documented in
`RUBRIC.md`; there is no task-specific target cap or floor. `reward` aliases the
continuous strict score; `reward_lenient` is the separate binary usability lens.
Golden must score strict and lenient `1.0`.

The supplied PDF records are scanned image documents. Fresh semantic review
renders image-only PDF pages and sends them as visual evidence to the judge;
empty text extraction is not treated as an empty source. Packaged replay remains
bound to its archived request and response.

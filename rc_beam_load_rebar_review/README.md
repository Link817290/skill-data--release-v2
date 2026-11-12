# Reinforced-Concrete Beam Calculation Review

Prepare an independent, source-bound review workbook for the supplied
reinforced-concrete beam calculation. The submission must preserve the input
evidence, reproduce the load, flexure and shear chains with inspectable Excel
formulas, publish controlled findings, and state a defensible overall
disposition.

## Package layout

The package root contains only `README.md`, `RUBRIC.md`, `dataset.toml`,
`MANIFEST.json`, `golden/`, and `task/`.

Build the actor and verifier images from the package root:

```sh
docker build --pull=false --target with-skill \
  -t rc_beam_load_rebar_review-with-skill:1.3 \
  -f task/environment/Dockerfile task/environment

docker build --pull=false --target no-skill \
  -t rc_beam_load_rebar_review-no-skill:1.3 \
  -f task/environment/Dockerfile task/environment

docker build --pull=false \
  -t rc_beam_load_rebar_review-verifier:1.3 \
  -f task/environment/Dockerfile.verifier .
```

All images use `harbor-claude-code-aggregated:1.3`. The with-skill and
no-skill actors receive byte-identical workspace inputs; only the with-skill
actor receives `/skills`. Golden and verifier sources are not actor-visible.

## Contract

Follow `task/instruction.md` and write `/workspace/beam_review.xlsx`. The
Oracle is `task/solution/solve.sh`, and scoring runs through
`task/tests/test.sh`.

The verifier accepts only these judge variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`,
`LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and
`LLM_JUDGE_TIMEOUT_SECONDS`. Structural and numerical relations are checked
locally. Finding rationales use the request-bound `gpt-5.6-sol` judge in fresh
mode or the packaged Golden replay in offline mode.

## Scoring

`RUBRIC.md` defines the public scoring contract, and
`task/tests/validator.py` is the executable scorer. `reward` aliases the
continuous strict score. The lenient score is a separate binary completion
lens over the task's must-have engineering conclusions; it does not cap or
rescale strict. No target floor or score cap is applied. Golden and Oracle must
both score strict and lenient `1.0`.

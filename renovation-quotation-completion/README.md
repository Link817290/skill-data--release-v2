# Renovation Quotation Completion

Complete a source-bound Chinese renovation quotation from the supplied schedule,
drawing and two visual references. The required deliverable is one editable XLS
or XLSX workbook under `/workspace/output`.

## Package

The release package contains only `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/` and `task/`.

```sh
docker build --pull=false -t renovation-quotation-completion:1.3 task/environment
```

The image derives from `harbor-claude-code-aggregated:1.3`. Both actor
conditions use byte-identical materials and have no network access. The
with-skill manifest exposes `renovation-quotation`; the no-skill manifest omits
the skill. Golden, Oracle and evaluator files are evaluator-only.

## Contract

The authoritative instruction is `task/instruction.md`. The Oracle entry point
is `task/solution/solve.sh`; the scorer is `task/tests/test.sh`.

The verifier accepts exactly six judge variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default
`gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` and
`LLM_JUDGE_TIMEOUT_SECONDS`. Fresh mode measures new work through the OpenAI
Responses protocol. Replay mode accepts only the exact request-bound Golden
fixture. A judge failure or replay miss is `UNMEASURED`, not a candidate zero.

## Scoring

The program layer measures preserved source inputs, supported row formulas,
section closure, equipment pricing and total dependency trees. The source-bound
semantic layer measures unresolved-item status, source fidelity and object/scope
binding across the schedule, drawing and visual references. Strict is
`0.80 * program + 0.20 * semantic`; lenient is an independent binary
coordination-readiness lens. Golden must score strict and lenient `1.0` in both
fresh and exact-replay modes.

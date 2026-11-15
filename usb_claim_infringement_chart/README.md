# USB Claim Infringement Chart

Create a source-grounded JSON claim chart comparing published and issued patent
claims with the supplied USB charging records. The analysis covers feature-level
evidence, claim construction, sensitivity, dependencies, family correspondence,
and terminal triage calls.

The actor image uses `harbor-claude-code-aggregated:1.3`. Run
`task/solution/solve.sh <output.json>` for the Oracle and
`task/tests/test.sh <output.json>` for evaluation. The scorer accepts explicitly
labelled contextual sources, gives no credit to missing rows, and requires all
terminal calls to be correct for the lenient lens.

Deterministic checks own structure, coverage, enums and arithmetic. Open claim
meaning, evidence roles and professional equivalence use the source-bound
`gpt-5.6-sol` reviewer. Configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`,
`LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` and
`LLM_JUDGE_TIMEOUT_SECONDS` for unseen artifacts. The package includes only the
exact request-bound Golden replay; judge failures publish no candidate score.

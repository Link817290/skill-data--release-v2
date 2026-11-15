# HACCP Plan Authorization Review

This package evaluates whether an agent can perform an evidence-limited technical review
of a seafood HACCP plan excerpt and turn the result into a decision-ready JSON audit.
The materials are frozen inside the task environment and the same program verifier with source-bound semantic adjudication
scores both experimental conditions.

The primary artifact is `haccp_audit.json`. It is assessed through a continuous strict
capability score and a binary lenient delivery score with professional-coverage and
evidence-binding floors. Both lenses also require the source-supported current
authorization decision: defer authorization until the missing controlled records
and validation are closed and re-reviewed. An adopted approval cannot be offset
by otherwise correct findings. The binary lens reuses strict anchor evidence and
is not independent.
`reward` is the compatibility alias for the strict score. Detailed scoring methodology is
defined in `RUBRIC.md`.
The task runs without network access. The source PDFs are read-only inputs, and source
integrity is checked during verification.

Fresh result-score semantic checks require evaluator-side `LLM_JUDGE_BASE_URL`,
`LLM_JUDGE_API_KEY`, and `LLM_JUDGE_MODEL` (default `gpt-5.6-sol`).
`LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` (`auto`, `fresh`, or `replay`), and
`LLM_JUDGE_TIMEOUT_SECONDS` control reproducible measurement. Golden replay uses the
single cache record in `task/tests/golden_replay`; new candidate artifacts use fresh
measurement when no matching cache exists. Required service failures abort scoring
without score artifacts. Runtime score files and probe logs are not part of this release
package. Agent workspace/network permissions are unchanged.
